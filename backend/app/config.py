"""Application configuration.

Owner: P2
Reads all settings from environment variables via pydantic-settings.
No other file should call os.environ directly.
"""

import logging
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Central settings object.  All values are read from environment variables
    or the .env file; never from os.environ directly outside this module.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key: str = Field(..., description="OpenAI API key")
    embedding_model: str = Field(
        "text-embedding-3-small", description="OpenAI embedding model name"
    )
    llm_model: str = Field("gpt-4o-mini", description="OpenAI chat model name")

    # ── Database (Neon serverless Postgres + pgvector) ────────────────────────
    database_url: str = Field(
        ...,
        description=(
            "Async SQLAlchemy URL for Neon Postgres. "
            "Prefer the direct (unpooled) connection string to avoid PgBouncer "
            "prepared-statement conflicts. Format: "
            "postgresql+asyncpg://<user>:<password>@<host>.neon.tech/<dbname>?sslmode=require"
        ),
    )

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

    # ── Retrieval ────────────────────────────────────────────────────────────
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
