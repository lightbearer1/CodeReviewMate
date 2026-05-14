"""Ollama local LLM provider."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Optional

import httpx

from codereviewmate.core.llm.base import ChatMessage, ChatResponse, LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """LLM provider backed by local Ollama instance."""

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        api_key: Optional[str] = None,
        api_base: str = "http://localhost:11434",
        **kwargs,
    ):
        super().__init__(model=model, api_key=api_key, **kwargs)
        self.api_base = api_base
        self._client = httpx.AsyncClient(base_url=api_base, timeout=120.0)

    @property
    def model_name(self) -> str:
        return f"ollama/{self.model}"

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ) -> ChatResponse:
        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]

        resp = await self._client.post(
            "/api/chat",
            json={
                "model": self.model,
                "messages": ollama_messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()

        return ChatResponse(
            content=data["message"]["content"],
            model=self.model,
            usage={
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            },
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]

        async with self._client.stream(
            "POST",
            "/api/chat",
            json={
                "model": self.model,
                "messages": ollama_messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            resp = await self._client.post(
                "/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings.append(data["embedding"])
        return embeddings
