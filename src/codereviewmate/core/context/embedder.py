"""Embedding model abstraction supporting local and API-based embeddings.

Embedder instances are lazy-loaded — the model is only downloaded/loaded
on the first call to embed(), not at import time.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from codereviewmate.core.models.config import EmbeddingProvider as EmbeddingProviderEnum

logger = logging.getLogger(__name__)


class Embedder(ABC):
    """Abstract embedding model interface."""

    @abstractmethod
    def embed(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    @abstractmethod
    async def embed_async(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings asynchronously."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension."""
        ...

    @property
    @abstractmethod
    def loaded(self) -> bool:
        """Whether the underlying model is loaded."""
        ...


class SentenceTransformerEmbedder(Embedder):
    """Local embedding via sentence-transformers (BGE-M3 by default).

    The model is loaded lazily on first use to avoid download delays
    at import time and to allow offline commands to work.
    """

    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = "cpu"):
        self._model_name = model_name
        self._device = device
        self._model = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s on %s", self._model_name, self._device)
        self._model = SentenceTransformer(self._model_name, device=self._device)

    @property
    def dimension(self) -> int:
        self._ensure_loaded()
        return self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        self._ensure_loaded()
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 100,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    async def embed_async(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        import asyncio

        self._ensure_loaded()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.embed(texts, batch_size))


class OpenAIEmbedder(Embedder):
    """API-based embedding via OpenAI."""

    def __init__(self, model: str = "text-embedding-3-small", api_key: Optional[str] = None):
        self._model_name = model
        self._api_key = api_key
        self._client = None

    @property
    def loaded(self) -> bool:
        return True  # API-based, always ready

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        import os

        from openai import OpenAI

        self._client = OpenAI(api_key=self._api_key or os.environ.get("OPENAI_API_KEY"))

    @property
    def dimension(self) -> int:
        return 1536

    def embed(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        self._ensure_client()
        result: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = self._client.embeddings.create(model=self._model_name, input=batch)
            result.extend([r.embedding for r in resp.data])
        return result

    async def embed_async(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        import asyncio

        self._ensure_client()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.embed(texts, batch_size))


_embedder: Optional[Embedder] = None


def get_embedder() -> Embedder:
    """Get the global embedder singleton based on config.

    The embedder is created lazily — model download happens on first embed() call.
    """
    global _embedder
    if _embedder is None:
        from codereviewmate.core.config.manager import get_config

        config = get_config()
        provider = config.embedding.provider
        model = config.embedding.model

        if provider == EmbeddingProviderEnum.SENTENCE_TRANSFORMERS:
            _embedder = SentenceTransformerEmbedder(model_name=model)
        elif provider == EmbeddingProviderEnum.OPENAI:
            _embedder = OpenAIEmbedder(model=model)
        else:
            raise ValueError(f"Unknown embedding provider: {provider}")

        logger.info(
            "Embedder created (lazy): provider=%s, model=%s",
            provider.value,
            model,
        )

    return _embedder
