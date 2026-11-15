from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Claude
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5-5"
    # Effort controls how hard Claude thinks. "low" keeps chat fast and cheap.
    claude_effort: str = "low"
    max_answer_tokens: int = 16000

    # Retrieval
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Where the embedding model is downloaded/cached (None = fastembed default).
    embedding_cache_dir: str | None = None
    chroma_dir: str = "./data/chroma"
    collection_name: str = "documents"
    chunk_size: int = 1000
    chunk_overlap: int = 150
    top_k: int = 5

    # Uploads
    max_upload_mb: int = 20

    # Comma-separated list of origins allowed to call the API (the Next.js app).
    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
