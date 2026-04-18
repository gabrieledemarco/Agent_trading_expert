"""Centralized configuration loader — singleton that reads agents.yaml once.

Usage:
    from configs.config_loader import ConfigLoader
    cfg = ConfigLoader.get_section("validation")
    threshold = cfg.get("approval_threshold", {}).get("min_sharpe", 0.5)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from configs.paths import Paths

_CONFIG_PATH = Paths.CONFIGS_DIR / "agents.yaml"


class ConfigLoader:
    _instance: dict | None = None

    @classmethod
    def get(cls, path: Path = _CONFIG_PATH) -> dict:
        if cls._instance is None:
            if path.exists():
                with open(path) as f:
                    cls._instance = yaml.safe_load(f) or {}
            else:
                cls._instance = {}
        return cls._instance

    @classmethod
    def get_section(cls, section: str) -> dict:
        return cls.get().get(section, {})

    @classmethod
    def reload(cls, path: Path = _CONFIG_PATH) -> dict:
        """Force reload — useful in tests."""
        cls._instance = None
        return cls.get(path)
