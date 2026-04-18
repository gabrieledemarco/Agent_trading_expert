#!/usr/bin/env python
"""Migrate SQLite data to PostgreSQL.

Usage:
  python migrate_to_postgres.py postgresql://user:pass@host/db [sqlite_path]
"""

import sys
import json
import sqlite3
import logging
from pathlib import Path

import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_sqlite_to_postgres(sqlite_path: str, postgres_url: str):
    """Migrate all data from SQLite to PostgreSQL."""
    logger.info(f"Starting migration from {sqlite_path} to PostgreSQL")

    if not Path(sqlite_path).exists():
        logger.error(f"SQLite database not found: {sqlite_path}")
        sys.exit(1)

    # Connect to both databases
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    postgres_conn = psycopg2.connect(postgres_url)
    postgres_conn.autocommit = False
    postgres_cursor = postgres_conn.cursor()

    try:
        # ── Research ──────────────────────────────────────────────────────────
        logger.info("Migrating research...")
        sqlite_cursor.execute("SELECT * FROM research")
        for row in sqlite_cursor.fetchall():
            postgres_cursor.execute("""
                INSERT INTO research
                (paper_id, title, authors, published, categories, abstract, pdf_url, found_date, relevance_score)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (paper_id) DO NOTHING
            """, (
                row["paper_id"], row["title"], row["authors"], row["published"],
                row["categories"], row["abstract"], row["pdf_url"],
                row["found_date"], row["relevance_score"],
            ))
        postgres_conn.commit()
        logger.info("✓ Research migrated")

        # ── Specs ─────────────────────────────────────────────────────────────
        logger.info("Migrating specs...")
        sqlite_cursor.execute("SELECT * FROM specs")
        for row in sqlite_cursor.fetchall():
            postgres_cursor.execute("""
                INSERT INTO specs
                (model_name, source_paper_id, model_type, created_date, status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (model_name) DO NOTHING
            """, (
                row["model_name"], row["source_paper_id"], row["model_type"],
                row["created_date"], row["status"],
            ))
        postgres_conn.commit()
        logger.info("✓ Specs migrated")

        # ── Models ────────────────────────────────────────────────────────────
        logger.info("Migrating models...")
        sqlite_cursor.execute("SELECT * FROM models")
        for row in sqlite_cursor.fetchall():
            postgres_cursor.execute("""
                INSERT INTO models
                (model_name, spec_id, model_type, created_date, status, metrics)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (model_name) DO NOTHING
            """, (
                row["model_name"], row["spec_id"], row["model_type"],
                row["created_date"], row["status"], row["metrics"],
            ))
        postgres_conn.commit()
        logger.info("✓ Models migrated")

        # ── Validation ────────────────────────────────────────────────────────
        logger.info("Migrating validation...")
        sqlite_cursor.execute("SELECT * FROM validation")
        for row in sqlite_cursor.fetchall():
            postgres_cursor.execute("""
                INSERT INTO validation
                (model_id, validation_date, status, risk_score, sharpe_ratio, robustness_score, anomalies)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                row["model_id"], row["validation_date"], row["status"],
                row["risk_score"], row["sharpe_ratio"], row["robustness_score"],
                row["anomalies"],
            ))
        postgres_conn.commit()
        logger.info("✓ Validation migrated")

        # ── Trades ────────────────────────────────────────────────────────────
        logger.info("Migrating trades...")
        sqlite_cursor.execute("SELECT * FROM trades")
        for row in sqlite_cursor.fetchall():
            postgres_cursor.execute("""
                INSERT INTO trades
                (timestamp, symbol, action, quantity, price, value, model_name, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row["timestamp"], row["symbol"], row["action"],
                row["quantity"], row["price"], row["value"],
                row["model_name"], row["status"],
            ))
        postgres_conn.commit()
        logger.info("✓ Trades migrated")

        # ── Performance ───────────────────────────────────────────────────────
        logger.info("Migrating performance...")
        sqlite_cursor.execute("SELECT * FROM performance")
        for row in sqlite_cursor.fetchall():
            postgres_cursor.execute("""
                INSERT INTO performance
                (timestamp, model_name, equity, total_return, sharpe_ratio, max_drawdown, win_rate, num_trades)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row["timestamp"], row["model_name"], row["equity"],
                row["total_return"], row["sharpe_ratio"], row["max_drawdown"],
                row["win_rate"], row["num_trades"],
            ))
        postgres_conn.commit()
        logger.info("✓ Performance migrated")

        # ── Agent logs ────────────────────────────────────────────────────────
        logger.info("Migrating agent logs...")
        sqlite_cursor.execute("SELECT * FROM agent_logs")
        for row in sqlite_cursor.fetchall():
            postgres_cursor.execute("""
                INSERT INTO agent_logs
                (agent_name, timestamp, status, message)
                VALUES (%s, %s, %s, %s)
            """, (
                row["agent_name"], row["timestamp"], row["status"], row["message"],
            ))
        postgres_conn.commit()
        logger.info("✓ Agent logs migrated")

        # ── Verification ──────────────────────────────────────────────────────
        logger.info("\nVerifying migration...")
        for table in ["research", "specs", "models", "validation", "trades", "performance", "agent_logs"]:
            sqlite_cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            sqlite_count = sqlite_cursor.fetchone()[0]

            postgres_cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            postgres_count = postgres_cursor.fetchone()[0]

            match = "✓" if sqlite_count == postgres_count else "✗"
            logger.info(f"{match} {table}: SQLite={sqlite_count}, PostgreSQL={postgres_count}")

        logger.info("\nMigration complete!")

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        postgres_conn.rollback()
        sys.exit(1)
    finally:
        postgres_cursor.close()
        postgres_conn.close()
        sqlite_cursor.close()
        sqlite_conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    postgres_url = sys.argv[1]
    # Use provided sqlite_path or default to data/storage/trading_agents.db
    sqlite_db = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).parent / "trading_agents.db")

    migrate_sqlite_to_postgres(sqlite_db, postgres_url)
