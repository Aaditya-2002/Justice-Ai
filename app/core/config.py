from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Justice AI"
    APP_VERSION: str = "0.1.0"

    # Database
    DATABASE_URL: str = "sqlite:///./justice_ai.db"

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
    EMBEDDING_PROVIDER: str = "mock"  # mock or sentence-transformers
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSIONS: int = 384  # default for all-MiniLM-L6-v2

    # RAG
    RAG_TOP_K: int = 5
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # File upload
    MAX_UPLOAD_SIZE: int = 10485760

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
