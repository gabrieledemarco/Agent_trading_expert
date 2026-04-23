"""Phase 0 contracts: documentation coherence for V2 baseline."""

from pathlib import Path


ROOT = Path(__file__).parent.parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v2_docs_exist():
    required = [
        ROOT / "README.md",
        ROOT / "PRD.md",
        ROOT / "DEPLOYMENT_NEON.md",
        ROOT / "docs" / "ARCHITECTURE_V2.md",
        ROOT / "docs" / "MIGRATION_GUIDE_V1_V2.md",
        ROOT / "docs" / "PHASE_0_STABILIZATION.md",
    ]
    for p in required:
        assert p.exists(), f"Missing required V2 doc: {p}"


def test_readme_points_to_v2_docs():
    content = _read(ROOT / "README.md")
    assert "docs/ARCHITECTURE_V2.md" in content
    assert "docs/MIGRATION_GUIDE_V1_V2.md" in content
    assert "Neon PostgreSQL" in content
    assert "Render Web Service" in content


def test_prd_contains_role_split():
    content = _read(ROOT / "PRD.md")
    assert "Model validation (MLEngineer)" in content
    assert "Strategy validation (ValidationAgent)" in content
    assert "PostgreSQL LISTEN/NOTIFY" in content


def test_architecture_v2_has_required_sections():
    content = _read(ROOT / "docs" / "ARCHITECTURE_V2.md")
    assert "Accuratezza vs Validazione" in content
    assert "Model validation minima" in content
    assert "ValidationAgent (L1-L5)" in content
    assert "Stato strategia (target)" in content
