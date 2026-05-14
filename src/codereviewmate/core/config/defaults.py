"""Built-in default configuration values."""

from codereviewmate.core.models.config import (
    EmbeddingConfig,
    KnowledgeConfig,
    LLMConfig,
    RAGConfig,
    ReviewConfig,
    TeamConfig,
)

DEFAULT_TEAM_CONFIG = TeamConfig(
    team_name="default",
    llm=LLMConfig(),
    embedding=EmbeddingConfig(),
    review=ReviewConfig(),
    rag=RAGConfig(),
    knowledge=KnowledgeConfig(),
)

DEFAULT_CONFIG_YAML = """
team_name: default

llm:
  provider: claude
  model: claude-sonnet-4-6
  max_tokens: 4096
  temperature: 0.2
  timeout_seconds: 60

embedding:
  provider: sentence_transformers
  model: BAAI/bge-m3
  batch_size: 32

review:
  pre_commit_enabled: true
  deep_review_enabled: true
  auto_fix_enabled: true
  max_file_size_kb: 500
  ignore_patterns:
    - "*.lock"
    - "package-lock.json"
    - "*.min.js"
    - "*.generated.*"
  supported_extensions:
    - .py
    - .js
    - .ts
    - .tsx
    - .go
    - .java
    - .rs
  rules:
    - id: no-hardcoded-secrets
      enabled: true
      severity: critical
      pattern: "(password|secret|api_key|token)\\s*=\\s*['\\\"][^'\\\"]+['\\\"]"
      description: "Detect hardcoded secrets in source code"
    - id: no-print-debug
      enabled: true
      severity: low
      pattern: "print\\("
      description: "Flag print() statements that may be leftover debug code"
    - id: no-console-log
      enabled: true
      severity: low
      pattern: "console\\.(log|debug|info)"
      description: "Flag console.log() in production code"
    - id: sql-injection-risk
      enabled: true
      severity: high
      pattern: "(execute|cursor\\.execute)\\(.*f['\\\"]"
      description: "Detect potential SQL injection via f-strings"
    - id: broad-exception-catch
      enabled: true
      severity: medium
      pattern: "except\\s*:"
      description: "Flag bare except clauses"

rag:
  chunk_size: 512
  chunk_overlap: 64
  top_k_retrieval: 5
  hybrid_search_alpha: 0.7
  rerank_enabled: true

knowledge:
  auto_extract_enabled: true
  graph_storage_path: .codereviewmate/knowledge_graph.json
  visualization_enabled: true

architecture_docs_path: docs/architecture
standards_path: docs/standards
"""
