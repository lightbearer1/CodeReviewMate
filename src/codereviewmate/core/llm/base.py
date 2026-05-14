"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, model: str, api_key: Optional[str] = None, **kwargs):
        self.model = model
        self.api_key = api_key

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ) -> ChatResponse:
        """Send a chat completion request."""
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream a chat completion response."""
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for the given texts."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    def format_messages(self, system_prompt: str, user_message: str) -> list[ChatMessage]:
        """Convenience method to build standard (system, user) message list."""
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=user_message))
        return messages
