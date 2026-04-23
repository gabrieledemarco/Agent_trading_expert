"""V2 model repository."""

from typing import Optional

from data.storage.data_manager import DataStorageManager


class ModelRepositoryV2:
    def __init__(self, db: Optional[DataStorageManager] = None):
        self.db = db or DataStorageManager()

    def create(self, model: dict) -> str:
        return self.db.save_model_v2(model)

    def list(self, status: Optional[str] = None, limit: int = 100) -> list[dict]:
        return self.db.get_models_v2(status=status, limit=limit)
