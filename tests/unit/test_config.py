"""Tests for configuration management."""

from __future__ import annotations

from pathlib import Path

from codereviewmate.core.config.defaults import DEFAULT_TEAM_CONFIG
from codereviewmate.core.config.manager import ConfigManager
from codereviewmate.core.models.config import LLMProvider, TeamConfig


class TestConfigManager:
    def test_default_config(self):
        """Default config should load without errors."""
        manager = ConfigManager()
        config = manager.load()
        assert isinstance(config, TeamConfig)
        assert config.team_name == "default"
        assert config.llm.provider == LLMProvider.CLAUDE

    def test_team_config_override(self, temp_team_config: Path):
        """Team config file should override defaults."""
        manager = ConfigManager()
        config = manager.load(team_config_path=temp_team_config)
        assert config.team_name == "test-team"
        assert config.review.auto_fix_enabled is False

    def test_cli_overrides(self):
        """CLI overrides should have highest priority."""
        manager = ConfigManager()
        config = manager.load(
            cli_overrides={
                "llm": {"model": "claude-opus-4-7"},
                "review": {"auto_fix_enabled": True},
            }
        )
        assert config.llm.model == "claude-opus-4-7"
        assert config.review.auto_fix_enabled is True

    def test_env_var_parsing(self):
        """Environment variables should be parsed correctly."""
        manager = ConfigManager()
        assert manager._cast_value("true") is True
        assert manager._cast_value("FALSE") is False
        assert manager._cast_value("42") == 42
        assert manager._cast_value("3.14") == 3.14
        assert manager._cast_value("hello") == "hello"

    def test_deep_merge(self):
        """Deep merge should correctly nest dictionaries."""
        manager = ConfigManager()
        base = {"a": 1, "b": {"x": 1, "y": 2}}
        override = {"b": {"y": 99, "z": 3}, "c": 4}
        result = manager._deep_merge(base, override)
        assert result == {"a": 1, "b": {"x": 1, "y": 99, "z": 3}, "c": 4}

    def test_save_and_reload(self, tmp_path: Path):
        """Saved config should be reloadable."""
        manager = ConfigManager()
        config = manager.load()
        config_path = tmp_path / "test_config.yaml"
        manager.save_team_config(config_path)
        assert config_path.exists()

        # Reload from saved file
        reloaded = manager.load(team_config_path=config_path)
        assert reloaded.llm.model == config.llm.model
