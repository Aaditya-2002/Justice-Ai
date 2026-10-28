"""Offline tests for NVIDIA Build API provider adapter.

These tests verify the NVIDIA provider implementation WITHOUT network access
or API credentials. They mock HTTP responses to test the adapter logic.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.core.model_provider import (
    NVIDIABuildModelProvider,
    ModelProviderFactory,
    MockModelProvider,
    OpenAICompatibleProvider,
    GeminiModelProvider,
    FailoverModelProvider,
    ProviderUnavailableError,
    redact,
)


class TestNVIDIAProviderInitialization:
    """Tests for NVIDIA provider initialization and configuration."""

    def test_init_requires_api_key(self):
        """NVIDIA provider must require an API key."""
        with pytest.raises(ValueError, match="NVIDIA API key is required"):
            NVIDIABuildModelProvider(api_key="")

    def test_init_requires_nvapi_prefix(self):
        """NVIDIA provider must validate nvapi- prefix."""
        with pytest.raises(ValueError, match="must start with 'nvapi-'"):
            NVIDIABuildModelProvider(api_key="invalid-key")

    def test_init_accepts_valid_nvapi_key(self):
        """NVIDIA provider accepts valid nvapi- prefixed key."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        assert provider.get_provider_name() == "nvidia_build"
        assert provider.get_model_name() == "meta/llama-3.3-70b-instruct"

    def test_init_accepts_custom_model_name(self):
        """NVIDIA provider accepts custom model name."""
        provider = NVIDIABuildModelProvider(
            api_key="nvapi-test-key-123",
            model_name="nvidia/nemotron-3-ultra-550b-a55b"
        )
        assert provider.get_model_name() == "nvidia/nemotron-3-ultra-550b-a55b"

    def test_init_accepts_custom_base_url(self):
        """NVIDIA provider accepts custom base URL."""
        provider = NVIDIABuildModelProvider(
            api_key="nvapi-test-key-123",
            base_url="https://custom.endpoint/v1"
        )
        assert provider._base_url == "https://custom.endpoint/v1"

    def test_init_accepts_custom_timeout_and_retries(self):
        """NVIDIA provider accepts custom timeout and retry settings."""
        provider = NVIDIABuildModelProvider(
            api_key="nvapi-test-key-123",
            timeout_seconds=60,
            max_retries=5,
            retry_delay_seconds=2
        )
        assert provider._timeout_seconds == 60
        assert provider._max_retries == 5
        assert provider._retry_delay_seconds == 2

    def test_provider_name_and_model_name(self):
        """get_provider_name and get_model_name return correct values."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        assert provider.get_provider_name() == "nvidia_build"
        assert provider.get_model_name() == "meta/llama-3.3-70b-instruct"

    def test_default_base_url_is_nvidia_build_api(self):
        """Default base URL is the NVIDIA Build API endpoint."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        assert provider._base_url == "https://integrate.api.nvidia.com/v1"


class TestNVIDIAProviderCapabilities:
    """Tests for NVIDIA provider capability reporting."""

    def test_capabilities_structure(self):
        """Capabilities dict has all required keys with boolean values."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        caps = provider.get_capabilities()

        required_keys = {
            "chat_completions",
            "streaming",
            "tool_calling",
            "structured_output",
            "embeddings",
            "token_counting",
        }
        assert required_keys.issubset(caps.keys())
        for key, value in caps.items():
            assert isinstance(value, bool), f"{key} must be bool"

    def test_capabilities_values(self):
        """Capabilities match expected values for NVIDIA Build API."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        caps = provider.get_capabilities()

        assert caps["chat_completions"] is True
        assert caps["streaming"] is True
        # Per official meta/llama-3.3-70b-instruct model card:
        # Function Calling supported, Structured Output NOT supported
        assert caps["tool_calling"] is True
        assert caps["structured_output"] is False
        assert caps["embeddings"] is False
        assert caps["token_counting"] is True


class TestNVIDIAProviderHealthCheck:
    """Tests for NVIDIA provider health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_failure(self):
        """health_check returns False when API call fails (no exception)."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        provider._client.models.list = AsyncMock(side_effect=Exception("Connection failed"))
        result = await provider.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_success(self):
        """health_check returns True when API call succeeds."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        mock_response = MagicMock()
        provider._client.models.list = AsyncMock(return_value=mock_response)
        result = await provider.health_check()
        assert result is True


class TestNVIDIAProviderGenerateResponse:
    """Tests for NVIDIA provider generate_response method with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_generate_response_returns_content(self):
        """generate_response returns the content from successful API call."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "This is a test response from NVIDIA API"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.generate_response(
            prompt="What is the law?",
            conversation_history=[],
        )
        assert result == "This is a test response from NVIDIA API"

    @pytest.mark.asyncio
    async def test_generate_response_includes_context(self):
        """generate_response includes RAG context in system prompt."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Response with context"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await provider.generate_response(
            prompt="What is the law?",
            conversation_history=[],
            context="Relevant legal text from documents"
        )
        assert result == "Response with context"

        call_args = provider._client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert "Relevant legal text from documents" in messages[0]["content"]
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "What is the law?"

    @pytest.mark.asyncio
    async def test_generate_response_includes_conversation_history(self):
        """generate_response includes conversation history."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Response"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        result = await provider.generate_response(
            prompt="Follow up question",
            conversation_history=history,
        )
        assert result == "Response"

        call_args = provider._client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 4
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Previous question"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "Previous answer"

    @pytest.mark.asyncio
    async def test_generate_response_retries_on_transient_error(self):
        """generate_response retries on transient errors (429, 5xx, timeout)."""
        provider = NVIDIABuildModelProvider(
            api_key="nvapi-test-key-123",
            max_retries=2,
            retry_delay_seconds=0.01
        )
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Success after retry"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        call_count = 0
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("429 Rate limit exceeded")
            return mock_response

        provider._client.chat.completions.create = mock_create
        result = await provider.generate_response(
            prompt="Test",
            conversation_history=[],
        )
        assert result == "Success after retry"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_generate_response_no_retry_on_auth_error(self):
        """generate_response does NOT retry on 401/403 auth errors."""
        provider = NVIDIABuildModelProvider(
            api_key="nvapi-test-key-123",
            max_retries=3,
            retry_delay_seconds=0.01
        )
        call_count = 0
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("401 Unauthorized: Invalid API key")
        provider._client.chat.completions.create = mock_create

        with pytest.raises(Exception, match="401 Unauthorized"):
            await provider.generate_response(
                prompt="Test",
                conversation_history=[],
            )
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_generate_response_no_retry_on_invalid_model(self):
        """generate_response does NOT retry on 404 invalid model."""
        provider = NVIDIABuildModelProvider(
            api_key="nvapi-test-key-123",
            max_retries=3,
            retry_delay_seconds=0.01
        )
        call_count = 0
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("404 Not Found: Model not found")
        provider._client.chat.completions.create = mock_create

        with pytest.raises(Exception, match="404 Not Found"):
            await provider.generate_response(
                prompt="Test",
                conversation_history=[],
            )
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_generate_response_raises_on_empty_response(self):
        """generate_response raises on empty response content."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = ""
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        with pytest.raises(Exception, match="Empty response"):
            await provider.generate_response(
                prompt="Test",
                conversation_history=[],
            )

    @pytest.mark.asyncio
    async def test_generate_response_raises_on_no_choices(self):
        """generate_response raises when no choices in response."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        mock_response = MagicMock()
        mock_response.choices = []
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        with pytest.raises(Exception, match="Empty response"):
            await provider.generate_response(
                prompt="Test",
                conversation_history=[],
            )

    @pytest.mark.asyncio
    async def test_generate_response_passes_temperature_and_max_tokens(self):
        """generate_response passes temperature and max_tokens from kwargs."""
        provider = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Response"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)

        await provider.generate_response(
            prompt="Test",
            conversation_history=[],
            temperature=0.5,
            max_tokens=100,
            top_p=0.8,
        )
        call_args = provider._client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.5
        assert call_args.kwargs["max_tokens"] == 100
        assert call_args.kwargs["top_p"] == 0.8


class TestNVIDIAProviderFactoryRegistration:
    """Tests for NVIDIA provider factory registration."""

    def test_factory_creates_nvidia_provider(self):
        """Factory creates NVIDIABuildModelProvider for 'nvidia_build'."""
        os.environ["NVIDIA_API_KEY"] = "nvapi-test-key-123"
        os.environ["NVIDIA_BASE_URL"] = "https://integrate.api.nvidia.com/v1"
        os.environ["NVIDIA_MODEL_NAME"] = "meta/llama-3.3-70b-instruct"

        provider = ModelProviderFactory.create_provider("nvidia_build")
        assert isinstance(provider, NVIDIABuildModelProvider)
        assert provider.get_provider_name() == "nvidia_build"
        assert provider.get_model_name() == "meta/llama-3.3-70b-instruct"

        os.environ.pop("NVIDIA_API_KEY", None)
        os.environ.pop("NVIDIA_BASE_URL", None)
        os.environ.pop("NVIDIA_MODEL_NAME", None)

    def test_factory_creates_nvidia_provider_with_kwargs_override(self):
        """Factory allows kwargs to override settings."""
        os.environ["NVIDIA_API_KEY"] = "nvapi-test-key-123"
        os.environ["NVIDIA_BASE_URL"] = "https://integrate.api.nvidia.com/v1"
        os.environ["NVIDIA_MODEL_NAME"] = "meta/llama-3.3-70b-instruct"

        provider = ModelProviderFactory.create_provider(
            "nvidia_build",
            model_name="nvidia/nemotron-3-ultra-550b-a55b",
            timeout_seconds=60,
        )
        assert provider.get_model_name() == "nvidia/nemotron-3-ultra-550b-a55b"
        assert provider._timeout_seconds == 60

        os.environ.pop("NVIDIA_API_KEY", None)
        os.environ.pop("NVIDIA_BASE_URL", None)
        os.environ.pop("NVIDIA_MODEL_NAME", None)

    def test_factory_raises_for_unknown_provider(self):
        """Factory raises ValueError for unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider: unknown_xyz"):
            ModelProviderFactory.create_provider("unknown_xyz")

    def test_factory_creates_mock_provider(self):
        """Factory still creates MockModelProvider for 'mock'."""
        provider = ModelProviderFactory.create_provider("mock")
        assert isinstance(provider, MockModelProvider)


class TestNVIDIAProviderErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_generate_response_handles_connection_error(self):
        """generate_response handles connection errors as transient."""
        provider = NVIDIABuildModelProvider(
            api_key="nvapi-test-key-123",
            max_retries=1,
            retry_delay_seconds=0.01
        )
        call_count = 0
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Connection refused")
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Success"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            return mock_response
        provider._client.chat.completions.create = mock_create
        result = await provider.generate_response(
            prompt="Test",
            conversation_history=[],
        )
        assert result == "Success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_generate_response_respects_max_retries(self):
        """generate_response respects max_retries limit."""
        provider = NVIDIABuildModelProvider(
            api_key="nvapi-test-key-123",
            max_retries=2,
            retry_delay_seconds=0.01
        )
        call_count = 0
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("503 Service Unavailable")
        provider._client.chat.completions.create = mock_create

        with pytest.raises(Exception, match="503 Service Unavailable"):
            await provider.generate_response(
                prompt="Test",
                conversation_history=[],
            )
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_generate_response_exponential_backoff(self):
        """generate_response uses exponential backoff between retries."""
        import time
        provider = NVIDIABuildModelProvider(
            api_key="nvapi-test-key-123",
            max_retries=2,
            retry_delay_seconds=0.1
        )
        call_times = []
        call_count = 0
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            call_times.append(time.monotonic())
            if call_count <= 2:
                raise Exception("503 Service Unavailable")
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Success"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            return mock_response
        provider._client.chat.completions.create = mock_create
        result = await provider.generate_response(
            prompt="Test",
            conversation_history=[],
        )
        assert result == "Success"
        assert len(call_times) == 3
        assert call_times[1] - call_times[0] >= 0.09
        assert call_times[2] - call_times[1] >= 0.19


class TestOpenAICompatibleProviderBase:
    """Tests for the OpenAICompatibleProvider base class."""

    def test_cannot_instantiate_base_directly(self):
        """OpenAICompatibleProvider requires subclass defaults."""
        with pytest.raises(ValueError, match="API key is required"):
            OpenAICompatibleProvider(api_key="")


class TestGeminiModelProvider:
    """Tests for Gemini model provider."""

    def test_init_accepts_valid_key(self):
        """Gemini provider accepts API key without prefix requirement."""
        provider = GeminiModelProvider(api_key="test-key-123")
        assert provider.get_provider_name() == "gemini"
        assert provider.get_model_name() == "gemini-3.8-flash"
        assert provider._base_url == "https://generativelanguage.googleapis.com/v1beta/openai"

    def test_capabilities(self):
        """Gemini capabilities match expected values."""
        provider = GeminiModelProvider(api_key="test-key-123")
        caps = provider.get_capabilities()
        assert caps["chat_completions"] is True
        assert caps["streaming"] is True
        assert caps["tool_calling"] is True
        assert caps["structured_output"] is True
        assert caps["embeddings"] is False
        assert caps["token_counting"] is False


class TestFailoverModelProvider:
    """Tests for FailoverModelProvider."""

    def test_failover_requires_at_least_one_provider(self):
        """FailoverModelProvider raises ValueError with empty provider list."""
        with pytest.raises(ValueError, match="requires at least one provider"):
            FailoverModelProvider(providers=[])

    def test_failover_provider_name(self):
        """Failover provider name combines all chain member names."""
        mock = MockModelProvider()
        nvidia = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        failover = FailoverModelProvider(providers=[mock, nvidia])
        assert "mock" in failover.get_provider_name()
        assert "nvidia_build" in failover.get_provider_name()

    def test_failover_get_model_name(self):
        """Failover get_model_name returns primary provider's model name."""
        mock = MockModelProvider()
        nvidia = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        failover = FailoverModelProvider(providers=[mock, nvidia])
        assert failover.get_model_name() == "mock-model"

    @pytest.mark.asyncio
    async def test_failover_health_check(self):
        """Failover health_check returns True if any provider is healthy."""
        mock = MockModelProvider()
        failover = FailoverModelProvider(providers=[mock])
        result = await failover.health_check()
        assert result is True

    def test_failover_capabilities_intersect(self):
        """Failover capabilities are the intersection of chain capabilities."""
        mock = MockModelProvider()
        nvidia = NVIDIABuildModelProvider(api_key="nvapi-test-key-123")
        failover = FailoverModelProvider(providers=[mock, nvidia])
        caps = failover.get_capabilities()
        # Mock has streaming=False, so failover streaming must be False
        assert caps["streaming"] is False
        # chat_completions is True for both
        assert caps["chat_completions"] is True


class TestProviderUnavailableError:
    """Tests for ProviderUnavailableError."""

    def test_error_contains_provider_names(self):
        """Error message contains provider names and causes."""
        err = ProviderUnavailableError(
            provider_names=["nvidia_build", "gemini"],
            causes=["401 Unauthorized", "403 Forbidden"]
        )
        assert "nvidia_build" in str(err)
        assert "gemini" in str(err)
        assert "401 Unauthorized" in str(err)
        assert "403 Forbidden" in str(err)

    def test_error_redacts_secrets(self):
        """Error messages do not leak API keys."""
        # FailoverModelProvider redacts causes before constructing the error;
        # ProviderUnavailableError expects already-redacted input.
        redacted_cause = redact("Error with key nvapi-secret-12345", "nvapi-secret-12345")
        err = ProviderUnavailableError(
            provider_names=["nvidia_build"],
            causes=[redacted_cause]
        )
        msg = str(err)
        assert "nvapi-secret-12345" not in msg
        assert "[REDACTED]" in msg
