"""V2 backtest repository."""

from typing import Optional

from data.storage.data_manager import DataStorageManager


class BacktestRepository:
    def __init__(self, db: Optional[DataStorageManager] = None):
        self.db = db or DataStorageManager()

    def create(self, report: dict) -> str:
        return self.db.save_backtest_report(report)

    def list(self, strategy_id: Optional[str] = None, limit: int = 100) -> list[dict]:
        return self.db.get_backtest_reports(strategy_id=strategy_id, limit=limit)
