"""Contract tests for SQLite database schema.

Guards the DataStorageManager table structure.
Any column rename or table drop will be caught here.
"""
import sqlite3
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DB_PATH = ROOT / "data" / "storage" / "trading_agents.db"

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


@pytest.fixture(scope="module")
def db_conn():
    if not DB_PATH.exists():
        pytest.skip(f"Database not found at {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


def get_columns(conn, table: str):
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


class TestDatabaseSchema:

    def test_all_tables_exist(self, db_conn):
        cursor = db_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in cursor.fetchall()}
        for table in EXPECTED_TABLES:
            assert table in existing, f"Table '{table}' missing from database"

    @pytest.mark.parametrize("table,expected_cols", list(EXPECTED_TABLES.items()))
    def test_table_columns(self, db_conn, table, expected_cols):
        actual = get_columns(db_conn, table)
        missing = expected_cols - actual
        assert not missing, (
            f"Table '{table}' missing columns: {missing}. "
            f"Existing: {actual}"
        )

    def test_specs_status_values(self, db_conn):
        """Specs status enum: pending, implemented, validated, trading."""
        cursor = db_conn.execute("SELECT DISTINCT status FROM specs")
        valid = {"pending", "implemented", "validated", "trading"}
        for (status,) in cursor.fetchall():
            assert status in valid, f"Unexpected specs.status value: '{status}'"

    def test_models_status_values(self, db_conn):
        """Models status enum: implemented, validated, active, retired."""
        cursor = db_conn.execute("SELECT DISTINCT status FROM models")
        valid = {"implemented", "validated", "active", "retired"}
        for (status,) in cursor.fetchall():
            assert status in valid, f"Unexpected models.status value: '{status}'"
