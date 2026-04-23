"""Phase 0 contracts: static SQL migration V2 integrity checks."""

from pathlib import Path


ROOT = Path(__file__).parent.parent.parent
SQL_FILE = ROOT / "migrations" / "V2__architecture.sql"


def _sql() -> str:
    return SQL_FILE.read_text(encoding="utf-8").lower()


def test_v2_sql_file_exists():
    assert SQL_FILE.exists(), "Missing V2 SQL migration file"


def test_v2_sql_has_core_tables():
    sql = _sql()
    for table in ("strategies", "models_v2", "backtest_reports", "validations_v2"):
        assert f"create table if not exists {table}" in sql


def test_v2_sql_has_event_triggers():
    sql = _sql()
    expected_triggers = (
        "trg_spec_created",
        "trg_model_state_changed",
        "trg_backtest_completed",
        "trg_validation_result",
    )
    for trigger_name in expected_triggers:
        assert trigger_name in sql, f"Missing trigger definition: {trigger_name}"


def test_v2_sql_has_expected_events():
    sql = _sql()
    for event in (
        "spec.created",
        "model.validated",
        "model.rejected",
        "backtest.completed",
        "validation.approved",
        "validation.warning",
        "validation.rejected",
        "validation.max_retries",
    ):
        assert event in sql, f"Missing expected event in migration: {event}"


def test_v2_statuses_include_human_review():
    sql = _sql()
    assert "'human_review'" in sql
