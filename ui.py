"""Shared UI helpers for the Streamlit pages: risk colours + cached loaders."""

import os

import streamlit as st

import analytics
import config

RISK_COLORS = {"GREEN": "#2ecc71", "AMBER": "#f39c12", "RED": "#e74c3c"}
RISK_EMOJI = {"GREEN": "🟢", "AMBER": "🟠", "RED": "🔴"}


def require_db() -> None:
    """Stop the page with a helpful message if the DB hasn't been generated."""
    if not os.path.exists(config.DB_PATH):
        st.warning(
            "No database found. Generate it first:\n\n```\npython generate_data.py\n```"
        )
        st.stop()


# --- Cached analytics loaders (cleared when the DB file changes) ----------
def _db_mtime() -> float:
    try:
        return os.path.getmtime(config.DB_PATH)
    except OSError:
        return 0.0


@st.cache_data
def rankings(weeks: int = 4, _mtime: float = 0.0) -> list[dict]:
    return analytics.get_all_module_rankings(weeks)


@st.cache_data
def org_summary(weeks: int = 4, _mtime: float = 0.0) -> dict:
    return analytics.get_org_summary(weeks)


def load_rankings(weeks: int = 4) -> list[dict]:
    return rankings(weeks, _db_mtime())


def load_org_summary(weeks: int = 4) -> dict:
    return org_summary(weeks, _db_mtime())


def style_risk_level(df, column: str = "risk_level"):
    """Return a pandas Styler that colours the risk-level column."""
    def _color(val):
        bg = RISK_COLORS.get(val, "#888")
        return f"background-color: {bg}; color: white; font-weight: 600;"

    return df.style.map(_color, subset=[column])
