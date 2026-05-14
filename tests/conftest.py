"""Shared test fixtures and configuration."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_config_yaml() -> str:
    return """
team_name: test-team
llm:
  provider: claude
  model: claude-sonnet-4-6
  max_tokens: 4096
review:
  pre_commit_enabled: true
  deep_review_enabled: true
  auto_fix_enabled: false
knowledge:
  graph_storage_path: /tmp/test_knowledge_graph.json
"""


@pytest.fixture
def temp_team_config(tmp_path: Path, sample_config_yaml: str) -> Path:
    """Create a temporary team config file."""
    config_path = tmp_path / ".codereviewmate.yaml"
    config_path.write_text(sample_config_yaml, encoding="utf-8")
    return config_path


@pytest.fixture
def sample_diff() -> str:
    return """diff --git a/src/app.py b/src/app.py
index 1234567..abcdefg 100644
--- a/src/app.py
+++ b/src/app.py
@@ -10,6 +10,8 @@ def process_data(items):
     for item in items:
         if item.status == 'active':
             result = transform(item)
+            print(f"Processing {item.id}")  # debug print
+            password = "hardcoded123"
             results.append(result)
     return results
"""
