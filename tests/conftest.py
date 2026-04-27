"""Shared fixtures for all tests."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _mock_agent_db(request):
    """Silently mock DataStorageManager for all agent tests.

    Any test that actually wants to exercise the DB layer (test_db_schema.py)
    already patches psycopg2 itself, so this fixture's patch is harmless there.
    Tests that need a real DB (integration tests against Neon) should set
    DATABASE_URL in the environment; the mock will be bypassed because the
    real class never raises an exception when the URL is present.
    """
    # Skip for tests that manage DataStorageManager themselves.
    skip_modules = ("test_db_schema", "test_api_contracts", "/smoke/")
    if any(m in request.node.nodeid for m in skip_modules):
        yield
        return

    mock_db = MagicMock()
    mock_db.log_agent_activity = MagicMock(return_value=None)

    # Patch at the source module; BaseAgent imports lazily via
    # `from data.storage.data_manager import DataStorageManager` inside the property.
    with patch("data.storage.data_manager.DataStorageManager", return_value=mock_db):
        yield

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def validation_approved():
    """Real APPROVED validation output – frozen schema v0."""
    with open(FIXTURES_DIR / "validation_approved_v0.json") as f:
        return json.load(f)


@pytest.fixture()
def validation_rejected():
    """Real REJECTED validation output – frozen schema v0."""
    with open(FIXTURES_DIR / "validation_rejected_v0.json") as f:
        return json.load(f)


@pytest.fixture()
def metrics_records():
    """Real performance metrics records – frozen schema v0."""
    records = []
    with open(FIXTURES_DIR / "metrics_snapshot_v0.jsonl") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.load(line if hasattr(line, "read") else __import__("io").StringIO(line)))
    return records


@pytest.fixture()
def trade_records():
    """Real trade log records – frozen schema v0."""
    import io
    records = []
    with open(FIXTURES_DIR / "trade_snapshot_v0.jsonl") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


@pytest.fixture()
def all_validation_files():
    """All real validation JSON files from models/validated/."""
    validated_dir = ROOT / "models" / "validated"
    files = {}
    for p in validated_dir.glob("*_validation.json"):
        with open(p) as f:
            files[p.stem] = json.load(f)
    return files
