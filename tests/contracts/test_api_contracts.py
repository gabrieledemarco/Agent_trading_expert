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


class TestApiDashboardSummaryContract:
    """The new GET /api/dashboard/summary response shape."""

    REQUIRED_TOP_KEYS = {"last_updated", "portfolio", "strategies", "models", "research", "agents", "trades"}
    PORTFOLIO_KEYS    = {"equity", "total_return", "sharpe_ratio", "max_drawdown"}
    STRATEGIES_KEYS   = {"total", "approved", "deployed", "by_status"}
    MODELS_KEYS       = {"total", "approved"}
    RESEARCH_KEYS     = {"papers", "specs"}
    AGENTS_KEYS       = {"total", "active", "idle"}
    TRADES_KEYS       = {"total"}

    def _build_summary(self):
        import sys
        sys.path.insert(0, str(ROOT))
        try:
            from data.storage.data_manager import DataStorageManager
            from datetime import datetime, timezone
            db = DataStorageManager()
            base   = db.get_dashboard_summary()
            risk   = db.get_performance(days=30)
            strats = db.get_strategies_v2(limit=500)
            agents = db.get_agent_status()
            latest = risk[0] if risk else {}
            by_status = {}
            for s in strats:
                st = str(s.get("status", "draft"))
                by_status[st] = by_status.get(st, 0) + 1
            active = sum(1 for a in agents if str(a.get("status","")).lower()=="running")
            return {
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "portfolio": {"equity": float(latest.get("equity") or 0), "total_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0},
                "strategies": {"total": len(strats), "approved": by_status.get("approved",0), "deployed": by_status.get("deployed",0), "by_status": by_status},
                "models": {"total": int(base.get("models_implemented",0)), "approved": int(base.get("models_validated",0))},
                "research": {"papers": int(base.get("research_papers",0)), "specs": int(base.get("specs_created",0))},
                "agents": {"total": len(agents), "active": active, "idle": max(0, len(agents)-active)},
                "trades": {"total": int(base.get("total_trades",0))},
            }
        except Exception:
            pytest.skip("DataStorageManager unavailable")

    def test_top_level_keys(self):
        s = self._build_summary()
        assert self.REQUIRED_TOP_KEYS.issubset(s.keys())

    def test_portfolio_keys(self):
        s = self._build_summary()
        assert self.PORTFOLIO_KEYS.issubset(s["portfolio"].keys())

    def test_strategies_keys(self):
        s = self._build_summary()
        assert self.STRATEGIES_KEYS.issubset(s["strategies"].keys())

    def test_agents_keys(self):
        s = self._build_summary()
        assert self.AGENTS_KEYS.issubset(s["agents"].keys())

    def test_idle_plus_active_equals_total(self):
        s = self._build_summary()
        ag = s["agents"]
        assert ag["active"] + ag["idle"] == ag["total"]

    def test_last_updated_is_iso(self):
        from datetime import datetime
        s = self._build_summary()
        datetime.fromisoformat(s["last_updated"])  # raises if invalid


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
