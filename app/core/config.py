from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import ConfigDict
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

    # Model Provider
    MODEL_PROVIDER: str = "mock"
    MODEL_NAME: str = "mock-model"
    # For future providers, we can add:
    # MODEL_BASE_URL: Optional[str] = None
    # MODEL_API_KEY: Optional[str] = None
    # MODEL_TIMEOUT_SECONDS: int = 30

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


settings = Settings()
