"""Centralized path definitions — single source of truth for all file paths.

All agents and services import from here instead of hardcoding strings.
Default values are identical to the previous hardcoded values, so
existing code is backward-compatible when migrated incrementally.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent


class Paths:
    # Root directories
    ROOT            = ROOT
    DATA_DIR        = ROOT / "data"
    CONFIGS_DIR     = ROOT / "configs"

    # Research
    RESEARCH_DIR    = ROOT / "data" / "research_findings"

    # Specs
    SPECS_DIR       = ROOT / "specs"

    # Models
    MODELS_DIR      = ROOT / "models"
    MODELS_VERSIONS = ROOT / "models" / "versions"
    VALIDATED_DIR   = ROOT / "models" / "validated"

    # Trading logs
    TRADING_LOGS    = ROOT / "trading_logs"
    MONITORING_DIR  = ROOT / "trading_logs" / "monitoring"

    # Database
    STORAGE_DIR     = ROOT / "data" / "storage"
    DB_PATH         = ROOT / "data" / "storage" / "trading_agents.db"

    # Data schemas
    SCHEMAS_DIR     = ROOT / "data" / "schemas"

    # Execution Engine
    EXECUTION_DIR   = ROOT / "execution_engine"

    @classmethod
    def ensure_dirs(cls):
        """Create all required directories if they don't exist."""
        for attr in vars(cls):
            val = getattr(cls, attr)
            if isinstance(val, Path) and not val.suffix:
                val.mkdir(parents=True, exist_ok=True)
