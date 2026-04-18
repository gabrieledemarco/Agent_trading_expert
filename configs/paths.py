"""Centralized path management for the TradingAgents project."""

from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()

DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"
SPECS_DIR = ROOT / "specs"
DASHBOARDS_DIR = ROOT / "dashboards"

AGENTS_DIR = ROOT / "agents"
CONFIGS_DIR = ROOT / "configs"


class Paths:
    """Centralized path access for the application."""
    
    ROOT = ROOT
    DATA_DIR = DATA_DIR
    MODELS_DIR = MODELS_DIR
    SPECS_DIR = SPECS_DIR
    DASHBOARDS_DIR = DASHBOARDS_DIR
    AGENTS_DIR = AGENTS_DIR
    CONFIGS_DIR = CONFIGS_DIR
