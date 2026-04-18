"""Data Storage Manager - Supports both SQLite and PostgreSQL."""

import os
import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from urllib.parse import urlparse

from configs.paths import Paths

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lazy import per PostgreSQL (opzionale)
try:
    import psycopg2
    import psycopg2.extras
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False


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
    status: str


@dataclass
class ModelData:
    """Model data record."""
    id: int
    model_name: str
    spec_id: int
    model_type: str
    created_date: str
    status: str
    metrics: str


@dataclass
class ValidationData:
    """Validation data record."""
    id: int
    model_id: int
    validation_date: str
    status: str
    risk_score: str
    sharpe_ratio: float
    robustness_score: str
    anomalies: str


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
    status: str


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
    """Unified data storage manager — SQLite or PostgreSQL."""

    def __init__(self, db_url: Optional[str] = None):
        # Rileva il backend dalla URL
        db_url = db_url or os.getenv("DATABASE_URL")

        if db_url and db_url.startswith("postgresql://"):
            if not HAS_POSTGRES:
                raise RuntimeError("PostgreSQL URL provided but psycopg2 not installed")
            self.backend = "postgres"
            self.db_url = db_url
            self.db_path = None
        else:
            self.backend = "sqlite"
            self.db_path = db_url or str(Paths.DB_PATH)
            self.db_url = None
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)

        self._init_database()
        logger.info(f"Database initialized ({self.backend})")

    def _get_connection(self):
        """Get connection based on backend."""
        if self.backend == "postgres":
            return psycopg2.connect(self.db_url)
        else:  # sqlite
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            return conn

    def _init_database(self):
        """Initialize database schema."""
        if self.backend == "postgres":
            self._init_postgres()
        else:
            self._init_sqlite()

    def _init_sqlite(self):
        """Initialize SQLite schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

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

    def _init_postgres(self):
        """Initialize PostgreSQL schema."""
        conn = psycopg2.connect(self.db_url)
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research (
                id SERIAL PRIMARY KEY,
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS specs (
                id SERIAL PRIMARY KEY,
                model_name TEXT UNIQUE,
                source_paper_id TEXT,
                model_type TEXT,
                created_date TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id SERIAL PRIMARY KEY,
                model_name TEXT UNIQUE,
                spec_id INTEGER,
                model_type TEXT,
                created_date TEXT,
                status TEXT DEFAULT 'implemented',
                metrics TEXT,
                FOREIGN KEY (spec_id) REFERENCES specs(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validation (
                id SERIAL PRIMARY KEY,
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                id SERIAL PRIMARY KEY,
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_logs (
                id SERIAL PRIMARY KEY,
                agent_name TEXT,
                timestamp TEXT,
                status TEXT,
                message TEXT
            )
        """)

        cursor.close()
        conn.close()

    # ── Research methods ──────────────────────────────────────────────────────

    def save_research(self, paper: dict) -> int:
        """Save research finding."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if self.backend == "postgres":
            cursor.execute("""
                INSERT INTO research
                (paper_id, title, authors, published, categories, abstract, pdf_url, found_date, relevance_score)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (paper_id) DO UPDATE SET
                title=EXCLUDED.title, authors=EXCLUDED.authors, published=EXCLUDED.published,
                categories=EXCLUDED.categories, abstract=EXCLUDED.abstract, pdf_url=EXCLUDED.pdf_url,
                relevance_score=EXCLUDED.relevance_score
                RETURNING id
            """, (
                paper.get("id"), paper.get("title"), paper.get("authors"), paper.get("published"),
                paper.get("categories"), paper.get("abstract"), paper.get("pdf_url"),
                datetime.now().strftime("%Y-%m-%d"), paper.get("relevance_score", 0),
            ))
            research_id = cursor.fetchone()[0]
        else:  # sqlite
            cursor.execute("""
                INSERT OR REPLACE INTO research
                (paper_id, title, authors, published, categories, abstract, pdf_url, found_date, relevance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                paper.get("id"), paper.get("title"), paper.get("authors"), paper.get("published"),
                paper.get("categories"), paper.get("abstract"), paper.get("pdf_url"),
                datetime.now().strftime("%Y-%m-%d"), paper.get("relevance_score", 0),
            ))
            research_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return research_id

    def get_research(self, limit: int = 100) -> list[dict]:
        """Get all research findings."""
        conn = self._get_connection()
        if self.backend == "postgres":
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

        cursor.execute("SELECT * FROM research ORDER BY found_date DESC LIMIT %s" if self.backend == "postgres" else
                      "SELECT * FROM research ORDER BY found_date DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ── Spec methods ──────────────────────────────────────────────────────────

    def save_spec(self, spec: dict) -> int:
        """Save specification."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if self.backend == "postgres":
            cursor.execute("""
                INSERT INTO specs
                (model_name, source_paper_id, model_type, created_date, status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (model_name) DO UPDATE SET
                source_paper_id=EXCLUDED.source_paper_id, model_type=EXCLUDED.model_type, status=EXCLUDED.status
                RETURNING id
            """, (
                spec.get("model_name"), spec.get("source_paper_id"), spec.get("model_type"),
                datetime.now().strftime("%Y-%m-%d"), spec.get("status", "pending"),
            ))
            spec_id = cursor.fetchone()[0]
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO specs
                (model_name, source_paper_id, model_type, created_date, status)
                VALUES (?, ?, ?, ?, ?)
            """, (
                spec.get("model_name"), spec.get("source_paper_id"), spec.get("model_type"),
                datetime.now().strftime("%Y-%m-%d"), spec.get("status", "pending"),
            ))
            spec_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return spec_id

    def get_specs(self, status: Optional[str] = None) -> list[dict]:
        """Get specifications."""
        conn = self._get_connection()
        if self.backend == "postgres":
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

        if status:
            if self.backend == "postgres":
                cursor.execute("SELECT * FROM specs WHERE status = %s ORDER BY created_date DESC", (status,))
            else:
                cursor.execute("SELECT * FROM specs WHERE status = ? ORDER BY created_date DESC", (status,))
        else:
            cursor.execute("SELECT * FROM specs ORDER BY created_date DESC")

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ── Model methods ─────────────────────────────────────────────────────────

    def save_model(self, model: dict) -> int:
        """Save model."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if self.backend == "postgres":
            cursor.execute("""
                INSERT INTO models
                (model_name, spec_id, model_type, created_date, status, metrics)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (model_name) DO UPDATE SET
                spec_id=EXCLUDED.spec_id, model_type=EXCLUDED.model_type, status=EXCLUDED.status, metrics=EXCLUDED.metrics
                RETURNING id
            """, (
                model.get("model_name"), model.get("spec_id"), model.get("model_type"),
                datetime.now().strftime("%Y-%m-%d"), model.get("status", "implemented"),
                json.dumps(model.get("metrics", {})),
            ))
            model_id = cursor.fetchone()[0]
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO models
                (model_name, spec_id, model_type, created_date, status, metrics)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                model.get("model_name"), model.get("spec_id"), model.get("model_type"),
                datetime.now().strftime("%Y-%m-%d"), model.get("status", "implemented"),
                json.dumps(model.get("metrics", {})),
            ))
            model_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return model_id

    def get_models(self, status: Optional[str] = None) -> list[dict]:
        """Get models."""
        conn = self._get_connection()
        if self.backend == "postgres":
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

        if status:
            if self.backend == "postgres":
                cursor.execute("SELECT * FROM models WHERE status = %s ORDER BY created_date DESC", (status,))
            else:
                cursor.execute("SELECT * FROM models WHERE status = ? ORDER BY created_date DESC", (status,))
        else:
            cursor.execute("SELECT * FROM models ORDER BY created_date DESC")

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ── Validation methods ────────────────────────────────────────────────────

    def save_validation(self, validation: dict) -> int:
        """Save validation result."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if self.backend == "postgres":
            cursor.execute("""
                INSERT INTO validation
                (model_id, validation_date, status, risk_score, sharpe_ratio, robustness_score, anomalies)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                validation.get("model_id"), datetime.now().strftime("%Y-%m-%d"), validation.get("status"),
                validation.get("risk_score"), validation.get("sharpe_ratio", 0),
                validation.get("robustness_score"), json.dumps(validation.get("anomalies", [])),
            ))
            validation_id = cursor.fetchone()[0]
        else:
            cursor.execute("""
                INSERT INTO validation
                (model_id, validation_date, status, risk_score, sharpe_ratio, robustness_score, anomalies)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                validation.get("model_id"), datetime.now().strftime("%Y-%m-%d"), validation.get("status"),
                validation.get("risk_score"), validation.get("sharpe_ratio", 0),
                validation.get("robustness_score"), json.dumps(validation.get("anomalies", [])),
            ))
            validation_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return validation_id

    def get_validations(self, status: Optional[str] = None) -> list[dict]:
        """Get validations."""
        conn = self._get_connection()
        if self.backend == "postgres":
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

        if status:
            if self.backend == "postgres":
                cursor.execute("SELECT * FROM validation WHERE status = %s ORDER BY validation_date DESC", (status,))
            else:
                cursor.execute("SELECT * FROM validation WHERE status = ? ORDER BY validation_date DESC", (status,))
        else:
            cursor.execute("SELECT * FROM validation ORDER BY validation_date DESC")

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ── Trade methods ─────────────────────────────────────────────────────────

    def save_trade(self, trade: dict) -> int:
        """Save trade."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if self.backend == "postgres":
            cursor.execute("""
                INSERT INTO trades
                (timestamp, symbol, action, quantity, price, value, model_name, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                trade.get("timestamp"), trade.get("symbol"), trade.get("action"),
                trade.get("quantity"), trade.get("price"), trade.get("value"),
                trade.get("model_name"), trade.get("status", "executed"),
            ))
            trade_id = cursor.fetchone()[0]
        else:
            cursor.execute("""
                INSERT INTO trades
                (timestamp, symbol, action, quantity, price, value, model_name, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.get("timestamp"), trade.get("symbol"), trade.get("action"),
                trade.get("quantity"), trade.get("price"), trade.get("value"),
                trade.get("model_name"), trade.get("status", "executed"),
            ))
            trade_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return trade_id

    def get_trades(self, model_name: Optional[str] = None, limit: int = 100) -> list[dict]:
        """Get trades."""
        conn = self._get_connection()
        if self.backend == "postgres":
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

        if model_name:
            if self.backend == "postgres":
                cursor.execute("SELECT * FROM trades WHERE model_name = %s ORDER BY timestamp DESC LIMIT %s",
                             (model_name, limit))
            else:
                cursor.execute("SELECT * FROM trades WHERE model_name = ? ORDER BY timestamp DESC LIMIT ?",
                             (model_name, limit))
        else:
            if self.backend == "postgres":
                cursor.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT %s", (limit,))
            else:
                cursor.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ── Performance methods ───────────────────────────────────────────────────

    def save_performance(self, performance: dict) -> int:
        """Save performance snapshot."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if self.backend == "postgres":
            cursor.execute("""
                INSERT INTO performance
                (timestamp, model_name, equity, total_return, sharpe_ratio, max_drawdown, win_rate, num_trades)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                performance.get("timestamp"), performance.get("model_name"), performance.get("equity"),
                performance.get("total_return"), performance.get("sharpe_ratio"),
                performance.get("max_drawdown"), performance.get("win_rate"), performance.get("num_trades"),
            ))
            perf_id = cursor.fetchone()[0]
        else:
            cursor.execute("""
                INSERT INTO performance
                (timestamp, model_name, equity, total_return, sharpe_ratio, max_drawdown, win_rate, num_trades)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                performance.get("timestamp"), performance.get("model_name"), performance.get("equity"),
                performance.get("total_return"), performance.get("sharpe_ratio"),
                performance.get("max_drawdown"), performance.get("win_rate"), performance.get("num_trades"),
            ))
            perf_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return perf_id

    def get_performance(self, model_name: Optional[str] = None, days: int = 30) -> list[dict]:
        """Get performance history."""
        conn = self._get_connection()
        if self.backend == "postgres":
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

        if model_name:
            if self.backend == "postgres":
                cursor.execute("""
                    SELECT * FROM performance
                    WHERE model_name = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                """, (model_name, days))
            else:
                cursor.execute("""
                    SELECT * FROM performance
                    WHERE model_name = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (model_name, days))
        else:
            if self.backend == "postgres":
                cursor.execute("""
                    SELECT * FROM performance
                    ORDER BY timestamp DESC
                    LIMIT %s
                """, (days,))
            else:
                cursor.execute("""
                    SELECT * FROM performance
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (days,))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ── Agent logs ────────────────────────────────────────────────────────────

    def log_agent_activity(self, agent_name: str, status: str, message: str):
        """Log agent activity."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if self.backend == "postgres":
            cursor.execute("""
                INSERT INTO agent_logs (agent_name, timestamp, status, message)
                VALUES (%s, %s, %s, %s)
            """, (
                agent_name, datetime.now().isoformat(), status, message,
            ))
        else:
            cursor.execute("""
                INSERT INTO agent_logs (agent_name, timestamp, status, message)
                VALUES (?, ?, ?, ?)
            """, (
                agent_name, datetime.now().isoformat(), status, message,
            ))

        conn.commit()
        conn.close()

    def get_agent_logs(self, agent_name: Optional[str] = None, limit: int = 100) -> list[dict]:
        """Get agent logs."""
        conn = self._get_connection()
        if self.backend == "postgres":
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

        if agent_name:
            if self.backend == "postgres":
                cursor.execute("""
                    SELECT * FROM agent_logs
                    WHERE agent_name = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                """, (agent_name, limit))
            else:
                cursor.execute("""
                    SELECT * FROM agent_logs
                    WHERE agent_name = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (agent_name, limit))
        else:
            if self.backend == "postgres":
                cursor.execute("SELECT * FROM agent_logs ORDER BY timestamp DESC LIMIT %s", (limit,))
            else:
                cursor.execute("SELECT * FROM agent_logs ORDER BY timestamp DESC LIMIT ?", (limit,))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ── Dashboard data methods ────────────────────────────────────────────────

    def get_dashboard_summary(self) -> dict:
        """Get dashboard summary data."""
        conn = self._get_connection()
        if self.backend == "postgres":
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

        # Get counts
        if self.backend == "postgres":
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
        else:
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
    db.log_agent_activity("ResearchAgent", "RUNNING", "Starting weekly research")
    summary = db.get_dashboard_summary()
    print(f"Summary: {summary}")
