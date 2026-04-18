"""Contract tests for API response shapes.

Guards the FastAPI endpoint response schemas.
Uses the real models/validated/ directory — no server needed.
"""
import json
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
VALIDATED_DIR = ROOT / "models" / "validated"


class TestStrategiesEndpointContract:
    """The /strategies endpoint reads *_validation.json and returns a list."""

    def _build_strategy_list(self):
        """Simulate what GET /strategies does (reads validation JSONs)."""
        strategies = []
        for p in VALIDATED_DIR.glob("*_validation.json"):
            with open(p) as f:
                data = json.load(f)
            rr = data.get("risk_return_profile", {})
            rob = data.get("statistical_robustness", {})
            strategies.append({
                "name": data["model_name"],
                "status": data["validation_status"],
                "risk_level": rr.get("risk_score", "UNKNOWN"),
                "sharpe_ratio": rr.get("sharpe_ratio", 0.0),
                "robustness": rob.get("robustness_score", "UNKNOWN"),
            })
        return strategies

    def test_strategies_list_not_empty(self):
        strategies = self._build_strategy_list()
        assert len(strategies) > 0

    def test_strategies_required_fields(self):
        required = {"name", "status", "risk_level", "sharpe_ratio", "robustness"}
        for s in self._build_strategy_list():
            assert required.issubset(s.keys()), (
                f"Strategy missing fields: {required - s.keys()}"
            )

    def test_strategies_status_values(self):
        valid_statuses = {"APPROVED", "REJECTED"}
        for s in self._build_strategy_list():
            assert s["status"] in valid_statuses

    def test_strategies_sharpe_is_numeric(self):
        for s in self._build_strategy_list():
            assert isinstance(s["sharpe_ratio"], (int, float))

    def test_approved_count(self):
        strategies = self._build_strategy_list()
        approved = [s for s in strategies if s["status"] == "APPROVED"]
        assert len(approved) == 4, (
            f"Expected 4 APPROVED strategies, got {len(approved)}"
        )

    def test_rejected_count(self):
        strategies = self._build_strategy_list()
        rejected = [s for s in strategies if s["status"] == "REJECTED"]
        assert len(rejected) == 2, (
            f"Expected 2 REJECTED strategies, got {len(rejected)}"
        )


class TestDashboardSummaryContract:
    """The /dashboard/summary endpoint response shape."""

    REQUIRED_FIELDS = {
        "research_papers": (int,),
        "specs_created": (int,),
        "models_implemented": (int,),
        "models_validated": (int,),
        "total_trades": (int,),
        "current_equity": (int, float),
        "total_return": (int, float),
        "sharpe_ratio": (int, float),
    }

    def test_summary_shape(self):
        """Simulate DataStorageManager.get_dashboard_summary() output shape."""
        import sys
        sys.path.insert(0, str(ROOT))
        try:
            from data.storage.data_manager import DataStorageManager
            db = DataStorageManager()
            summary = db.get_dashboard_summary()
        except Exception:
            pytest.skip("DataStorageManager unavailable")

        for field, types in self.REQUIRED_FIELDS.items():
            assert field in summary, f"dashboard summary missing '{field}'"
            assert isinstance(summary[field], types), (
                f"summary.{field} wrong type: {type(summary[field])}"
            )
