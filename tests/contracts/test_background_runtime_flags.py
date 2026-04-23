"""Runtime flag contracts for background loops in deployed environments."""

from unittest.mock import patch

from api import main


def test_background_jobs_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_BACKGROUND_LOOPS", raising=False)
    assert main.is_background_jobs_enabled() is False


def test_background_jobs_can_be_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_BACKGROUND_LOOPS", "true")
    assert main.is_background_jobs_enabled() is True


def test_db_connectivity_probe_handles_failure():
    with patch("api.main.get_db", side_effect=RuntimeError("db down")):
        assert main.can_connect_db() is False
