"""Configuration validation tests for Justice AI's model provider settings.

These tests verify that the Settings class correctly validates provider
configuration. They run without network access or API credentials.
"""

import os
import pytest
from pydantic import ValidationError


def _make_settings(**overrides):
    """Create a Settings instance with given env overrides.

    Sets required env vars (SECRET_KEY, DATABASE_URL) plus overrides,
    then instantiates Settings directly without module reload.
    """
    env = {
        "SECRET_KEY": "test-secret-key-do-not-use-in-production",
        "DATABASE_URL": "postgresql://postgres@127.0.0.1:5432/justice_ai",
        **overrides,
    }
    for k, v in env.items():
        os.environ[k] = v
    from app.core.config import Settings
    return Settings()


class TestConfigProviderSelection:
    """Tests for MODEL_PROVIDER validation."""

    def test_default_provider_is_mock(self):
        """Settings defaults to 'mock' provider when no env var is set."""
        os.environ.pop("MODEL_PROVIDER", None)
        from app.core.config import Settings
        settings = Settings()
        assert settings.MODEL_PROVIDER == "mock"
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("DATABASE_URL", None)

    def test_known_providers_accepted(self):
        """All known provider names are accepted."""
        for provider in ["mock", "nvidia_build", "openai", "google"]:
            if provider == "nvidia_build":
                settings = _make_settings(
                    MODEL_PROVIDER=provider,
                    MODEL_API_KEY="test-key",
                    MODEL_BASE_URL="https://integrate.api.nvidia.com/v1",
                )
            elif provider == "openai":
                settings = _make_settings(
                    MODEL_PROVIDER=provider,
                    MODEL_API_KEY="test-key",
                    MODEL_BASE_URL="https://api.openai.com/v1",
                )
            elif provider == "google":
                settings = _make_settings(
                    MODEL_PROVIDER=provider,
                    MODEL_API_KEY="test-key",
                    MODEL_BASE_URL="https://generativelanguage.googleapis.com/v1beta",
                )
            else:
                settings = _make_settings(MODEL_PROVIDER=provider)
            assert settings.MODEL_PROVIDER == provider
            os.environ.pop("SECRET_KEY", None)
            os.environ.pop("DATABASE_URL", None)

    def test_unknown_provider_raises_error(self):
        """Unknown provider name raises ValidationError."""
        os.environ["MODEL_PROVIDER"] = "invalid_provider"
        from app.core.config import Settings
        with pytest.raises(ValidationError, match="not a known provider"):
            Settings()
        # Clean up
        os.environ.pop("MODEL_PROVIDER", None)
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("DATABASE_URL", None)


class TestConfigApiKeyRequirement:
    """Tests for MODEL_API_KEY validation when real provider is selected."""

    def test_mock_provider_works_without_api_key(self):
        """Mock provider does not require MODEL_API_KEY."""
        os.environ.pop("MODEL_API_KEY", None)
        settings = _make_settings(MODEL_PROVIDER="mock")
        assert settings.MODEL_API_KEY is None
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("DATABASE_URL", None)

    def test_nvidia_build_requires_api_key(self):
        """NVIDIA Build API provider requires MODEL_API_KEY."""
        # Import before mutating env: config.py instantiates Settings at module
        # import time, which would fail outside the pytest.raises block.
        from app.core.config import Settings
        os.environ["MODEL_PROVIDER"] = "nvidia_build"
        os.environ.pop("MODEL_API_KEY", None)
        with pytest.raises(ValidationError, match="API key is required"):
            Settings()
        # Clean up
        os.environ.pop("MODEL_PROVIDER", None)
        os.environ.pop("MODEL_API_KEY", None)
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("DATABASE_URL", None)

    def test_openai_requires_api_key(self):
        """OpenAI provider requires MODEL_API_KEY."""
        os.environ["MODEL_PROVIDER"] = "openai"
        os.environ.pop("MODEL_API_KEY", None)
        from app.core.config import Settings
        with pytest.raises(ValidationError, match="MODEL_API_KEY is required"):
            Settings()
        # Clean up
        os.environ.pop("MODEL_PROVIDER", None)
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("DATABASE_URL", None)


class TestConfigBaseUrlRequirement:
    """Tests for MODEL_BASE_URL validation when real provider is selected."""

    def test_nvidia_build_requires_base_url(self):
        """NVIDIA Build API provider requires MODEL_BASE_URL."""
        os.environ["MODEL_PROVIDER"] = "nvidia_build"
        os.environ["MODEL_API_KEY"] = "test-key"
        os.environ.pop("MODEL_BASE_URL", None)
        from app.core.config import Settings
        with pytest.raises(ValidationError, match="MODEL_BASE_URL is required"):
            Settings()
        # Clean up
        os.environ.pop("MODEL_PROVIDER", None)
        os.environ.pop("MODEL_API_KEY", None)
        os.environ.pop("MODEL_BASE_URL", None)
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("DATABASE_URL", None)


class TestConfigDefaults:
    """Tests for default configuration values."""

    def test_defaults_are_safe_for_development(self):
        """Default settings work without any provider credentials."""
        os.environ.pop("MODEL_PROVIDER", None)
        os.environ.pop("MODEL_API_KEY", None)
        os.environ.pop("MODEL_BASE_URL", None)
        settings = _make_settings()
        assert settings.MODEL_PROVIDER == "mock"
        assert settings.MODEL_NAME == "mock-model"
        assert settings.MODEL_TIMEOUT_SECONDS == 30
        assert settings.MODEL_MAX_RETRIES == 3
        assert settings.MODEL_RETRY_DELAY_SECONDS == 1
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("DATABASE_URL", None)