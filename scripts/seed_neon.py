#!/usr/bin/env python3
"""Seed Neon con dati demo per dashboard."""
import os
import sys
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.storage.data_manager import DataStorageManager

# Dati seed - 6 modelli
MODELS_SEED = [
    {"model_name": "model_momentum_further_constrains_sharpness_at", "model_type": "LSTM", "status": "implemented"},
    {"model_name": "model_a_comparative_study_of_dynamic", "model_type": "Transformer", "status": "implemented"},
    {"model_name": "model_dynamic_time_window_optimization_for", "model_type": "CNN", "status": "implemented"},
    {"model_name": "model_from_pyx_to_py_investigating", "model_type": "XGBoost", "status": "implemented"},
    {"model_name": "model_intraday_momentum_trading_with_machine", "model_type": "RandomForest", "status": "implemented"},
    {"model_name": "model_highfrequency_statistical_arbitrage", "model_type": "Arbitrage", "status": "implemented"},
]

# 6 validation results
VALIDATION_SEED = [
    {"status": "approved", "risk_score": "low", "sharpe_ratio": 2.1, "robustness_score": "high"},
    {"status": "approved", "risk_score": "medium", "sharpe_ratio": 1.8, "robustness_score": "medium"},
    {"status": "approved", "risk_score": "low", "sharpe_ratio": 2.3, "robustness_score": "high"},
    {"status": "pending", "risk_score": "medium", "sharpe_ratio": 1.5, "robustness_score": "medium"},
    {"status": "approved", "risk_score": "high", "sharpe_ratio": 1.9, "robustness_score": "low"},
    {"status": "approved", "risk_score": "low", "sharpe_ratio": 2.0, "robustness_score": "high"},
]

# 6 research papers
RESEARCH_SEED = [
    {"id": "arXiv:210101234", "title": "Momentum Constrains Sharpe", "authors": "Smith et al.", "published": "2021", "categories": "q-fin", "abstract": "..."},
    {"id": "arXiv:2102.05678", "title": "Dynamic Time Windows", "authors": "Chen et al.", "published": "2021", "categories": "cs.LG", "abstract": "..."},
    {"id": "arXiv:2103.04567", "title": "Comparative Study Dynamic Models", "authors": "Johnson et al.", "published": "2021", "categories": "q-fin", "abstract": "..."},
    {"id": "arXiv:2104.02345", "title": "pyx to py investigation", "authors": "Williams et al.", "published": "2021", "categories": "cs.PL", "abstract": "..."},
    {"id": "arXiv:2105.03456", "title": "Intraday Momentum Trading", "authors": "Brown et al.", "published": "2021", "categories": "q-fin", "abstract": "..."},
    {"id": "arXiv:2106.01234", "title": "High-Frequency Statistical Arbitrage", "authors": "Davis et al.", "published": "2021", "categories": "q-fin", "abstract": "..."},
]

# Performance iniziale
PERFORMANCE_SEED = {
    "equity": 100000.0,
    "total_return": 0.15,
    "sharpe_ratio": 2.1,
    "max_drawdown": -0.08,
    "win_rate": 0.62,
    "num_trades": 156,
}

# Agent logs
AGENT_LOGS_SEED = [
    {"agent_name": "research", "status": "completed", "message": "Found 6 relevant papers"},
    {"agent_name": "spec", "status": "completed", "message": "Generated 6 specs"},
    {"agent_name": "ml_engineer", "status": "completed", "message": "Implemented 6 models"},
    {"agent_name": "validation", "status": "completed", "message": "Validated 6 models"},
    {"agent_name": "trading", "status": "active", "message": "Monitoring market opportunities"},
    {"agent_name": "monitoring", "status": "active", "message": "System healthy"},
]


def seed_neon():
    """Esegue seed di tutti i dati."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)
    
    db = DataStorageManager(db_url)
    print(f"Seeding Neon database...")
    
    # Seed research papers
    for paper in RESEARCH_SEED:
        db.save_research(paper)
    print(f"  - Inserted {len(RESEARCH_SEED)} research papers")
    
    # Seed models e validation
    for i, model in enumerate(MODELS_SEED):
        model_id = db.save_model(model)
        # Link validation to model
        validation = VALIDATION_SEED[i].copy()
        validation["model_id"] = model_id
        db.save_validation(validation)
    print(f"  - Inserted {len(MODELS_SEED)} models with validation")
    
    # Seed performance
    perf = PERFORMANCE_SEED.copy()
    perf["timestamp"] = datetime.now().isoformat()
    perf["model_name"] = "portfolio"
    db.save_performance(perf)
    print(f"  - Inserted performance snapshot")
    
    # Seed agent logs
    for log in AGENT_LOGS_SEED:
        db.log_agent_activity(log["agent_name"], log["status"], log["message"])
    print(f"  - Inserted {len(AGENT_LOGS_SEED)} agent logs")
    
    print("Seed completed!")


if __name__ == "__main__":
    seed_neon()