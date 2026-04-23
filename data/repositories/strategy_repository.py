"""V2 strategy repository."""

from typing import Optional

from data.storage.data_manager import DataStorageManager


class StrategyRepository:
    def __init__(self, db: Optional[DataStorageManager] = None):
        self.db = db or DataStorageManager()

    def create(self, strategy: dict) -> str:
        return self.db.save_strategy(strategy)

    def list(self, status: Optional[str] = None, limit: int = 100) -> list[dict]:
        return self.db.get_strategies_v2(status=status, limit=limit)
