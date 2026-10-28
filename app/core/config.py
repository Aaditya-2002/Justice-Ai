from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import ConfigDict, field_validator
import os

# Get the directory of this file to locate .env
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Justice AI"
    APP_VERSION: str = "0.1.0"

    # Database
    DATABASE_URL: str = "postgresql://postgres@127.0.0.1:5432/justice_ai"

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Provider API keys (provider-specific names; MODEL_API_KEY stays generic)
    # Defined before MODEL_* so validators can see them via info.data.
    NVIDIA_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # Model Provider
    MODEL_PROVIDER: str = "mock"
    MODEL_NAME: str = "mock-model"  # default model for the selected provider
    MODEL_BASE_URL: Optional[str] = None
    MODEL_API_KEY: Optional[str] = None
    MODEL_TIMEOUT_SECONDS: int = 30
    MODEL_MAX_RETRIES: int = 3
    MODEL_RETRY_DELAY_SECONDS: int = 1

    # Provider failover (deterministic order, comma-separated provider names)
    MODEL_PROVIDER_ORDER: str = ""  # e.g. "nvidia_build,google"
    MODEL_COOLDOWN_SECONDS: int = 60  # skip a failed provider this long
    MODEL_REQUEST_DEADLINE_SECONDS: int = 60  # hard deadline per provider attempt

    # Embedding
    EMBEDDING_PROVIDER: str = "sentence-transformers"  # mock or sentence-transformers
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSIONS: int = 384  # default for all-MiniLM-L6-v2

    # RAG
    RAG_TOP_K: int = 5
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # File upload
    MAX_UPLOAD_SIZE: int = 10485760

    # Tenant
    DEFAULT_TENANT_ID: str = "default"

    model_config = ConfigDict(
        env_file = os.path.join(BASE_DIR, ".env"),
        case_sensitive = True
    )

    @field_validator("MODEL_PROVIDER")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate that MODEL_PROVIDER is a known provider name."""
        allowed = {"mock", "nvidia_build", "openai", "google"}
        if v not in allowed:
            raise ValueError(
                f"MODEL_PROVIDER='{v}' is not a known provider. "
                f"Allowed values: {sorted(allowed)}"
            )
        return v

    @field_validator("MODEL_API_KEY")
    @classmethod
    def validate_api_key_when_not_mock(cls, v: Optional[str], info) -> Optional[str]:
        """Require an API key when a real provider is selected.

        Accepts either the generic MODEL_API_KEY or the provider-specific
        NVIDIA_API_KEY / GEMINI_API_KEY.
        """
        provider = info.data.get("MODEL_PROVIDER", "mock")
        if provider in ("nvidia_build", "google"):
            per_provider_key = {
                "nvidia_build": info.data.get("NVIDIA_API_KEY"),
                "google": info.data.get("GEMINI_API_KEY"),
            }.get(provider)
            if not v and not per_provider_key:
                raise ValueError(
                    f"An API key is required when MODEL_PROVIDER='{provider}': "
                    f"set MODEL_API_KEY, NVIDIA_API_KEY, or GEMINI_API_KEY."
                )
        elif provider != "mock" and not v:
            raise ValueError(
                f"MODEL_API_KEY is required when MODEL_PROVIDER='{provider}'. "
                f"Set it in your .env file or environment."
            )
        return v

    @field_validator("MODEL_BASE_URL")
    @classmethod
    def validate_base_url_when_not_mock(cls, v: Optional[str], info) -> Optional[str]:
        """Require base URL when a real provider is selected."""
        provider = info.data.get("MODEL_PROVIDER", "mock")
        if provider != "mock" and not v:
            raise ValueError(
                f"MODEL_BASE_URL is required when MODEL_PROVIDER='{provider}'. "
                f"Set it in your .env file or environment."
            )
        return v


settings = Settings()
