"""Anthropic Claude LLM provider."""

from __future__ import annotations

import logging
import os
from typing import AsyncIterator, Optional

from anthropic import AsyncAnthropic

from codereviewmate.core.llm.base import ChatMessage, ChatResponse, LLMProvider

logger = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    """LLM provider backed by Anthropic Claude API."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(model=model, api_key=api_key, **kwargs)
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        client_kwargs = {"api_key": self._api_key}
        if api_base:
            client_kwargs["base_url"] = api_base
        self._client = AsyncAnthropic(**client_kwargs)

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
        system_prompt = ""
        user_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                user_messages.append({"role": msg.role, "content": msg.content})

        response = await self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt if system_prompt else None,
            messages=user_messages,
        )

        return ChatResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        system_prompt = ""
        user_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                user_messages.append({"role": msg.role, "content": msg.content})

        async with self._client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt if system_prompt else None,
            messages=user_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            "Claude API does not support embeddings. Use sentence-transformers or OpenAI."
        )
