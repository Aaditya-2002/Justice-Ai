"""Provider contract tests for Justice AI's ModelProvider interface.

These tests run WITHOUT network access or API credentials. They verify
that any provider adapter implements the ModelProvider contract correctly.
"""

import pytest
from typing import Dict, Any
from app.core.model_provider import (
    ModelProvider,
    MockModelProvider,
    ModelProviderFactory,
)


class TestModelProviderContract:
    """Contract tests that any ModelProvider implementation must pass."""

    def test_implements_all_abstract_methods(self):
        """PT-01: Adapter implements all ModelProvider abstract methods."""
        provider = MockModelProvider()
        # Should not raise NotImplementedError at instantiation
        assert provider is not None

    def test_get_provider_name_returns_string(self):
        """PT-02: get_provider_name() returns a non-empty string."""
        provider = MockModelProvider()
        name = provider.get_provider_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_get_model_name_returns_string(self):
        """PT-03: get_model_name() returns a non-empty string."""
        provider = MockModelProvider()
        name = provider.get_model_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_get_capabilities_returns_dict_with_required_keys(self):
        """PT-04: get_capabilities() returns dict with all required keys."""
        provider = MockModelProvider()
        caps = provider.get_capabilities()
        assert isinstance(caps, dict)
        required_keys = {
            "chat_completions",
            "streaming",
            "tool_calling",
            "structured_output",
            "embeddings",
            "token_counting",
        }
        assert required_keys.issubset(caps.keys()), \
            f"Missing capability keys: {required_keys - caps.keys()}"
        # All values must be booleans
        for key, value in caps.items():
            assert isinstance(value, bool), \
                f"Capability {key} must be bool, got {type(value)}"

    def test_health_check_returns_bool(self):
        """PT-05: health_check() returns True or False (no exception)."""
        provider = MockModelProvider()
        import asyncio
        result = asyncio.run(provider.health_check())
        assert isinstance(result, bool)

    def test_generate_response_returns_string(self):
        """PT-07: generate_response() returns non-empty string."""
        provider = MockModelProvider()
        import asyncio
        result = asyncio.run(provider.generate_response(
            prompt="Hello",
            conversation_history=[],
        ))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_response_handles_empty_context(self):
        """PT-08: generate_response() handles empty context without error."""
        provider = MockModelProvider()
        import asyncio
        result = asyncio.run(provider.generate_response(
            prompt="Hello",
            conversation_history=[],
            context=None,
        ))
        assert isinstance(result, str)
        assert len(result) > 0


class TestModelProviderFactory:
    """Factory registration tests."""

    def test_create_provider_mock_returns_mock_model_provider(self):
        """PT-09: create_provider('mock') returns MockModelProvider instance."""
        provider = ModelProviderFactory.create_provider("mock")
        assert isinstance(provider, MockModelProvider)

    def test_create_provider_unknown_raises_valueerror(self):
        """PT-10: create_provider('unknown') raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            ModelProviderFactory.create_provider("unknown_provider")


class TestMockModelProviderIsNotProductionFallback:
    """MockModelProvider must never be used as a production fallback."""

    def test_mock_provider_returns_fixed_response(self):
        """MockModelProvider returns a hardcoded string, not real model output."""
        provider = MockModelProvider(response="fixed mock response")
        import asyncio
        result = asyncio.run(provider.generate_response(
            prompt="Any prompt",
            conversation_history=[],
        ))
        assert result == "fixed mock response"

    def test_mock_provider_capabilities_are_explicit(self):
        """MockModelProvider explicitly declares which capabilities it lacks."""
        provider = MockModelProvider()
        caps = provider.get_capabilities()
        # Mock provider does NOT support streaming, tool calling, etc.
        assert caps["streaming"] is False
        assert caps["tool_calling"] is False
        assert caps["structured_output"] is False
        assert caps["embeddings"] is False
        assert caps["token_counting"] is False