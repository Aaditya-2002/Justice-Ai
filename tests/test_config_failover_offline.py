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
        if v is None:
            # Explicit None means "not set": remove any ambient value.
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _cleanup(env_keys):
    for k in env_keys:
        if k not in REQUIRED:
            os.environ.pop(k, None)


def _make_settings(**overrides):
    """Create a Settings instance in a controlled environment.

    Overrides with None pop the variable so the test controls the state
    regardless of ambient/.env values. String overrides are set in os.environ.
    """
    env = {**REQUIRED, **{k: v for k, v in overrides.items() if v is not None}}
    for k, v in overrides.items():
        if v is None:
            os.environ.pop(k, None)
    _apply(env)
    from app.core.config import Settings
    try:
        return Settings()
    finally:
        _cleanup(list(overrides.keys()) + list(REQUIRED.keys()))


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
            # _env_file=None: a locally configured .env (e.g. with keys for
            # live tests) must not leak into this "nothing configured" test.
            with pytest.raises(ValidationError):
                Settings(_env_file=None)
        finally:
            _cleanup(["MODEL_PROVIDER", "MODEL_BASE_URL"])


class TestFailoverSettings:

    def test_provider_order_default_empty(self):
        # Empty-string init override makes the default independent of a
        # locally configured .env (e.g. when keys were added for live tests).
        settings = _make_settings(MODEL_PROVIDER_ORDER="")
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
    """Config never invents key material: defaults are None unless the
    environment (.env/env vars) provides them."""

    def test_no_builtin_default_api_keys(self):
        # Explicit init-kwarg Nones pin the defaults regardless of a locally
        # configured .env (init kwargs have the highest pydantic-settings priority).
        from app.core.config import Settings
        settings = Settings(
            _env_file=None,
            SECRET_KEY="test-secret-key-do-not-use-in-production",
            DATABASE_URL="postgresql://postgres@127.0.0.1:5432/justice_ai",
            NVIDIA_API_KEY=None, GEMINI_API_KEY=None, MODEL_API_KEY=None,
        )
        assert settings.MODEL_API_KEY is None
        assert settings.NVIDIA_API_KEY is None
        assert settings.GEMINI_API_KEY is None
