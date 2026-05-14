"""LLM provider factory."""

from __future__ import annotations

import logging
from typing import Optional

from codereviewmate.core.config.manager import get_config
from codereviewmate.core.llm.base import LLMProvider
from codereviewmate.core.llm.claude import ClaudeProvider
from codereviewmate.core.llm.ollama import OllamaProvider
from codereviewmate.core.llm.openai_adapter import OpenAIProvider
from codereviewmate.core.models.config import LLMProvider as LLMProviderEnum

logger = logging.getLogger(__name__)


def create_llm_provider(
    provider: Optional[LLMProviderEnum] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
) -> LLMProvider:
    """Create an LLM provider instance from configuration or explicit parameters."""
    config = get_config()
    provider = provider or config.llm.provider
    model = model or config.llm.model
    api_key = api_key or config.llm.api_key
    api_base = api_base or config.llm.api_base

    logger.info("Creating LLM provider: %s (model=%s)", provider.value, model)

    if provider == LLMProviderEnum.CLAUDE:
        return ClaudeProvider(model=model, api_key=api_key, api_base=api_base)

    if provider == LLMProviderEnum.OPENAI:
        return OpenAIProvider(model=model, api_key=api_key, api_base=api_base)

    if provider == LLMProviderEnum.OLLAMA:
        return OllamaProvider(model=model, api_base=api_base or "http://localhost:11434")

    raise ValueError(f"Unknown LLM provider: {provider}")
