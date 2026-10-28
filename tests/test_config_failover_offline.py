"""Configuration validation tests for Justice AI's failover / provider-key envs.

Offline: no network, no real credentials. Complements test_model_provider_config.
"""

import os
import pytest
from pydantic import ValidationError


REQUIRED = {
    "SECRET_KEY": "test-secret-key-do-not-use-in-production",
    "DATABASE_URL": "postgresql://postgres@127.0.0.1:5432/justice_ai",
}


def _apply(env):
    for k, v in env.items():
        os.environ[k] = v


def _cleanup(env_keys):
    for k in env_keys:
        os.environ.pop(k, None)


def _make_settings(**overrides):
    env = {**REQUIRED, **overrides}
    _apply(env)
    from app.core.config import Settings
    try:
        return Settings()
    finally:
        _cleanup(env.keys())


_BASE_ENV_KEYS = list(REQUIRED.keys()) + [
    "MODEL_PROVIDER", "MODEL_API_KEY", "MODEL_BASE_URL",
    "NVIDIA_API_KEY", "GEMINI_API_KEY", "MODEL_PROVIDER_ORDER",
]


class TestProviderSpecificKeys:

    def test_nvidia_build_accepts_nvidia_api_key(self):
        settings = _make_settings(
            MODEL_PROVIDER="nvidia_build",
            NVIDIA_API_KEY="nvapi-test-key",
            MODEL_BASE_URL="https://integrate.api.nvidia.com/v1",
        )
        assert settings.NVIDIA_API_KEY == "nvapi-test-key"

    def test_google_accepts_gemini_api_key(self):
        settings = _make_settings(
            MODEL_PROVIDER="google",
            GEMINI_API_KEY="test-gemini-key",
            MODEL_BASE_URL="https://generativelanguage.googleapis.com/v1beta",
        )
        assert settings.GEMINI_API_KEY == "test-gemini-key"

    def test_google_without_any_key_raises(self):
        os.environ["MODEL_PROVIDER"] = "google"
        os.environ["MODEL_BASE_URL"] = "https://generativelanguage.googleapis.com/v1beta"
        os.environ.pop("MODEL_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("NVIDIA_API_KEY", None)
        try:
            from app.core.config import Settings
            with pytest.raises(ValidationError):
                Settings()
        finally:
            _cleanup(["MODEL_PROVIDER", "MODEL_BASE_URL"])

    def test_nvidia_build_without_any_key_raises(self):
        os.environ["MODEL_PROVIDER"] = "nvidia_build"
        os.environ["MODEL_BASE_URL"] = "https://integrate.api.nvidia.com/v1"
        os.environ.pop("MODEL_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("NVIDIA_API_KEY", None)
        try:
            from app.core.config import Settings
            with pytest.raises(ValidationError):
                Settings()
        finally:
            _cleanup(["MODEL_PROVIDER", "MODEL_BASE_URL"])


class TestFailoverSettings:

    def test_provider_order_default_empty(self):
        settings = _make_settings()
        assert settings.MODEL_PROVIDER_ORDER == ""

    def test_cooldown_default_60(self):
        settings = _make_settings()
        assert settings.MODEL_COOLDOWN_SECONDS == 60

    def test_request_deadline_default_60(self):
        settings = _make_settings()
        assert settings.MODEL_REQUEST_DEADLINE_SECONDS == 60

    def test_provider_order_accepts_list(self):
        settings = _make_settings(
            MODEL_PROVIDER_ORDER="nvidia_build,google",
        )
        assert settings.MODEL_PROVIDER_ORDER == "nvidia_build,google"


class TestSecretHygiene:
    """Secrets must live in env only; config never invents key material."""

    def test_no_default_api_keys(self):
        settings = _make_settings()
        assert settings.MODEL_API_KEY is None
        assert settings.NVIDIA_API_KEY is None
        assert settings.GEMINI_API_KEY is None
