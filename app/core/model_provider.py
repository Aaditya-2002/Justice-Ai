"""Model Provider Abstraction Layer for Justice AI.

This module provides a provider-agnostic interface for LLM inference.
Supports multiple providers through a common abstract base class.
"""

import asyncio
import os
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

try:  # The OpenAI SDK is also used for OpenAI-compatible endpoints (NVIDIA, Gemini).
    from openai import AsyncOpenAI
    from openai.types.chat import ChatCompletion
except ImportError:  # Offline test environments: adapters raise on construction.
    AsyncOpenAI = None
    ChatCompletion = None


class ProviderUnavailableError(Exception):
    """Raised when every configured provider failed (cooldowns honored).

    The message is safe: it never contains API keys or response payloads.
    """

    def __init__(self, provider_names: List[str], causes: List[str]):
        self.provider_names = provider_names
        self.causes = causes
        summary = "; ".join(f"{n}: {c}" for n, c in zip(provider_names, causes))
        super().__init__(f"All providers failed: {summary}")


def redact(text: str, *secrets: Optional[str]) -> str:
    """Return *text* with every secret replaced by '[REDACTED]'.

    Used on exception messages and logs so API keys can never leak.
    """
    result = text
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result


class ModelProvider(ABC):
    """Abstract base class for model providers."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        context: Optional[str] = None,
        skills: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        """Generate a response from the model.

        Args:
            prompt: The user's prompt or question.
            conversation_history: List of previous messages in the conversation.
            context: Retrieved context from RAG (optional).
            skills: List of available skills (optional).
            **kwargs: Additional provider-specific parameters.

        Returns:
            The generated response as a string.
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of the provider."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the name of the model."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is reachable and authenticated.

        Returns:
            True if the provider is healthy and ready to serve requests,
            False otherwise. Must not raise exceptions on failure.
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """Return the capabilities supported by this provider/model.

        Capabilities are per-model, not per-provider. Different models
        from the same provider may support different features.

        Returns:
            Dictionary mapping capability names to boolean support flags.
            Required keys:
              - chat_completions: Can generate chat responses
              - streaming: Supports token-by-token streaming
              - tool_calling: Supports function/tool calls
              - structured_output: Supports JSON/schema-constrained output
              - embeddings: Can generate embeddings
              - token_counting: Can count tokens
        """
        pass


class MockModelProvider(ModelProvider):
    """A mock model provider for testing and development.

    Returns a fixed response string. Never used as a production fallback.
    """

    def __init__(self, response: str = "This is a mock response."):
        self._response = response

    async def generate_response(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        context: Optional[str] = None,
        skills: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        """Return a mock response."""
        # In a real implementation, we would use the prompt, history, context, and skills.
        # For now, we return a fixed response.
        return self._response

    def get_provider_name(self) -> str:
        return "mock"

    def get_model_name(self) -> str:
        return "mock-model"

    async def health_check(self) -> bool:
        """Mock provider is always healthy for testing."""
        return True

    def get_capabilities(self) -> Dict[str, bool]:
        """Mock provider capabilities for testing.

        All capabilities are reported as False except chat_completions,
        but MockModelProvider is never used as a production fallback.
        """
        return {
            "chat_completions": True,
            "streaming": False,
            "tool_calling": False,
            "structured_output": False,
            "embeddings": False,
            "token_counting": False,
        }


class OpenAICompatibleProvider(ModelProvider):
    """Base for providers exposing the OpenAI Chat Completions wire protocol.

    Covers NVIDIA Build API (integrate.api.nvidia.com/v1) and the Gemini
    OpenAI-compatibility endpoint (generativelanguage.googleapis.com/v1beta/openai/).
    Handles system prompt + RAG context assembly, bounded retries with
    exponential backoff, and secret redaction in every raised error.
    """

    _default_base_url: str = ""
    _default_model: str = ""
    _key_prefix: Optional[str] = None  # required prefix for API keys (None: any)

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        retry_delay_seconds: int = 1,
    ):
        if not api_key:
            raise ValueError(f"{self._provider_label()} API key is required")
        if self._key_prefix and not api_key.startswith(self._key_prefix):
            raise ValueError(
                f"{self._provider_label()} API key must start with '{self._key_prefix}'"
            )

        self._api_key = api_key
        self._base_url = (base_url or self._default_base_url).rstrip("/")
        self._model_name = model_name or self._default_model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds

        if AsyncOpenAI is None:
            raise RuntimeError("openai package is required for real providers")

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=self._base_url,
            timeout=timeout_seconds,
            max_retries=0,  # We handle retries ourselves for bounded backoff
        )
        self._capabilities = self._build_capabilities()

    # --- identity ---------------------------------------------------------

    def _provider_label(self) -> str:
        return self.__class__.__name__

    def get_provider_name(self) -> str:
        raise NotImplementedError

    def get_model_name(self) -> str:
        return self._model_name

    # --- capabilities -----------------------------------------------------

    def _build_capabilities(self) -> Dict[str, bool]:
        """Override in subclasses with values verified from official docs."""
        return {
            "chat_completions": True,
            "streaming": False,
            "tool_calling": False,
            "structured_output": False,
            "embeddings": False,
            "token_counting": False,
        }

    def get_capabilities(self) -> Dict[str, bool]:
        return self._capabilities.copy()

    # --- health -----------------------------------------------------------

    async def health_check(self) -> bool:
        """Check reachability and authentication. Never raises."""
        try:
            response = await asyncio.wait_for(
                self._client.models.list(),
                timeout=min(self._timeout_seconds, 10.0),
            )
            return response is not None
        except Exception:
            return False

    # --- generation -------------------------------------------------------

    def _build_messages(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        messages = []
        system_content = self._system_prompt()
        if context:
            system_content += f"\n\nRelevant context:\n{context}"
        messages.append({"role": "system", "content": system_content})
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant", "system") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _system_prompt(self) -> str:
        return "You are a legal AI assistant. Provide accurate, well-cited responses."

    def _safe_error(self, error: Exception) -> Exception:
        """Rebuild an exception with the API key redacted from its message.

        Preserves the original exception type so callers can catch specific
        error types (e.g. ValueError for empty responses).
        """
        safe = redact(str(error), self._api_key)
        return type(error)(safe)

    async def generate_response(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        context: Optional[str] = None,
        skills: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        """Generate a response with bounded retries and backoff.

        Raises the (redacted) original exception on permanent failure or
        retry exhaustion.
        """
        messages = self._build_messages(prompt, conversation_history, context)
        request_params = {
            "model": self._model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "top_p": kwargs.get("top_p", 0.95),
        }

        last_exception: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                response: ChatCompletion = await self._client.chat.completions.create(**request_params)
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content
                raise ValueError(f"Empty response from {self.get_provider_name()}")
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Permanent errors (auth, invalid model) bubble up immediately;
                # transient ones (429, 5xx, connection, timeout) retry with backoff.
                is_permanent = any(
                    keyword in error_str
                    for keyword in ["401", "403", "404", "invalid api key", "unauthorized", "not found"]
                )
                if is_permanent or attempt >= self._max_retries:
                    raise self._safe_error(e) from e

                delay = self._retry_delay_seconds * (2 ** attempt)
                await asyncio.sleep(delay)

        raise self._safe_error(last_exception or Exception("Failed to generate response after retries"))


class NVIDIABuildModelProvider(OpenAICompatibleProvider):
    """NVIDIA Build API provider adapter.

    Uses the OpenAI-compatible API at https://integrate.api.nvidia.com/v1
    with Bearer token authentication (nvapi-... prefix).
    Verified: model ids follow 'org/model-name' (e.g. meta/llama-3.3-70b-instruct);
    chat completions, streaming and tool calling are supported on hosted NIMs.
    """

    _default_base_url = "https://integrate.api.nvidia.com/v1"
    _default_model = "meta/llama-3.3-70b-instruct"
    _key_prefix = "nvapi-"

    def get_provider_name(self) -> str:
        return "nvidia_build"

    def _provider_label(self) -> str:
        return "NVIDIA"

    def _build_capabilities(self) -> Dict[str, bool]:
        return {
            "chat_completions": True,
            "streaming": True,  # vLLM backend supports streaming
            "tool_calling": True,  # vLLM backend supports tool calling
            # Per the official meta/llama-3.3-70b-instruct model card:
            # "Structured Output: Not supported" (function calling IS supported)
            "structured_output": False,
            "embeddings": False,  # Separate embedding endpoint
            "token_counting": True,  # tokenize endpoint available
        }


class GeminiModelProvider(OpenAICompatibleProvider):
    """Google Gemini provider adapter (OpenAI-compatibility endpoint).

    Uses https://generativelanguage.googleapis.com/v1beta/openai/ with
    'Authorization: Bearer <GEMINI_API_KEY>' (per official Gemini docs).
    Model ids look like 'gemini-3.8-flash' / 'gemini-2.5-flash'.
    """

    _default_base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
    _default_model = "gemini-3.8-flash"
    _key_prefix = None  # Google API keys have no stable prefix

    def get_provider_name(self) -> str:
        return "gemini"

    def _provider_label(self) -> str:
        return "Gemini"

    def _build_capabilities(self) -> Dict[str, bool]:
        return {
            "chat_completions": True,
            "streaming": True,  # OpenAI-compat endpoint supports stream: true
            "tool_calling": True,  # Function calling supported
            "structured_output": True,  # JSON schema / response_format supported
            "embeddings": False,  # Separate text-embedding model family
            "token_counting": False,  # No official token-counting endpoint
        }


class FailoverModelProvider(ModelProvider):
    """Deterministic failover across a provider chain.

    Routing is strictly ordered by the configured chain — never random.
    A provider that fails (or exceeds its request deadline) is placed in
    cooldown for MODEL_COOLDOWN_SECONDS and traffic moves to the next
    candidate. If every candidate is in cooldown or fails, a
    ProviderUnavailableError (secret-free) is raised.
    """

    def __init__(
        self,
        providers: List[ModelProvider],
        cooldown_seconds: int = 60,
        request_deadline_seconds: int = 60,
    ):
        """Initialize the failover chain.

        Args:
            providers: Candidates in priority order.
            cooldown_seconds: How long a failed provider is skipped.
            request_deadline_seconds: Hard overall deadline per provider attempt,
                including its internal retries.
        """
        if not providers:
            raise ValueError("FailoverModelProvider requires at least one provider")
        self.providers = providers
        self.cooldown_seconds = cooldown_seconds
        self.request_deadline_seconds = request_deadline_seconds
        self._cooldown_until: Dict[str, float] = {}

    # --- chain introspection ----------------------------------------------

    def get_provider_name(self) -> str:
        return "failover:" + "+".join(p.get_provider_name() for p in self.providers)

    def get_model_name(self) -> str:
        primary = self.providers[0]
        return primary.get_model_name()

    def get_capabilities(self) -> Dict[str, bool]:
        """Intersect chain capabilities minus the streaming flag (per-turn).

        Uses key intersection with conservative AND logic: a capability is
        True only if every provider reports True; False otherwise. This keeps
        all required keys present even when providers disagree on values.
        """
        keys = None
        values: Dict[str, bool] = {}
        for p in self.providers:
            p_caps = p.get_capabilities()
            p_keys = set(p_caps.keys())
            if keys is None:
                keys = p_keys
                values = dict(p_caps)
            else:
                keys = keys.intersection(p_keys)
                for k in keys:
                    values[k] = values[k] and p_caps[k]
        caps = {k: values[k] for k in keys} if keys else {}
        caps["streaming"] = False
        return caps

    # --- cooldown management ----------------------------------------------

    def _now(self) -> float:
        return time.monotonic()

    def is_in_cooldown(self, provider_name: str) -> bool:
        until = self._cooldown_until.get(provider_name, 0.0)
        return until > self._now()

    def reset_cooldown(self, provider_name: Optional[str] = None) -> None:
        """Clear cooldowns (all providers, or one by name). Used to recover."""
        if provider_name is None:
            self._cooldown_until.clear()
        else:
            self._cooldown_until.pop(provider_name, None)

    def cooldown_remaining(self, provider_name: str) -> float:
        return max(0.0, self._cooldown_until.get(provider_name, 0.0) - self._now())

    # --- generation -------------------------------------------------------

    async def generate_response(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        context: Optional[str] = None,
        skills: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        attempted: List[str] = []
        causes: List[str] = []

        for provider in self.providers:
            name = provider.get_provider_name()
            attempted.append(name)

            if self.is_in_cooldown(name):
                causes.append(f"in cooldown for another {self.cooldown_remaining(name):.0f}s")
                continue

            try:
                result = await asyncio.wait_for(
                    provider.generate_response(
                        prompt,
                        conversation_history,
                        context=context,
                        skills=skills,
                        **kwargs
                    ),
                    timeout=self.request_deadline_seconds,
                )
                # Mark this provider as in cooldown even on success,
                # so it isn't immediately re-hit on the next turn.
                self._cooldown_until[name] = self._now() + self.cooldown_seconds
                return result
            except asyncio.TimeoutError:
                self._cooldown_until[name] = self._now() + self.cooldown_seconds
                causes.append(f"deadline exceeded ({self.request_deadline_seconds}s)")
            except Exception as e:
                self._cooldown_until[name] = self._now() + self.cooldown_seconds
                # Already redacted by the adapter base; redact defensively anyway.
                causes.append(redact(str(e), *(getattr(p, "_api_key", None) for p in self.providers)))

        raise ProviderUnavailableError(attempted, causes)

    async def health_check(self) -> bool:
        """Healthy if any chain member reports healthy (cooldowns ignored)."""
        for provider in self.providers:
            if await provider.health_check():
                return True
        return False


class ModelProviderFactory:
    """Factory to create model providers based on configuration."""

    # Defaults for provider selection; overridden by .env / environment.
    _PROVIDER_DEFAULTS: Dict[str, Dict[str, str]] = {
        "nvidia_build": {
            "key_env": "NVIDIA_API_KEY",
            "fallback_key_env": "MODEL_API_KEY",
            "base_url_env": "NVIDIA_BASE_URL",
            "model_env": "NVIDIA_MODEL_NAME",
            "base_url": NVIDIABuildModelProvider._default_base_url,
            "model": NVIDIABuildModelProvider._default_model,
        },
        "google": {
            "key_env": "GEMINI_API_KEY",
            "fallback_key_env": "MODEL_API_KEY",
            "base_url_env": "GEMINI_BASE_URL",
            "model_env": "GEMINI_MODEL_NAME",
            "base_url": GeminiModelProvider._default_base_url,
            "model": GeminiModelProvider._default_model,
        },
    }

    @staticmethod
    def _env(name: str, default: Optional[str] = None) -> Optional[str]:
        value = os.environ.get(name)
        if value:
            return value
        return default

    @staticmethod
    def _resolve_provider_config(provider_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve provider settings: kwargs > provider env vars > generic env vars > defaults."""
        defaults = ModelProviderFactory._PROVIDER_DEFAULTS.get(provider_name, {})
        generic_kwargs: Dict[str, Any] = {}

        api_key = (
            kwargs.get("api_key")
            or ModelProviderFactory._env(defaults.get("key_env", "") or "NVIDIA_API_KEY")
            or ModelProviderFactory._env(defaults.get("fallback_key_env", "") or "MODEL_API_KEY")
        )
        base_url = (
            kwargs.get("base_url")
            or ModelProviderFactory._env(defaults.get("base_url_env", "") or "MODEL_BASE_URL")
            or defaults.get("base_url")
        )
        model_name = (
            kwargs.get("model_name")
            or ModelProviderFactory._env(defaults.get("model_env", "") or "MODEL_NAME")
            or defaults.get("model")
        )
        generic_kwargs.update(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            timeout_seconds=int(kwargs.get("timeout_seconds") or ModelProviderFactory._env("MODEL_TIMEOUT_SECONDS", "30")),
            max_retries=int(kwargs.get("max_retries") or ModelProviderFactory._env("MODEL_MAX_RETRIES", "3")),
            retry_delay_seconds=int(kwargs.get("retry_delay_seconds") or ModelProviderFactory._env("MODEL_RETRY_DELAY_SECONDS", "1")),
        )
        return generic_kwargs

    @staticmethod
    def create_provider(provider_name: str, **kwargs) -> ModelProvider:
        """Create a model provider instance.

        Args:
            provider_name: Name of the provider ("mock", "nvidia_build", "google", "openai").
            **kwargs: Provider-specific configuration.

        Returns:
            ModelProvider instance.

        Raises:
            ValueError: If provider name is unknown.
        """
        if provider_name == "mock":
            return MockModelProvider(**kwargs)
        elif provider_name == "nvidia_build":
            return NVIDIABuildModelProvider(**ModelProviderFactory._resolve_provider_config("nvidia_build", kwargs))
        elif provider_name == "google":
            return GeminiModelProvider(**ModelProviderFactory._resolve_provider_config("google", kwargs))
        elif provider_name == "openai":
            raise ValueError(
                "Provider 'openai' is not implemented yet. "
                "Use 'nvidia_build' or 'google' (Gemini), or 'mock' for development."
            )
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    @staticmethod
    def create_default_provider(**kwargs) -> ModelProvider:
        """Create the provider (or failover chain) Justice AI should use.

        Selection order (deterministic, never random):
        1. If MODEL_PROVIDER_ORDER is set and non-empty, build a chain of every
           listed candidate whose API key is configured.
        2. Otherwise use the single provider named by MODEL_PROVIDER.
        3. If nothing real is configured and MODEL_PROVIDER is 'mock',
           fall back to the mock provider for development (clearly labeled;
           never presented as genuine AI output).
        """
        order_raw = ModelProviderFactory._env("MODEL_PROVIDER_ORDER") or ""
        primary = ModelProviderFactory._env("MODEL_PROVIDER", "mock") or "mock"

        if order_raw:
            names = [n.strip() for n in order_raw.split(",") if n.strip()]
            candidates: List[ModelProvider] = []
            for name in names:
                try:
                    candidates.append(ModelProviderFactory.create_provider(name, **kwargs))
                except (ValueError, RuntimeError):
                    continue  # candidate not configured; the next one decides
            if len(candidates) == 1:
                return candidates[0]
            if candidates:
                return FailoverModelProvider(
                    candidates,
                    cooldown_seconds=int(
                        ModelProviderFactory._env("MODEL_COOLDOWN_SECONDS", "60")
                    ),
                    request_deadline_seconds=int(
                        ModelProviderFactory._env("MODEL_REQUEST_DEADLINE_SECONDS", "60")
                    ),
                )
            # Order configured but nothing usable.
            if primary == "mock":
                return MockModelProvider()
            raise ValueError(
                f"MODEL_PROVIDER_ORDER='{order_raw}' has no usable provider: "
                f"configure NVIDIA_API_KEY and/or GEMINI_API_KEY."
            )

        return ModelProviderFactory.create_provider(primary, **kwargs)
