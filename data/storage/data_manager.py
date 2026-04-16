"""Data Storage Manager - Unified data storage for all agents."""

import os
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ResearchData:
    """Research data record."""
    id: int
    paper_id: str
    title: str
    authors: str
    published: str
    categories: str
    abstract: str
    pdf_url: str
    found_date: str
    relevance_score: float


@dataclass
class SpecData:
    """Specification data record."""
    id: int
    model_name: str
    source_paper_id: str
    model_type: str
    created_date: str
    status: str  # pending, implemented, validated, trading


@dataclass
class ModelData:
    """Model data record."""
    id: int
    model_name: str
    spec_id: int
    model_type: str
    created_date: str
    status: str  # implemented, validated, active, retired
    metrics: str  # JSON string


@dataclass
class ValidationData:
    """Validation data record."""
    id: int
    model_id: int
    validation_date: str
    status: str  # approved, rejected
    risk_score: str
    sharpe_ratio: float
    robustness_score: str
    anomalies: str  # JSON string


@dataclass
class TradeData:
    """Trade data record."""
    id: int
    timestamp: str
    symbol: str
    action: str
    quantity: float
    price: float
    value: float
    model_name: str
    status: str  # pending, executed, failed


@dataclass
class PerformanceData:
    """Performance data record."""
    id: int
    timestamp: str
    model_name: str
    equity: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    num_trades: int


class DataStorageManager:
    """Unified data storage manager for all agents."""

    def __init__(self, db_path: str = "data/storage/trading_agents.db"):
        self.db_path = db_path
        self.db_dir = Path(db_path).parent
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Research table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT UNIQUE,
                title TEXT,
                authors TEXT,
                published TEXT,
                categories TEXT,
                abstract TEXT,
                pdf_url TEXT,
                found_date TEXT,
                relevance_score REAL DEFAULT 0
            )
        """)

        # Specs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS specs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT UNIQUE,
                source_paper_id TEXT,
                model_type TEXT,
                created_date TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)

        # Models table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT UNIQUE,
                spec_id INTEGER,
                model_type TEXT,
                created_date TEXT,
                status TEXT DEFAULT 'implemented',
                metrics TEXT,
                FOREIGN KEY (spec_id) REFERENCES specs(id)
            )
        """)

        # Validation table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER,
                validation_date TEXT,
                status TEXT,
                risk_score TEXT,
                sharpe_ratio REAL,
                robustness_score TEXT,
                anomalies TEXT,
                FOREIGN KEY (model_id) REFERENCES models(id)
            )
        """)

        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                action TEXT,
                quantity REAL,
                price REAL,
                value REAL,
                model_name TEXT,
                status TEXT DEFAULT 'executed'
            )
        """)

        # Performance table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                model_name TEXT,
                equity REAL,
                total_return REAL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                win_rate REAL,
                num_trades INTEGER
            )
        """)

        # Agent logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                timestamp TEXT,
                status TEXT,
                message TEXT
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")

    def _get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    # Research methods
    def save_research(self, paper: dict) -> int:
        """Save research finding."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO research 
            (paper_id, title, authors, published, categories, abstract, pdf_url, found_date, relevance_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            paper.get("id"),
            paper.get("title"),
            paper.get("authors"),
            paper.get("published"),
            paper.get("categories"),
            paper.get("abstract"),
            paper.get("pdf_url"),
            datetime.now().strftime("%Y-%m-%d"),
            paper.get("relevance_score", 0),
        ))

        conn.commit()
        research_id = cursor.lastrowid
        conn.close()
        return research_id

    def get_research(self, limit: int = 100) -> list[dict]:
        """Get all research findings."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM research ORDER BY found_date DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # Spec methods
    def save_spec(self, spec: dict) -> int:
        """Save specification."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO specs 
            (model_name, source_paper_id, model_type, created_date, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            spec.get("model_name"),
            spec.get("source_paper_id"),
            spec.get("model_type"),
            datetime.now().strftime("%Y-%m-%d"),
            spec.get("status", "pending"),
        ))

        conn.commit()
        spec_id = cursor.lastrowid
        conn.close()
        return spec_id

    def get_specs(self, status: Optional[str] = None) -> list[dict]:
        """Get specifications."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if status:
            cursor.execute("SELECT * FROM specs WHERE status = ? ORDER BY created_date DESC", (status,))
        else:
            cursor.execute("SELECT * FROM specs ORDER BY created_date DESC")

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Model methods
    def save_model(self, model: dict) -> int:
        """Save model."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO models 
            (model_name, spec_id, model_type, created_date, status, metrics)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            model.get("model_name"),
            model.get("spec_id"),
            model.get("model_type"),
            datetime.now().strftime("%Y-%m-%d"),
            model.get("status", "implemented"),
            json.dumps(model.get("metrics", {})),
        ))

        conn.commit()
        model_id = cursor.lastrowid
        conn.close()
        return model_id

    def get_models(self, status: Optional[str] = None) -> list[dict]:
        """Get models."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if status:
            cursor.execute("SELECT * FROM models WHERE status = ? ORDER BY created_date DESC", (status,))
        else:
            cursor.execute("SELECT * FROM models ORDER BY created_date DESC")

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Validation methods
    def save_validation(self, validation: dict) -> int:
        """Save validation result."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO validation 
            (model_id, validation_date, status, risk_score, sharpe_ratio, robustness_score, anomalies)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            validation.get("model_id"),
            datetime.now().strftime("%Y-%m-%d"),
            validation.get("status"),
            validation.get("risk_score"),
            validation.get("sharpe_ratio", 0),
            validation.get("robustness_score"),
            json.dumps(validation.get("anomalies", [])),
        ))

        conn.commit()
        validation_id = cursor.lastrowid
        conn.close()
        return validation_id

    def get_validations(self, status: Optional[str] = None) -> list[dict]:
        """Get validations."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if status:
            cursor.execute("SELECT * FROM validation WHERE status = ? ORDER BY validation_date DESC", (status,))
        else:
            cursor.execute("SELECT * FROM validation ORDER BY validation_date DESC")

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Trade methods
    def save_trade(self, trade: dict) -> int:
        """Save trade."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO trades 
            (timestamp, symbol, action, quantity, price, value, model_name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.get("timestamp"),
            trade.get("symbol"),
            trade.get("action"),
            trade.get("quantity"),
            trade.get("price"),
            trade.get("value"),
            trade.get("model_name"),
            trade.get("status", "executed"),
        ))

        conn.commit()
        trade_id = cursor.lastrowid
        conn.close()
        return trade_id

    def get_trades(self, model_name: Optional[str] = None, limit: int = 100) -> list[dict]:
        """Get trades."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if model_name:
            cursor.execute("SELECT * FROM trades WHERE model_name = ? ORDER BY timestamp DESC LIMIT ?", 
                         (model_name, limit))
        else:
            cursor.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Performance methods
    def save_performance(self, performance: dict) -> int:
        """Save performance snapshot."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO performance 
            (timestamp, model_name, equity, total_return, sharpe_ratio, max_drawdown, win_rate, num_trades)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            performance.get("timestamp"),
            performance.get("model_name"),
            performance.get("equity"),
            performance.get("total_return"),
            performance.get("sharpe_ratio"),
            performance.get("max_drawdown"),
            performance.get("win_rate"),
            performance.get("num_trades"),
        ))

        conn.commit()
        performance_id = cursor.lastrowid
        conn.close()
        return performance_id

    def get_performance(self, model_name: Optional[str] = None, days: int = 30) -> list[dict]:
        """Get performance history."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if model_name:
            cursor.execute("""
                SELECT * FROM performance 
                WHERE model_name = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (model_name, days))
        else:
            cursor.execute("""
                SELECT * FROM performance 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (days,))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Agent logs
    def log_agent_activity(self, agent_name: str, status: str, message: str):
        """Log agent activity."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO agent_logs (agent_name, timestamp, status, message)
            VALUES (?, ?, ?, ?)
        """, (
            agent_name,
            datetime.now().isoformat(),
            status,
            message,
        ))

        conn.commit()
        conn.close()

    def get_agent_logs(self, agent_name: Optional[str] = None, limit: int = 100) -> list[dict]:
        """Get agent logs."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if agent_name:
            cursor.execute("""
                SELECT * FROM agent_logs 
                WHERE agent_name = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (agent_name, limit))
        else:
            cursor.execute("SELECT * FROM agent_logs ORDER BY timestamp DESC LIMIT ?", (limit,))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Dashboard data methods
    def get_dashboard_summary(self) -> dict:
        """Get dashboard summary data."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get counts
        cursor.execute("SELECT COUNT(*) as count FROM research")
        research_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM specs")
        specs_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM models")
        models_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM validation WHERE status = 'approved'")
        validated_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM trades")
        trades_count = cursor.fetchone()["count"]

        cursor.execute("SELECT equity, total_return, sharpe_ratio FROM performance ORDER BY timestamp DESC LIMIT 1")
        latest_perf = cursor.fetchone()
        latest_perf = dict(latest_perf) if latest_perf else {}

        conn.close()

        return {
            "research_papers": research_count,
            "specs_created": specs_count,
            "models_implemented": models_count,
            "models_validated": validated_count,
            "total_trades": trades_count,
            "current_equity": latest_perf.get("equity", 0),
            "total_return": latest_perf.get("total_return", 0),
            "sharpe_ratio": latest_perf.get("sharpe_ratio", 0),
        }


if __name__ == "__main__":
    db = DataStorageManager()
    print("Database initialized")

    # Test insert
    db.log_agent_activity("ResearchAgent", "RUNNING", "Starting weekly research")
    db.log_agent_activity("ResearchAgent", "COMPLETED", "Found 5 relevant papers")

    summary = db.get_dashboard_summary()
    print(f"Summary: {summary}")