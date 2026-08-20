"""Unified LLM Client and Model Factory.

Handles OpenAI and Groq API keys seamlessly, configuring base_url and supported model names.
"""

from __future__ import annotations

import logging
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)


def get_llm_client() -> AsyncOpenAI:
    """Return an AsyncOpenAI client configured for OpenAI or Groq based on api_key format."""
    settings = get_settings()
    api_key = (settings.openai_api_key or "").strip().rstrip(".")
    kwargs: dict[str, str] = {"api_key": api_key}
    if api_key.startswith("gsk_"):
        kwargs["base_url"] = "https://api.groq.com/openai/v1"
    return AsyncOpenAI(**kwargs)


def get_llm_model() -> str:
    """Return an appropriate model identifier.

    If Groq is used and model is set to an OpenAI specific name like gpt-4o-mini,
    map to a high-capacity Groq model.
    """
    settings = get_settings()
    api_key = (settings.openai_api_key or "").strip().rstrip(".")
    if api_key.startswith("gsk_") and (settings.llm_model.startswith("gpt-") or "mini" in settings.llm_model):
        return "openai/gpt-oss-120b"
    return settings.llm_model
