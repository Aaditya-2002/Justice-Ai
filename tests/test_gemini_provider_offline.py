"""Offline tests for the Gemini provider adapter.

Mirrors tests/test_nvidia_provider_offline.py: verifies the adapter logic
WITHOUT network access or real API credentials.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from app.core.model_provider import (
    GeminiModelProvider,
    ModelProviderFactory,
    MockModelProvider,
)


class TestGeminiProviderInitialization:

    def test_init_requires_api_key(self):
        with pytest.raises(ValueError, match="Gemini API key is required"):
            GeminiModelProvider(api_key="")

    def test_init_accepts_api_key(self):
        provider = GeminiModelProvider(api_key="test-gemini-key-123")
        assert provider.get_provider_name() == "gemini"

    def test_default_model_id(self):
        provider = GeminiModelProvider(api_key="test-gemini-key-123")
        # Model id per official Gemini OpenAI-compatibility docs
        assert provider.get_model_name() == "gemini-3.8-flash"

    def test_custom_model_name(self):
        provider = GeminiModelProvider(
            api_key="test-gemini-key-123",
            model_name="gemini-2.5-flash",
        )
        assert provider.get_model_name() == "gemini-2.5-flash"

    def test_default_base_url_is_official_openai_compat(self):
        provider = GeminiModelProvider(api_key="test-gemini-key-123")
        assert provider._base_url == (
            "https://generativelanguage.googleapis.com/v1beta/openai"
        )

    def test_custom_base_url(self):
        provider = GeminiModelProvider(
            api_key="test-gemini-key-123",
            base_url="https://custom.endpoint/v1/",
        )
        assert provider._base_url == "https://custom.endpoint/v1"

    def test_timeout_and_retries(self):
        provider = GeminiModelProvider(
            api_key="test-gemini-key-123",
            timeout_seconds=45,
            max_retries=5,
            retry_delay_seconds=2,
        )
        assert provider._timeout_seconds == 45
        assert provider._max_retries == 5
        assert provider._retry_delay_seconds == 2


class TestGeminiProviderCapabilities:

    def test_capabilities_structure_and_values(self):
        provider = GeminiModelProvider(api_key="test-gemini-key-123")
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
            assert isinstance(value, bool)
        # Verified from https://ai.google.dev/gemini-api/docs/openai
        assert caps["chat_completions"] is True
        assert caps["streaming"] is True
        assert caps["tool_calling"] is True
        assert caps["structured_output"] is True
        assert caps["embeddings"] is False
        assert caps["token_counting"] is False

    def test_capabilities_dict_is_a_copy(self):
        provider = GeminiModelProvider(api_key="test-gemini-key-123")
        caps = provider.get_capabilities()
        caps["chat_completions"] = "mutated"
        assert provider.get_capabilities()["chat_completions"] is True


class TestGeminiProviderHealthCheck:

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_failure(self):
        provider = GeminiModelProvider(api_key="test-gemini-key-123")
        provider._client.models.list = AsyncMock(side_effect=Exception("Connection failed"))
        assert await provider.health_check() is False

    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_success(self):
        provider = GeminiModelProvider(api_key="test-gemini-key-123")
        provider._client.models.list = AsyncMock(return_value=MagicMock())
        assert await provider.health_check() is True


class TestGeminiProviderGenerateResponse:

    def _provider_with_mock(self, content: str = "Gemini response"):
        provider = GeminiModelProvider(api_key="test-gemini-key-123")
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = content
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)
        return provider

    @pytest.mark.asyncio
    async def test_generate_response_returns_content(self):
        provider = self._provider_with_mock("This is a test response from Gemini")
        result = await provider.generate_response(prompt="What is the law?", conversation_history=[])
        assert result == "This is a test response from Gemini"

    @pytest.mark.asyncio
    async def test_generate_response_includes_rag_context_in_system_message(self):
        provider = self._provider_with_mock("Response with context")
        await provider.generate_response(
            prompt="What is the law?",
            conversation_history=[],
            context="Retrieved legal text",
        )
        messages = provider._client.chat.completions.create.call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert "Retrieved legal text" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_generate_response_includes_conversation_history(self):
        provider = self._provider_with_mock("Response")
        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        await provider.generate_response(prompt="Follow up", conversation_history=history)
        messages = provider._client.chat.completions.create.call_args.kwargs["messages"]
        assert len(messages) == 4
        assert messages[1]["content"] == "Previous question"
        assert messages[2]["content"] == "Previous answer"

    @pytest.mark.asyncio
    async def test_generate_response_passes_sampling_kwargs(self):
        provider = self._provider_with_mock("Response")
        await provider.generate_response(
            prompt="Test", conversation_history=[],
            temperature=0.2, max_tokens=256, top_p=0.7,
        )
        call_args = provider._client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.2
        assert call_args.kwargs["max_tokens"] == 256
        assert call_args.kwargs["top_p"] == 0.7

    @pytest.mark.asyncio
    async def test_generate_response_retries_on_transient_error(self):
        provider = GeminiModelProvider(
            api_key="test-gemini-key-123",
            max_retries=2,
            retry_delay_seconds=0.01,
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
        result = await provider.generate_response(prompt="Test", conversation_history=[])
        assert result == "Success after retry"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_generate_response_does_not_retry_on_auth_error(self):
        provider = GeminiModelProvider(
            api_key="test-gemini-key-123",
            max_retries=3,
            retry_delay_seconds=0.01,
        )
        call_count = 0
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("401 Unauthorized: Invalid API key")

        provider._client.chat.completions.create = mock_create
        with pytest.raises(Exception, match="401 Unauthorized"):
            await provider.generate_response(prompt="Test", conversation_history=[])
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_generate_response_redacts_api_key_from_error(self):
        secret = "test-gemini-secret-key-value-123"
        provider = GeminiModelProvider(api_key=secret, max_retries=0)
        async def mock_create(*args, **kwargs):
            raise Exception(f"400 Bad request: invalid key {secret}")

        provider._client.chat.completions.create = mock_create
        with pytest.raises(Exception) as exc_info:
            await provider.generate_response(prompt="Test", conversation_history=[])
        assert secret not in str(exc_info.value)
        assert "[REDACTED]" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_response_raises_on_empty_response(self):
        provider = GeminiModelProvider(api_key="test-gemini-key-123")
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = ""
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        provider._client.chat.completions.create = AsyncMock(return_value=mock_response)
        with pytest.raises(ValueError, match="Empty response"):
            await provider.generate_response(prompt="Test", conversation_history=[])


class TestGeminiProviderFactory:

    def test_factory_creates_gemini_provider(self):
        os_key = "test-gemini-key-123"
        import os
        old_provider = os.environ.get("MODEL_PROVIDER")
        old_key = os.environ.get("GEMINI_API_KEY")
        os.environ["MODEL_PROVIDER"] = "google"
        os.environ["GEMINI_API_KEY"] = os_key
        try:
            provider = ModelProviderFactory.create_default_provider()
            assert isinstance(provider, GeminiModelProvider)
            assert provider.get_provider_name() == "gemini"
        finally:
            if old_provider is None:
                os.environ.pop("MODEL_PROVIDER", None)
            else:
                os.environ["MODEL_PROVIDER"] = old_provider
            if old_key is None:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = old_key

    def test_factory_mock_still_works(self):
        assert isinstance(ModelProviderFactory.create_provider("mock"), MockModelProvider)
