"""Configuration manager with layered resolution.

Resolution order (later overrides earlier):
  1. Built-in defaults (defaults.py)
  2. Team config file (.codereviewmate.yaml in repo root)
  3. User config file (~/.config/codereviewmate/config.yaml)
  4. Environment variables (CRM_* prefix)
  5. CLI flags (highest priority)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from codereviewmate.core.config.defaults import DEFAULT_TEAM_CONFIG
from codereviewmate.core.models.config import LLMConfig, LLMProvider, TeamConfig


class ConfigManager:
    """Manages configuration loading and merging across layers."""

    def __init__(self):
        self._config: Optional[TeamConfig] = None
        self._user_config_path = Path.home() / ".config" / "codereviewmate" / "config.yaml"

    @property
    def config(self) -> TeamConfig:
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(
        self,
        team_config_path: Optional[Path] = None,
        user_config_path: Optional[Path] = None,
        cli_overrides: Optional[dict] = None,
    ) -> TeamConfig:
        """Load configuration from all layers and merge."""
        # Layer 1: Built-in defaults
        config_data = DEFAULT_TEAM_CONFIG.model_dump()

        # Layer 2: Team config file (in current directory or repo root)
        team_path = team_config_path or self._find_team_config()
        if team_path and team_path.exists():
            team_data = self._read_yaml(team_path)
            if team_data:
                config_data = self._deep_merge(config_data, team_data)

        # Layer 3: User config file
        user_path = user_config_path or self._user_config_path
        if user_path.exists():
            user_data = self._read_yaml(user_path)
            if user_data:
                config_data = self._deep_merge(config_data, user_data)

        # Layer 4: Environment variables
        env_data = self._read_env_vars()
        if env_data:
            config_data = self._deep_merge(config_data, env_data)

        # Layer 5: CLI overrides
        if cli_overrides:
            config_data = self._deep_merge(config_data, cli_overrides)

        return TeamConfig(**config_data)

    def reload(self) -> TeamConfig:
        """Force reload configuration from all sources."""
        self._config = self.load()
        return self._config

    def save_team_config(self, path: Path) -> None:
        """Save current config as team config file."""
        data = self.config.model_dump(exclude_none=True)
        content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _find_team_config(self) -> Optional[Path]:
        """Find .codereviewmate.yaml in current directory or git root."""
        current = Path.cwd()
        for _ in range(10):
            candidate = current / ".codereviewmate.yaml"
            if candidate.exists():
                return candidate
            if (current / ".git").exists():
                return None
            parent = current.parent
            if parent == current:
                break
            current = parent
        return None

    @staticmethod
    def _read_yaml(path: Path) -> Optional[dict]:
        """Read and parse a YAML config file."""
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f)
        except (OSError, yaml.YAMLError):
            return None

    @staticmethod
    def _read_env_vars() -> dict:
        """Extract configuration from CRM_* environment variables."""
        env_config: dict = {}
        env_mappings = {
            "CRM_LLM_PROVIDER": ("llm", "provider"),
            "CRM_LLM_MODEL": ("llm", "model"),
            "CRM_LLM_API_KEY": ("llm", "api_key"),
            "CRM_LLM_API_BASE": ("llm", "api_base"),
            "CRM_LLM_MAX_TOKENS": ("llm", "max_tokens"),
            "CRM_LLM_TEMPERATURE": ("llm", "temperature"),
            "CRM_EMBEDDING_PROVIDER": ("embedding", "provider"),
            "CRM_EMBEDDING_MODEL": ("embedding", "model"),
        }
        for env_var, (section, key) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                env_config.setdefault(section, {})[key] = self._cast_value(value)
        return env_config

    @staticmethod
    def _cast_value(value: str):
        """Cast string environment variable to appropriate type."""
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Deep merge two dicts, with override taking precedence."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._deep_merge(result[key], value)
            else:
                result[key] = value
        return result


_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global config manager singleton."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> TeamConfig:
    """Get the current configuration."""
    return get_config_manager().config
