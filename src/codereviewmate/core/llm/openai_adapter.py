"""OpenAI LLM provider (GPT-4, GPT-4o, etc.)."""

from __future__ import annotations

import logging
import os
from typing import AsyncIterator, Optional

from openai import AsyncOpenAI

from codereviewmate.core.llm.base import ChatMessage, ChatResponse, LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """LLM provider backed by OpenAI API."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(model=model, api_key=api_key, **kwargs)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        client_kwargs = {"api_key": self._api_key}
        if api_base:
            client_kwargs["base_url"] = api_base
        self._client = AsyncOpenAI(**client_kwargs)

    @property
    def model_name(self) -> str:
        return self.model

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ) -> ChatResponse:
        openai_messages = [{"role": m.role, "content": m.content} for m in messages]

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return ChatResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        openai_messages = [{"role": m.role, "content": m.content} for m in messages]

        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [r.embedding for r in response.data]
