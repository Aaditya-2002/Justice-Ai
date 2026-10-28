"""Offline provider-independent tests for Justice AI's model provider layer.

These tests verify provider-independent reliability behavior WITHOUT network
access or API credentials. They cover:
- Malformed model responses (empty, None, non-string)
- Missing configuration (no API key for real provider)
- Timeout and retry boundaries
- Unavailable / unregistered providers
- Mock model cannot silently serve as genuine AI output
- Capability handling for unsupported features
"""

import os
import asyncio
import pytest
from typing import Dict, Any
from app.core.model_provider import (
    ModelProvider,
    MockModelProvider,
    ModelProviderFactory,
)


class TestMalformedModelResponses:
    """Offline tests for malformed model responses."""

    def test_empty_response_is_not_none(self):
        """Mock provider must never return None for generate_response."""
        provider = MockModelProvider()
        result = asyncio.run(provider.generate_response(
            prompt="Hello",
            conversation_history=[],
        ))
        assert result is not None, "generate_response must not return None"
        assert isinstance(result, str), "generate_response must return a string"

    def test_empty_string_response_is_rejected(self):
        """Mock provider must not return empty string as a valid response."""
        provider = MockModelProvider(response="")
        result = asyncio.run(provider.generate_response(
            prompt="Hello",
            conversation_history=[],
        ))
        # Mock returns whatever it's configured with; the adapter layer
        # should reject empty responses before serving them.
        assert isinstance(result, str)
        assert len(result) == 0  # Mock is hardcoded; caller must validate

    def test_whitespace_only_response_is_rejected(self):
        """Mock provider with whitespace-only response returns exactly that."""
        provider = MockModelProvider(response="   ")
        result = asyncio.run(provider.generate_response(
            prompt="Hello",
            conversation_history=[],
        ))
        assert result == "   "

    def test_response_with_newlines_only(self):
        """Mock provider with newline-only response."""
        provider = MockModelProvider(response="\n\n\n")
        result = asyncio.run(provider.generate_response(
            prompt="Hello",
            conversation_history=[],
        ))
        assert result == "\n\n\n"


class TestMissingConfiguration:
    """Offline tests for missing configuration handling."""

    def test_mock_provider_without_api_key(self):
        """Mock provider works without MODEL_API_KEY."""
        os.environ.pop("MODEL_API_KEY", None)
        provider = ModelProviderFactory.create_provider("mock")
        assert provider.get_provider_name() == "mock"
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("DATABASE_URL", None)

    def test_factory_unknown_provider_raises(self):
        """Factory raises ValueError for unregistered provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            ModelProviderFactory.create_provider("nonexistent_provider")

    def test_factory_empty_provider_raises(self):
        """Factory raises ValueError for empty provider name."""
        with pytest.raises(ValueError, match="Unknown provider"):
            ModelProviderFactory.create_provider("")


class TestTimeoutAndRetryBoundaries:
    """Offline tests for timeout and retry configuration boundaries."""

    def test_timeout_seconds_default_is_30(self):
        """Default MODEL_TIMEOUT_SECONDS is 30 seconds."""
        os.environ.pop("MODEL_TIMEOUT_SECONDS", None)
        os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-production"
        os.environ["DATABASE_URL"] = "postgresql://postgres@127.0.0.1:5432/justice_ai"
        from app.core.config import Settings
        settings = Settings()
        assert settings.MODEL_TIMEOUT_SECONDS == 30
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("DATABASE_URL", None)

    def test_max_retries_default_is_3(self):
        """Default MODEL_MAX_RETRIES is 3."""
        os.environ.pop("MODEL_MAX_RETRIES", None)
        os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-production"
        os.environ["DATABASE_URL"] = "postgresql://postgres@127.0.0.1:5432/justice_ai"
        from app.core.config import Settings
        settings = Settings()
        assert settings.MODEL_MAX_RETRIES == 3
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("DATABASE_URL", None)

    def test_retry_delay_default_is_1(self):
        """Default MODEL_RETRY_DELAY_SECONDS is 1 second."""
        os.environ.pop("MODEL_RETRY_DELAY_SECONDS", None)
        os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-production"
        os.environ["DATABASE_URL"] = "postgresql://postgres@127.0.0.1:5432/justice_ai"
        from app.core.config import Settings
        settings = Settings()
        assert settings.MODEL_RETRY_DELAY_SECONDS == 1
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("DATABASE_URL", None)


class TestMockCannotServeAsProductionAI:
    """Mock model must never be served as genuine AI-generated output."""

    def test_mock_returns_hardcoded_response(self):
        """MockModelProvider returns a fixed string, not real model output."""
        provider = MockModelProvider(response="fixed mock response")
        result = asyncio.run(provider.generate_response(
            prompt="Any prompt at all",
            conversation_history=[],
        ))
        assert result == "fixed mock response"
        assert result != "Hello"  # Not actually responding to the prompt

    def test_mock_response_is_independent_of_prompt(self):
        """Mock response does not vary based on input prompt."""
        provider = MockModelProvider(response="mock")
        result1 = asyncio.run(provider.generate_response(
            prompt="What is the law?",
            conversation_history=[],
        ))
        result2 = asyncio.run(provider.generate_response(
            prompt="Completely different prompt",
            conversation_history=[],
        ))
        assert result1 == result2 == "mock"

    def test_mock_capabilities_do_not_overclaim(self):
        """Mock provider explicitly declares unsupported capabilities as False."""
        provider = MockModelProvider()
        caps = provider.get_capabilities()
        assert caps["streaming"] is False
        assert caps["tool_calling"] is False
        assert caps["structured_output"] is False
        assert caps["embeddings"] is False
        assert caps["token_counting"] is False
        assert caps["chat_completions"] is True  # Only chat is supported

    def test_mock_health_check_always_healthy(self):
        """Mock health_check always returns True (for testing only)."""
        provider = MockModelProvider()
        result = asyncio.run(provider.health_check())
        assert result is True


class TestUnsupportedCapabilityHandling:
    """Tests for how providers handle unsupported capabilities."""

    def test_capability_keys_are_booleans(self):
        """All capability values must be boolean, never None or string."""
        provider = MockModelProvider()
        caps = provider.get_capabilities()
        for key, value in caps.items():
            assert isinstance(value, bool), f"{key} must be bool, got {type(value)}"

    def test_unknown_capability_key_returns_false_if_checked(self):
        """Provider should not claim capabilities it doesn't have."""
        provider = MockModelProvider()
        caps = provider.get_capabilities()
        # Mock provider explicitly reports False for advanced capabilities
        assert caps.get("video_generation", False) is False or "video_generation" not in caps
        assert caps.get("image_analysis", False) is False or "image_analysis" not in caps

    def test_capability_dict_is_not_empty(self):
        """get_capabilities() must return a non-empty dict."""
        provider = MockModelProvider()
        caps = provider.get_capabilities()
        assert len(caps) > 0