"""Data Storage Manager — PostgreSQL (Neon) only."""

import os
import json
import logging
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras

from configs.paths import Paths

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataStorageManager:
    """Unified data storage manager — PostgreSQL (Neon) only.

    Requires DATABASE_URL environment variable pointing to a postgresql:// URL.
    Never falls back to SQLite or filesystem storage.
    """

    def __init__(self, db_url: Optional[str] = None):
        url = db_url or os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not set. "
                "Set it to the Neon PostgreSQL connection string before starting."
            )
        if not url.startswith("postgresql://") and not url.startswith("postgres://"):
            raise RuntimeError(
                f"DATABASE_URL must be a postgresql:// URL, got: {url[:30]}..."
            )
        self.db_url = url
        self._init_schema()
        logger.info("PostgreSQL (Neon) storage initialised")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _connect(self):
        return psycopg2.connect(self.db_url)

    def _cursor(self, conn):
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def _init_schema(self):
        """Ensure all tables exist (idempotent)."""
        conn = self._connect()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS research (
                id            SERIAL PRIMARY KEY,
                paper_id      TEXT UNIQUE,
                title         TEXT,
                authors       TEXT,
                published     TEXT,
                categories    TEXT,
                abstract      TEXT,
                pdf_url       TEXT,
                found_date    TEXT,
                relevance_score REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS specs (
                id              SERIAL PRIMARY KEY,
                model_name      TEXT UNIQUE,
                source_paper_id TEXT,
                model_type      TEXT,
                created_date    TEXT,
                status          TEXT DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS models (
                id           SERIAL PRIMARY KEY,
                model_name   TEXT UNIQUE,
                spec_id      INTEGER REFERENCES specs(id),
                model_type   TEXT,
                created_date TEXT,
                status       TEXT DEFAULT 'implemented',
                metrics      TEXT
            );
            CREATE TABLE IF NOT EXISTS validation (
                id               SERIAL PRIMARY KEY,
                model_id         INTEGER REFERENCES models(id),
                validation_date  TEXT,
                status           TEXT,
                risk_score       TEXT,
                sharpe_ratio     REAL,
                robustness_score TEXT,
                anomalies        TEXT
            );
            CREATE TABLE IF NOT EXISTS trades (
                id         SERIAL PRIMARY KEY,
                timestamp  TEXT,
                symbol     TEXT,
                action     TEXT,
                quantity   REAL,
                price      REAL,
                value      REAL,
                model_name TEXT,
                status     TEXT DEFAULT 'executed'
            );
            CREATE TABLE IF NOT EXISTS performance (
                id           SERIAL PRIMARY KEY,
                timestamp    TEXT,
                model_name   TEXT,
                equity       REAL,
                total_return REAL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                win_rate     REAL,
                num_trades   INTEGER
            );
            CREATE TABLE IF NOT EXISTS agent_logs (
                id              SERIAL PRIMARY KEY,
                agent_name      TEXT,
                timestamp       TEXT,
                status          TEXT,
                message         TEXT,
                duration_ms     INTEGER DEFAULT 0,
                records_written INTEGER DEFAULT 0,
                error_detail    TEXT
            );
            CREATE TABLE IF NOT EXISTS strategies (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                spec JSONB NOT NULL,
                model_id UUID,
                status VARCHAR(30) NOT NULL DEFAULT 'draft',
                validation_result JSONB,
                feedback_payload JSONB,
                retry_count INT NOT NULL DEFAULT 0,
                max_retries INT NOT NULL DEFAULT 3,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS models_v2 (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                strategy_id UUID REFERENCES strategies(id),
                architecture VARCHAR(100),
                hyperparams JSONB,
                directional_accuracy DECIMAL(5,4),
                r2_score DECIMAL(5,4),
                mse DECIMAL(15,10),
                train_test_gap DECIMAL(5,4),
                artifact_path VARCHAR(500),
                status VARCHAR(20) NOT NULL DEFAULT 'training',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                validated_at TIMESTAMPTZ
            );
            CREATE TABLE IF NOT EXISTS backtest_reports (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                strategy_id UUID REFERENCES strategies(id),
                method VARCHAR(50) NOT NULL,
                sharpe_ratio DECIMAL(5,4),
                max_drawdown DECIMAL(5,4),
                total_return DECIMAL(8,4),
                win_rate DECIMAL(5,4),
                monte_carlo_pvalue DECIMAL(5,4),
                regime_stability_score DECIMAL(5,4),
                equity_curve JSONB,
                trades JSONB,
                params JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS validations_v2 (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                strategy_id UUID REFERENCES strategies(id),
                backtest_report_id UUID REFERENCES backtest_reports(id),
                level VARCHAR(5) NOT NULL,
                status VARCHAR(20) NOT NULL,
                metric_name VARCHAR(50),
                expected_threshold VARCHAR(50),
                actual_value DECIMAL(10,6),
                details TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        # Non-destructive migration: add columns if the table already existed
        cur.execute("ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS duration_ms INTEGER DEFAULT 0;")
        cur.execute("ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS records_written INTEGER DEFAULT 0;")
        cur.execute("ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS error_detail TEXT;")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_strategies_model'
                ) THEN
                    ALTER TABLE strategies
                    ADD CONSTRAINT fk_strategies_model
                    FOREIGN KEY (model_id) REFERENCES models_v2(id);
                END IF;
            END $$;
        """)
        cur.close()
        conn.close()

    # ── V2 Strategy domain ───────────────────────────────────────────────────

    def save_strategy(self, strategy: dict) -> str:
        """Write V2 strategy entity (write-by-default for new flows)."""
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute(
            """
            INSERT INTO strategies (name, spec, model_id, status, validation_result, feedback_payload, retry_count, max_retries)
            VALUES (%s, %s::jsonb, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
            RETURNING id
            """,
            (
                strategy.get("name"),
                json.dumps(strategy.get("spec", {})),
                strategy.get("model_id"),
                strategy.get("status", "draft"),
                json.dumps(strategy.get("validation_result")) if strategy.get("validation_result") is not None else None,
                json.dumps(strategy.get("feedback_payload")) if strategy.get("feedback_payload") is not None else None,
                strategy.get("retry_count", 0),
                strategy.get("max_retries", 3),
            ),
        )
        row_id = str(cur.fetchone()["id"])
        conn.commit()
        conn.close()
        return row_id

    def get_strategies_v2(self, status: Optional[str] = None, limit: int = 100) -> list[dict]:
        conn = self._connect()
        cur = self._cursor(conn)
        if status:
            cur.execute(
                "SELECT * FROM strategies WHERE status = %s ORDER BY created_at DESC LIMIT %s",
                (status, limit),
            )
        else:
            cur.execute("SELECT * FROM strategies ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows


    def get_strategy_by_id(self, strategy_id: str) -> Optional[dict]:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute("SELECT * FROM strategies WHERE id = %s", (strategy_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_strategy_status(self, strategy_id: str, status: str) -> None:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute(
            "UPDATE strategies SET status = %s, updated_at = NOW() WHERE id = %s",
            (status, strategy_id),
        )
        conn.commit()
        conn.close()

    def increment_strategy_retry(self, strategy_id: str) -> dict:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute(
            """
            UPDATE strategies
            SET retry_count = retry_count + 1, updated_at = NOW()
            WHERE id = %s
            RETURNING retry_count, max_retries
            """,
            (strategy_id,),
        )
        row = cur.fetchone()
        conn.commit()
        conn.close()

        retry_count = int((row or {}).get("retry_count", 0))
        max_retries = int((row or {}).get("max_retries", 3))
        return {
            "retry_count": retry_count,
            "max_retries": max_retries,
            "reached_max": retry_count >= max_retries,
        }

    def save_model_v2(self, model: dict) -> str:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute(
            """
            INSERT INTO models_v2
                (strategy_id, architecture, hyperparams, directional_accuracy, r2_score, mse,
                 train_test_gap, artifact_path, status)
            VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                model.get("strategy_id"),
                model.get("architecture"),
                json.dumps(model.get("hyperparams", {})),
                model.get("directional_accuracy"),
                model.get("r2_score"),
                model.get("mse"),
                model.get("train_test_gap"),
                model.get("artifact_path"),
                model.get("status", "training"),
            ),
        )
        row_id = str(cur.fetchone()["id"])
        conn.commit()
        conn.close()
        return row_id

    def get_models_v2(self, status: Optional[str] = None, limit: int = 100) -> list[dict]:
        conn = self._connect()
        cur = self._cursor(conn)
        if status:
            cur.execute("SELECT * FROM models_v2 WHERE status = %s ORDER BY created_at DESC LIMIT %s", (status, limit))
        else:
            cur.execute("SELECT * FROM models_v2 ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def save_backtest_report(self, report: dict) -> str:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute(
            """
            INSERT INTO backtest_reports
                (strategy_id, method, sharpe_ratio, max_drawdown, total_return, win_rate,
                 monte_carlo_pvalue, regime_stability_score, equity_curve, trades, params)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
            RETURNING id
            """,
            (
                report.get("strategy_id"),
                report.get("method", "rolling_window"),
                report.get("sharpe_ratio"),
                report.get("max_drawdown"),
                report.get("total_return"),
                report.get("win_rate"),
                report.get("monte_carlo_pvalue"),
                report.get("regime_stability_score"),
                json.dumps(report.get("equity_curve", [])),
                json.dumps(report.get("trades", [])),
                json.dumps(report.get("params", {})),
            ),
        )
        row_id = str(cur.fetchone()["id"])
        conn.commit()
        conn.close()
        return row_id

    def get_backtest_reports(self, strategy_id: Optional[str] = None, limit: int = 100) -> list[dict]:
        conn = self._connect()
        cur = self._cursor(conn)
        if strategy_id:
            cur.execute(
                "SELECT * FROM backtest_reports WHERE strategy_id = %s ORDER BY created_at DESC LIMIT %s",
                (strategy_id, limit),
            )
        else:
            cur.execute("SELECT * FROM backtest_reports ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def save_validation_v2(self, validation: dict) -> str:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute(
            """
            INSERT INTO validations_v2
                (strategy_id, backtest_report_id, level, status, metric_name, expected_threshold, actual_value, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                validation.get("strategy_id"),
                validation.get("backtest_report_id"),
                validation.get("level", "L3"),
                validation.get("status", "warning"),
                validation.get("metric_name"),
                validation.get("expected_threshold"),
                validation.get("actual_value"),
                validation.get("details"),
            ),
        )
        row_id = str(cur.fetchone()["id"])
        conn.commit()
        conn.close()
        return row_id

    def get_validations_v2(self, strategy_id: Optional[str] = None, limit: int = 100) -> list[dict]:
        conn = self._connect()
        cur = self._cursor(conn)
        if strategy_id:
            cur.execute(
                "SELECT * FROM validations_v2 WHERE strategy_id = %s ORDER BY created_at DESC LIMIT %s",
                (strategy_id, limit),
            )
        else:
            cur.execute("SELECT * FROM validations_v2 ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    # ── Research ──────────────────────────────────────────────────────────────

    def save_research(self, paper: dict) -> int:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute("""
            INSERT INTO research
                (paper_id, title, authors, published, categories, abstract, pdf_url, found_date, relevance_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (paper_id) DO UPDATE SET
                title=EXCLUDED.title, authors=EXCLUDED.authors, published=EXCLUDED.published,
                categories=EXCLUDED.categories, abstract=EXCLUDED.abstract,
                pdf_url=EXCLUDED.pdf_url, relevance_score=EXCLUDED.relevance_score
            RETURNING id
        """, (
            paper.get("id"), paper.get("title"), paper.get("authors"),
            paper.get("published"), paper.get("categories"), paper.get("abstract"),
            paper.get("pdf_url"), datetime.now().strftime("%Y-%m-%d"),
            paper.get("relevance_score", 0),
        ))
        row_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return row_id

    def get_research(self, limit: int = 100) -> list[dict]:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute("SELECT * FROM research ORDER BY found_date DESC LIMIT %s", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    # ── Specs ─────────────────────────────────────────────────────────────────

    def save_spec(self, spec: dict) -> int:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute("""
            INSERT INTO specs (model_name, source_paper_id, model_type, created_date, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (model_name) DO UPDATE SET
                source_paper_id=EXCLUDED.source_paper_id,
                model_type=EXCLUDED.model_type,
                status=EXCLUDED.status
            RETURNING id
        """, (
            spec.get("model_name"), spec.get("source_paper_id"), spec.get("model_type"),
            datetime.now().strftime("%Y-%m-%d"), spec.get("status", "pending"),
        ))
        row_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return row_id

    def get_specs(self, status: Optional[str] = None) -> list[dict]:
        conn = self._connect()
        cur = self._cursor(conn)
        if status:
            cur.execute("SELECT * FROM specs WHERE status = %s ORDER BY created_date DESC", (status,))
        else:
            cur.execute("SELECT * FROM specs ORDER BY created_date DESC")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    # ── Models ────────────────────────────────────────────────────────────────

    def save_model(self, model: dict) -> int:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute("""
            INSERT INTO models (model_name, spec_id, model_type, created_date, status, metrics)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (model_name) DO UPDATE SET
                spec_id=EXCLUDED.spec_id, model_type=EXCLUDED.model_type,
                status=EXCLUDED.status, metrics=EXCLUDED.metrics
            RETURNING id
        """, (
            model.get("model_name"), model.get("spec_id"), model.get("model_type"),
            datetime.now().strftime("%Y-%m-%d"), model.get("status", "implemented"),
            json.dumps(model.get("metrics", {})),
        ))
        row_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return row_id

    def get_models(self, status: Optional[str] = None) -> list[dict]:
        conn = self._connect()
        cur = self._cursor(conn)
        if status:
            cur.execute("SELECT * FROM models WHERE status = %s ORDER BY created_date DESC", (status,))
        else:
            cur.execute("SELECT * FROM models ORDER BY created_date DESC")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    # ── Validation ────────────────────────────────────────────────────────────

    def save_validation(self, validation: dict) -> int:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute("""
            INSERT INTO validation
                (model_id, validation_date, status, risk_score, sharpe_ratio, robustness_score, anomalies)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            validation.get("model_id"), datetime.now().strftime("%Y-%m-%d"),
            validation.get("status"), validation.get("risk_score"),
            validation.get("sharpe_ratio", 0), validation.get("robustness_score"),
            json.dumps(validation.get("anomalies", [])),
        ))
        row_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return row_id

    def get_validations(self, status: Optional[str] = None) -> list[dict]:
        conn = self._connect()
        cur = self._cursor(conn)
        if status:
            cur.execute("SELECT * FROM validation WHERE status = %s ORDER BY validation_date DESC", (status,))
        else:
            cur.execute("SELECT * FROM validation ORDER BY validation_date DESC")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_strategies(self) -> list[dict]:
        """Dual-read: return V2 strategies first, fallback to legacy model/validation join."""
        v2 = self.get_strategies_v2(limit=100)
        if v2:
            normalized = []
            for s in v2:
                vr = s.get("validation_result") or {}
                normalized.append({
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "model_type": (s.get("spec") or {}).get("model", {}).get("type", "unknown"),
                    "created_date": s.get("created_at"),
                    "status": str(s.get("status", "draft")).upper(),
                    "risk_level": vr.get("risk_score", "UNKNOWN"),
                    "sharpe_ratio": vr.get("sharpe_ratio", 0.0),
                    "robustness": vr.get("robustness_score", "UNKNOWN"),
                    "validation_date": vr.get("validation_date"),
                })
            return normalized

        # Legacy fallback
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute("""
            SELECT
                m.id,
                m.model_name   AS name,
                m.model_type,
                m.created_date,
                UPPER(COALESCE(v.status, m.status)) AS status,
                v.risk_score   AS risk_level,
                v.sharpe_ratio,
                v.robustness_score AS robustness,
                v.validation_date
            FROM models m
            LEFT JOIN LATERAL (
                SELECT * FROM validation
                WHERE model_id = m.id
                ORDER BY validation_date DESC
                LIMIT 1
            ) v ON true
            ORDER BY m.created_date DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    # ── Trades ────────────────────────────────────────────────────────────────

    def save_trade(self, trade: dict) -> int:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute("""
            INSERT INTO trades (timestamp, symbol, action, quantity, price, value, model_name, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            trade.get("timestamp"), trade.get("symbol"), trade.get("action"),
            trade.get("quantity"), trade.get("price"), trade.get("value"),
            trade.get("model_name"), trade.get("status", "executed"),
        ))
        row_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return row_id

    def get_trades(self, model_name: Optional[str] = None, limit: int = 100) -> list[dict]:
        conn = self._connect()
        cur = self._cursor(conn)
        if model_name:
            cur.execute(
                "SELECT * FROM trades WHERE model_name = %s ORDER BY timestamp DESC LIMIT %s",
                (model_name, limit),
            )
        else:
            cur.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT %s", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    # ── Performance ───────────────────────────────────────────────────────────

    def save_performance(self, performance: dict) -> int:
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute("""
            INSERT INTO performance
                (timestamp, model_name, equity, total_return, sharpe_ratio, max_drawdown, win_rate, num_trades)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            performance.get("timestamp"), performance.get("model_name"),
            performance.get("equity"), performance.get("total_return"),
            performance.get("sharpe_ratio"), performance.get("max_drawdown"),
            performance.get("win_rate"), performance.get("num_trades"),
        ))
        row_id = cur.fetchone()["id"]
        conn.commit()
        conn.close()
        return row_id

    def get_performance(self, model_name: Optional[str] = None, days: int = 30) -> list[dict]:
        conn = self._connect()
        cur = self._cursor(conn)
        if model_name:
            cur.execute(
                "SELECT * FROM performance WHERE model_name = %s ORDER BY timestamp DESC LIMIT %s",
                (model_name, days),
            )
        else:
            cur.execute("SELECT * FROM performance ORDER BY timestamp DESC LIMIT %s", (days,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    # ── Agent logs ────────────────────────────────────────────────────────────

    def log_agent_activity(self, agent_name: str, status: str, message: str,
                           duration_ms: int = 0, records_written: int = 0,
                           error_detail: str = None):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO agent_logs
               (agent_name, timestamp, status, message, duration_ms, records_written, error_detail)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (agent_name, datetime.now().isoformat(), status, message,
             duration_ms, records_written, error_detail),
        )
        conn.commit()
        conn.close()

    def get_agent_status(self) -> list[dict]:
        """Ritorna stato corrente di ogni agente (ultimo log + statistiche)."""
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute("""
            SELECT DISTINCT ON (agent_name)
                agent_name,
                timestamp      AS last_run,
                status         AS last_status,
                message        AS last_message,
                duration_ms,
                records_written,
                error_detail
            FROM agent_logs
            ORDER BY agent_name, timestamp DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_agent_run_history(self, agent_name: str, limit: int = 20) -> list[dict]:
        """Storico delle run di un agente specifico."""
        conn = self._connect()
        cur = self._cursor(conn)
        cur.execute(
            """SELECT * FROM agent_logs WHERE agent_name = %s
               ORDER BY timestamp DESC LIMIT %s""",
            (agent_name, limit)
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_agent_logs(self, agent_name: Optional[str] = None, limit: int = 100) -> list[dict]:
        conn = self._connect()
        cur = self._cursor(conn)
        if agent_name:
            cur.execute(
                "SELECT * FROM agent_logs WHERE agent_name = %s ORDER BY timestamp DESC LIMIT %s",
                (agent_name, limit),
            )
        else:
            cur.execute("SELECT * FROM agent_logs ORDER BY timestamp DESC LIMIT %s", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    # ── Dashboard summary ─────────────────────────────────────────────────────

    def get_dashboard_summary(self) -> dict:
        conn = self._connect()
        cur = self._cursor(conn)

        cur.execute("SELECT COUNT(*) AS count FROM research")
        research_count = cur.fetchone()["count"]

        cur.execute("SELECT COUNT(*) AS count FROM specs")
        specs_count = cur.fetchone()["count"]

        cur.execute("SELECT COUNT(*) AS count FROM models")
        models_count_legacy = cur.fetchone()["count"]
        cur.execute("SELECT COUNT(*) AS count FROM models_v2")
        models_count_v2 = cur.fetchone()["count"]
        models_count = max(models_count_legacy, models_count_v2)

        cur.execute("SELECT COUNT(*) AS count FROM validation WHERE status = 'approved'")
        validated_legacy = cur.fetchone()["count"]
        cur.execute("SELECT COUNT(*) AS count FROM strategies WHERE status = 'approved'")
        validated_v2 = cur.fetchone()["count"]
        validated_count = max(validated_legacy, validated_v2)

        cur.execute("SELECT COUNT(*) AS count FROM trades")
        trades_count = cur.fetchone()["count"]

        cur.execute(
            "SELECT equity, total_return, sharpe_ratio FROM performance ORDER BY timestamp DESC LIMIT 1"
        )
        latest_perf = dict(cur.fetchone() or {})
        conn.close()

        return {
            "research_papers":    research_count,
            "specs_created":      specs_count,
            "models_implemented": models_count,
            "models_validated":   validated_count,
            "total_trades":       trades_count,
            "current_equity":     latest_perf.get("equity", 0),
            "total_return":       latest_perf.get("total_return", 0),
            "sharpe_ratio":       latest_perf.get("sharpe_ratio", 0),
        }
