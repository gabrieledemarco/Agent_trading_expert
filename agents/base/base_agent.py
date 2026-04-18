"""BaseAgent — abstract base class for all agents in the system.

Provides:
- Shared logging
- ExecutionClient access (no agent computes numerics directly)
- DataStorageManager access
- Standardized run() interface
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from agents.base.execution_client import ExecutionClient


class BaseAgent(ABC):
    """Abstract base for all trading agents.

    Subclasses must implement run().
    Numerical computation must go through self.execution_client.
    """

    def __init__(self, engine_url: str | None = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.execution_client = ExecutionClient(engine_url=engine_url)
        self._db = None  # lazy

    # ── Subclass contract ─────────────────────────────────────────────────────

    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """Execute the agent's primary task."""

    # ── Shared helpers ────────────────────────────────────────────────────────

    @property
    def db(self):
        if self._db is None:
            from data.storage.data_manager import DataStorageManager
            self._db = DataStorageManager()
        return self._db

    def log_activity(self, status: str, message: str):
        self.db.log_agent_activity(self.__class__.__name__, status, message)

    def _now(self) -> str:
        return datetime.utcnow().isoformat()
