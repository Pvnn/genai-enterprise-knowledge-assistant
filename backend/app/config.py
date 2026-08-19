"""Application configuration.

Owner: P2
Reads all settings from environment variables via pydantic-settings.
No other file should call os.environ directly.
"""

import logging
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Central settings object.  All values are read from environment variables
    or the .env file; never from os.environ directly outside this module.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Google Gemini / LLM ───────────────────────────────────────────────────
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    openai_api_key: str | None = Field(default=None, description="OpenAI API key (optional)")
    embedding_model: str = Field(
        "gemini-embedding-001", description="Gemini embedding model name"
    )
    llm_model: str = Field("gpt-4o-mini", description="OpenAI chat model name")

    # ── Database (Neon serverless Postgres + pgvector) ────────────────────────
    database_url: str = Field(
        ...,
        description=(
            "Async SQLAlchemy URL for Neon Postgres. "
            "Prefer the direct (unpooled) connection string to avoid PgBouncer "
            "prepared-statement conflicts. Format: "
            "postgresql+asyncpg://<user>:<password>@<host>.neon.tech/<dbname>?ssl=require"
        ),
    )

    @field_validator("database_url", mode="after")
    @classmethod
    def sanitize_database_url(cls, v: str) -> str:
        """asyncpg requires ssl instead of sslmode."""
        if "sslmode=" in v:
            v = v.replace("sslmode=", "ssl=")
        return v

    # ── Auth / JWT ────────────────────────────────────────────────────────────
    jwt_secret_key: str = Field(..., description="HMAC secret for JWT signing")
    jwt_algorithm: str = Field("HS256")
    access_token_expire_minutes: int = Field(60)

    # ── Application ───────────────────────────────────────────────────────────
    app_env: str = Field("development")
    log_level: str = Field("INFO")

    # ── Ingestion ─────────────────────────────────────────────────────────────
    ocr_device: str = Field(
        "auto",
        description=(
            "Device for Marker/OCR model. "
            "'auto' detects CUDA at runtime and falls back to CPU. "
            "Set to 'cuda' or 'cpu' to override."
        ),
    )
    aws_endpoint_url_s3: Optional[str] = Field(default=None, description="Neon Object Storage endpoint URL")
    aws_access_key_id: Optional[str] = Field(default=None, description="Neon Object Storage access key")
    aws_secret_access_key: Optional[str] = Field(default=None, description="Neon Object Storage secret key")
    aws_region: Optional[str] = Field(default=None, description="Neon Object Storage region")

    # ── Retrieval / Embeddings ────────────────────────────────────────────────
    embedding_dimension: int = Field(768, description="Embedding vector dimension")
    embed_batch_size: int = Field(
        256, description="Maximum number of chunks sent to the embedding API in a single call"
    )
    embedding_max_retries: int = Field(
        3, description="Maximum retry attempts for transient embedding failures"
    )
    dense_retrieval_top_k: int = Field(25)
    reranker_top_n: int = Field(5)
    refusal_score_threshold: float = Field(0.72)

    # ── Frontend ─────────────────────────────────────────────────────────────
    vite_api_base_url: str = Field("http://localhost:8000")


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings singleton.

    Returns:
        Settings: Application settings loaded from environment / .env.
    """
    settings = Settings()  # type: ignore[call-arg]
    logger.info("Settings loaded (env=%s)", settings.app_env)
    return settings
