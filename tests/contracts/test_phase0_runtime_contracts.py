"""Phase 0 contracts: runtime/deploy configuration baseline checks."""

from pathlib import Path


ROOT = Path(__file__).parent.parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_render_yaml_contains_required_keys():
    render_file = ROOT / "render.yaml"
    assert render_file.exists(), "Missing render.yaml"
    content = _read(render_file)
    assert "startCommand: uvicorn api.main:app" in content
    assert "healthCheckPath: /health" in content
    assert "DATABASE_URL" in content


def test_env_example_contains_required_variables():
    env_file = ROOT / ".env.example"
    assert env_file.exists(), "Missing .env.example"
    content = _read(env_file)
    required = [
        "DATABASE_URL=",
        "ALPACA_API_KEY=",
        "ALPACA_SECRET_KEY=",
        "OPENAI_API_KEY=",
        "PORT=",
        "LOG_LEVEL=",
    ]
    for key in required:
        assert key in content, f"Missing env var example: {key}"


def test_data_storage_manager_contract_mentions_postgres_only():
    content = _read(ROOT / "data" / "storage" / "data_manager.py")
    assert "DATABASE_URL is not set" in content
    assert "must be a postgresql:// URL" in content
