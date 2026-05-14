"""Configuration domain models."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LLMProvider(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"
    OLLAMA = "ollama"


class EmbeddingProvider(str, Enum):
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    OPENAI = "openai"
    CLAUDE = "claude"


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: LLMProvider = LLMProvider.CLAUDE
    model: str = "claude-sonnet-4-6"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.2
    timeout_seconds: int = 60


class EmbeddingConfig(BaseModel):
    """Embedding provider configuration."""

    provider: EmbeddingProvider = EmbeddingProvider.SENTENCE_TRANSFORMERS
    model: str = "BAAI/bge-m3"
    batch_size: int = 32


class ReviewRule(BaseModel):
    """Configuration for a single review rule."""

    id: str
    enabled: bool = True
    severity: str = "low"
    pattern: str = ""
    description: str = ""


class ReviewConfig(BaseModel):
    """Review execution configuration."""

    pre_commit_enabled: bool = True
    deep_review_enabled: bool = True
    auto_fix_enabled: bool = True
    max_file_size_kb: int = 500
    ignore_patterns: list[str] = Field(default_factory=list)
    rules: list[ReviewRule] = Field(default_factory=list)
    supported_extensions: list[str] = Field(
        default_factory=lambda: [".py", ".js", ".ts", ".tsx", ".go", ".java", ".rs"]
    )


class RAGConfig(BaseModel):
    """RAG / context awareness configuration."""

    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k_retrieval: int = 5
    hybrid_search_alpha: float = 0.7
    rerank_enabled: bool = True


class KnowledgeConfig(BaseModel):
    """Knowledge accumulation configuration."""

    auto_extract_enabled: bool = True
    graph_storage_path: str = ".codereviewmate/knowledge_graph.json"
    visualization_enabled: bool = True


class TeamConfig(BaseModel):
    """Complete team-level configuration."""

    team_name: str = "default"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    architecture_docs_path: str = "docs/architecture"
    standards_path: str = "docs/standards"
