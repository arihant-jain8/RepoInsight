"""Engineering Intelligence Copilot — Streamlit entrypoint (Overview / Home).

The sidebar lists the role-based pages (Unit Head / Project Manager / Team Lead)
from the pages/ directory. This landing page is the org-wide executive overview.
"""

import os
import sys

# Make the modules in src/ importable when launched via `streamlit run app.py`.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import plotly.express as px
import streamlit as st

import analytics
import config
import database
import ui

st.set_page_config(
    page_title="Engineering Intelligence Copilot",
    page_icon="🔬",
    layout="wide",
)

st.sidebar.title("🔬 Engineering Copilot")
st.sidebar.caption("Pick a role-based view above, or browse the overview here.")

ui.require_db()

st.title("Executive Overview")
st.caption(f"Org-wide engineering intelligence · central DB `{config.DB_PATH}`")

org = ui.load_org_summary()
ranks = ui.load_rankings()

# --- KPI cards ------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Modules", org["modules"])
c2.metric("🟢 Healthy", org["healthy"])
c3.metric("🟠 Warning", org["warning"])
c4.metric("🔴 Critical", org["critical"])
c5.metric("Avg Build Success", f"{org['avg_build_success']:.1f}%")

# --- Callouts -------------------------------------------------------------
hi, lo = org["highest_risk"], org["fastest_improving"]
cc1, cc2, cc3 = st.columns(3)
if hi:
    cc1.error(f"**Highest risk:** {hi['module']} — "
              f"{ui.RISK_EMOJI[hi['risk_level']]} {hi['risk_score']} "
              f"({hi['risk_level']})")
if lo:
    cc2.success(f"**Fastest improving:** {lo['module']} — "
                f"clang {lo['warning_trend']}")
cc3.info(f"**Customer issues (all time):** {org['total_customer_issues']}")

st.divider()

# --- Rankings table -------------------------------------------------------
st.subheader("Module rankings by risk")
import pandas as pd

cols = ["module", "project", "unit", "risk_level", "risk_score",
        "build_success_rate", "avg_clang_warnings_per_commit",
        "punctuality_days_late", "customer_issues", "warning_trend"]
df = pd.DataFrame(ranks)[cols].rename(columns={
    "risk_score": "risk", "build_success_rate": "build %",
    "avg_clang_warnings_per_commit": "clang/commit",
    "punctuality_days_late": "days late", "customer_issues": "cust. issues",
    "warning_trend": "clang trend"})
st.dataframe(ui.style_risk_level(df), width="stretch", hide_index=True)

# --- Risk bar chart -------------------------------------------------------
st.subheader("Risk score per module")
fig = px.bar(
    pd.DataFrame(ranks), x="module", y="risk_score", color="risk_level",
    color_discrete_map=ui.RISK_COLORS, text="risk_score",
    category_orders={"module": [r["module"] for r in ranks]},
    labels={"risk_score": "Risk score", "module": "Module",
            "risk_level": "Level"},
)
fig.update_traces(textposition="outside")
fig.update_layout(yaxis_range=[0, 100])
st.plotly_chart(fig, width="stretch")

# --- Raw table browser (kept for transparency) ---------------------------
with st.expander("Browse any raw table / view"):
    table = st.selectbox("Table or view", database.table_names())
    if table:
        st.dataframe(
            database.query_df(f"SELECT * FROM {table} LIMIT 500"),
            width="stretch", hide_index=True,
        )
