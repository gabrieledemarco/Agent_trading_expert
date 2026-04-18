"""Contract tests for DataStorageManager — PostgreSQL schema.

Guards the table structure and API contract of DataStorageManager.
Uses mocks so no live database connection is required in CI.
"""
import json
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime


EXPECTED_TABLES = {
    "research": {
        "id", "paper_id", "title", "authors", "published",
        "categories", "abstract", "pdf_url", "found_date", "relevance_score",
    },
    "specs": {
        "id", "model_name", "source_paper_id", "model_type",
        "created_date", "status",
    },
    "models": {
        "id", "model_name", "spec_id", "model_type",
        "created_date", "status", "metrics",
    },
    "validation": {
        "id", "model_id", "validation_date", "status",
        "risk_score", "sharpe_ratio", "robustness_score", "anomalies",
    },
    "trades": {
        "id", "timestamp", "symbol", "action", "quantity",
        "price", "value", "model_name", "status",
    },
    "performance": {
        "id", "timestamp", "model_name", "equity", "total_return",
        "sharpe_ratio", "max_drawdown", "win_rate", "num_trades",
    },
    "agent_logs": {
        "id", "agent_name", "timestamp", "status", "message",
    },
}


def _make_manager():
    """Return a DataStorageManager with mocked psycopg2."""
    with patch("data.storage.data_manager.psycopg2") as mock_pg:
        mock_conn = MagicMock()
        mock_conn.autocommit = False
        mock_pg.connect.return_value = mock_conn
        mock_pg.extras.RealDictCursor = MagicMock()

        from data.storage.data_manager import DataStorageManager
        mgr = DataStorageManager(db_url="postgresql://mock:mock@localhost/mock")
    return mgr, mock_pg


@pytest.fixture(scope="module")
def manager():
    with patch("data.storage.data_manager.psycopg2") as mock_pg:
        mock_conn = MagicMock()
        mock_conn.autocommit = False
        mock_pg.connect.return_value = mock_conn
        mock_pg.extras.RealDictCursor = MagicMock()

        from data.storage.data_manager import DataStorageManager
        mgr = DataStorageManager(db_url="postgresql://mock:mock@localhost/mock")
        mgr._mock_pg = mock_pg
        mgr._mock_conn = mock_conn
        yield mgr


class TestDataStorageManagerInit:

    def test_requires_database_url(self):
        with patch("data.storage.data_manager.psycopg2"):
            from data.storage.data_manager import DataStorageManager
            import os
            old = os.environ.pop("DATABASE_URL", None)
            try:
                with pytest.raises(RuntimeError, match="DATABASE_URL"):
                    DataStorageManager(db_url=None)
            finally:
                if old is not None:
                    os.environ["DATABASE_URL"] = old

    def test_rejects_non_postgres_url(self):
        with patch("data.storage.data_manager.psycopg2"):
            from data.storage.data_manager import DataStorageManager
            with pytest.raises(RuntimeError, match="postgresql://"):
                DataStorageManager(db_url="sqlite:///local.db")

    def test_accepts_postgresql_url(self, manager):
        assert manager.db_url.startswith("postgresql://")

    def test_no_sqlite_import(self):
        import data.storage.data_manager as mod
        import sys
        assert "sqlite3" not in sys.modules or not hasattr(mod, "sqlite3"), (
            "sqlite3 must not be imported in data_manager"
        )

    def test_no_backend_attribute(self, manager):
        assert not hasattr(manager, "backend"), (
            "DataStorageManager must not have a 'backend' attribute (SQLite artefact)"
        )


class TestSchemaContract:
    """Verify the CREATE TABLE statements cover all expected columns."""

    def test_init_schema_called_on_construction(self):
        with patch("data.storage.data_manager.psycopg2") as mock_pg:
            mock_conn = MagicMock()
            mock_pg.connect.return_value = mock_conn
            from data.storage.data_manager import DataStorageManager
            DataStorageManager(db_url="postgresql://mock:mock@localhost/mock")
            # _init_schema calls connect() + cursor.execute()
            assert mock_pg.connect.called

    @pytest.mark.parametrize("table", list(EXPECTED_TABLES))
    def test_create_table_in_schema_sql(self, table):
        """Each expected table must appear in the schema SQL."""
        import inspect, data.storage.data_manager as mod
        src = inspect.getsource(mod.DataStorageManager._init_schema)
        assert f"CREATE TABLE IF NOT EXISTS {table}" in src, (
            f"Table '{table}' missing from _init_schema()"
        )

    @pytest.mark.parametrize("table,cols", list(EXPECTED_TABLES.items()))
    def test_columns_in_schema_sql(self, table, cols):
        """Each expected column must appear in the schema SQL."""
        import inspect, data.storage.data_manager as mod
        src = inspect.getsource(mod.DataStorageManager._init_schema)
        # Find the CREATE TABLE block for this table
        start = src.find(f"CREATE TABLE IF NOT EXISTS {table}")
        end = src.find(";", start)
        block = src[start:end]
        for col in cols:
            assert col in block, (
                f"Column '{col}' missing from CREATE TABLE {table}"
            )


class TestSaveAndGetAPIs:
    """Verify all public save/get methods use %s placeholders (not ?) and call commit."""

    def _exec_with_mock(self, method_name, arg, extra_fetchone=None):
        with patch("data.storage.data_manager.psycopg2") as mock_pg:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = extra_fetchone or {"id": 1}
            mock_cur.fetchall.return_value = []
            mock_conn.cursor.return_value = mock_cur
            mock_pg.connect.return_value = mock_conn
            mock_pg.extras.RealDictCursor = dict

            from data.storage.data_manager import DataStorageManager
            mgr = DataStorageManager(db_url="postgresql://mock:mock@localhost/mock")
            getattr(mgr, method_name)(arg)
            return mock_cur

    def test_save_research_uses_percent_placeholder(self):
        cur = self._exec_with_mock("save_research", {
            "id": "arxiv:1234", "title": "T", "authors": "A",
            "published": "2026-01-01", "categories": "cs.AI",
            "abstract": "abs", "pdf_url": "http://x", "relevance_score": 0.9,
        })
        sql = cur.execute.call_args[0][0]
        assert "%s" in sql and "?" not in sql

    def test_save_spec_uses_percent_placeholder(self):
        cur = self._exec_with_mock("save_spec", {
            "model_name": "m1", "source_paper_id": "p1",
            "model_type": "lstm", "status": "pending",
        })
        sql = cur.execute.call_args[0][0]
        assert "%s" in sql and "?" not in sql

    def test_save_model_uses_percent_placeholder(self):
        cur = self._exec_with_mock("save_model", {
            "model_name": "m1", "model_type": "lstm", "status": "implemented",
        })
        sql = cur.execute.call_args[0][0]
        assert "%s" in sql and "?" not in sql

    def test_save_validation_uses_percent_placeholder(self):
        cur = self._exec_with_mock("save_validation", {
            "model_id": 1, "status": "approved",
            "risk_score": "low", "sharpe_ratio": 1.2,
            "robustness_score": "high", "anomalies": [],
        })
        sql = cur.execute.call_args[0][0]
        assert "%s" in sql and "?" not in sql

    def test_save_trade_uses_percent_placeholder(self):
        cur = self._exec_with_mock("save_trade", {
            "timestamp": "2026-01-01T10:00:00", "symbol": "AAPL",
            "action": "BUY", "quantity": 1.0, "price": 100.0,
            "value": 100.0, "model_name": "m1", "status": "executed",
        })
        sql = cur.execute.call_args[0][0]
        assert "%s" in sql and "?" not in sql

    def test_save_performance_uses_percent_placeholder(self):
        cur = self._exec_with_mock("save_performance", {
            "timestamp": "2026-01-01T10:00:00", "model_name": "m1",
            "equity": 10000.0, "total_return": 0.05, "sharpe_ratio": 1.1,
            "max_drawdown": 0.02, "win_rate": 0.55, "num_trades": 10,
        })
        sql = cur.execute.call_args[0][0]
        assert "%s" in sql and "?" not in sql

    def test_log_agent_activity_uses_percent_placeholder(self):
        with patch("data.storage.data_manager.psycopg2") as mock_pg:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conn.cursor.return_value = mock_cur
            mock_pg.connect.return_value = mock_conn

            from data.storage.data_manager import DataStorageManager
            mgr = DataStorageManager(db_url="postgresql://mock:mock@localhost/mock")
            mgr.log_agent_activity("ResearchAgent", "RUNNING", "started")
            sql = mock_cur.execute.call_args[0][0]
            assert "%s" in sql and "?" not in sql

    def test_get_research_returns_list(self):
        with patch("data.storage.data_manager.psycopg2") as mock_pg:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchall.return_value = [{"id": 1, "paper_id": "x"}]
            mock_conn.cursor.return_value = mock_cur
            mock_pg.connect.return_value = mock_conn
            mock_pg.extras.RealDictCursor = dict

            from data.storage.data_manager import DataStorageManager
            mgr = DataStorageManager(db_url="postgresql://mock:mock@localhost/mock")
            result = mgr.get_research(limit=10)
            assert isinstance(result, list)

    def test_get_dashboard_summary_returns_expected_keys(self):
        with patch("data.storage.data_manager.psycopg2") as mock_pg:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_cur.fetchone.return_value = {"count": 5, "equity": 10000.0,
                                               "total_return": 0.05, "sharpe_ratio": 1.1}
            mock_cur.fetchall.return_value = []
            mock_conn.cursor.return_value = mock_cur
            mock_pg.connect.return_value = mock_conn
            mock_pg.extras.RealDictCursor = dict

            from data.storage.data_manager import DataStorageManager
            mgr = DataStorageManager(db_url="postgresql://mock:mock@localhost/mock")
            summary = mgr.get_dashboard_summary()
            for key in ("research_papers", "specs_created", "models_implemented",
                        "models_validated", "total_trades", "current_equity",
                        "total_return", "sharpe_ratio"):
                assert key in summary, f"Missing key '{key}' from get_dashboard_summary()"
