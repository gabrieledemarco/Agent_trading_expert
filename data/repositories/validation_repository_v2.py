"""V2 validation repository."""

from typing import Optional

from data.storage.data_manager import DataStorageManager


class ValidationRepositoryV2:
    def __init__(self, db: Optional[DataStorageManager] = None):
        self.db = db or DataStorageManager()

    def create(self, validation: dict) -> str:
        return self.db.save_validation_v2(validation)

    def list(self, strategy_id: Optional[str] = None, limit: int = 100) -> list[dict]:
        return self.db.get_validations_v2(strategy_id=strategy_id, limit=limit)
