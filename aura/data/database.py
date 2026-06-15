"""SQLite connection + thin query helpers for the central engineering.db.

Single source of the DB path (config.DB_PATH). Everything else in the app reads
through here, so swapping SQLite for Postgres later means changing only this file.
"""

import os
import sqlite3

from aura import config


def connect() -> sqlite3.Connection:
    """Open a connection to the central DB with row access by column name."""
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """(Re)create all tables and views from schema.sql. Idempotent."""
    with open(config.SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a read query and return a list of dict rows."""
    conn = connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def query_df(sql: str, params: tuple = ()):
    """Run a read query and return a pandas DataFrame (for Streamlit/charts)."""
    import pandas as pd

    conn = connect()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def table_names() -> list[str]:
    """All user tables and views in the DB (handy for the raw viewer)."""
    rows = query(
        "SELECT name FROM sqlite_master "
        "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type, name"
    )
    return [r["name"] for r in rows]
