"""Project Manager view — scoped to one project.

Per-module risk, commit-wise review-comment counts, delivery/punctuality, and
customer-issue -> commit traceability for the manager's project only.
"""

import os
import sys

# Make the modules in src/ importable (pages live one level below the root).
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."))

import pandas as pd
import plotly.express as px
import streamlit as st

from aura.analytics import analytics
from aura.ai import llm_service
from aura import ui

st.set_page_config(page_title="Project Manager", page_icon="📋", layout="wide")
ui.require_db()
ui.llm_badge()

st.title("📋 Project Manager — Project View")
st.caption("Scoped to one project: delivery, review activity, and customer impact.")

projects = analytics.list_projects()
plabels = {f"{p['name']}  ·  {p['unit']}  (mgr: {p['manager']})": p for p in projects}
proj = plabels[st.selectbox("Project", list(plabels.keys()))]
project_id = proj["id"]

# Modules in this project (with risk), filtered by project name.
ranks = [r for r in ui.load_rankings() if r["project"] == proj["name"]]

# --- Delivery KPI row -----------------------------------------------------
kpi = analytics.get_project_delivery_kpis(project_id)
build_pct = (sum(r["build_success_rate"] for r in ranks) / len(ranks)) if ranks else 0.0
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Open tickets", kpi["open_count"] or 0)
k2.metric("🔴 High/critical open", kpi["high_crit_open"] or 0)
k3.metric("Avg MTTR", f"{kpi['mttr_days'] or 0:.1f} d")
k4.metric("Build success", f"{build_pct:.1f}%")
k5.metric("AI usage", f"{kpi['ai_assisted_pct'] or 0:.0f}%")

st.divider()

# --- AI insight (this project, Project Manager tone) ---------------------
ui.render_ai_insight(
    f"Project summary — {proj['name']}",
    f"ai_pm_{project_id}",
    lambda: llm_service.generate_project_report(project_id, "Project Manager"),
)

st.divider()

# --- Module health in this project ---------------------------------------
st.subheader("Modules in this project")
mdf = pd.DataFrame([{
    "module": r["module"], "type": r["type"], "risk_level": r["risk_level"],
    "risk": r["risk_score"], "build %": r["build_success_rate"],
    "days late": r["punctuality_days_late"], "cust. issues": r["customer_issues"],
    "quality trend": r["quality_trend"],
} for r in ranks])
st.dataframe(ui.style_risk_level(mdf), width="stretch", hide_index=True)

# --- Ticket pipeline governance (status / lifecycle / severity) ----------
st.subheader("Ticket pipeline governance")
pipe = analytics.get_jira_pipeline(project_id)
if not pipe:
    st.info("No customer tickets for this project. 🎉")
else:
    pdf = pd.DataFrame(pipe)
    SEV_ORDER = ["low", "medium", "high", "critical"]
    SEV_COLORS = {"low": "#2ecc71", "medium": "#f39c12",
                  "high": "#e67e22", "critical": "#e74c3c"}
    LIFE_ORDER = ["study stage", "implementation stage", "review stage",
                  "testing stage", "deployment stage"]
    g1, g2, g3 = st.columns(3)
    with g1:
        sc = pdf.groupby("status").size().reset_index(name="tickets")
        st.plotly_chart(px.bar(sc, x="status", y="tickets", title="By status"),
                        width="stretch")
    with g2:
        lc = pdf.groupby("lifecycle_status").size().reset_index(name="tickets")
        st.plotly_chart(px.bar(lc, x="lifecycle_status", y="tickets",
                               title="By lifecycle stage",
                               category_orders={"lifecycle_status": LIFE_ORDER}),
                        width="stretch")
    with g3:
        vc = pdf.groupby("severity").size().reset_index(name="tickets")
        st.plotly_chart(px.bar(vc, x="severity", y="tickets", title="By severity",
                               color="severity", category_orders={"severity": SEV_ORDER},
                               color_discrete_map=SEV_COLORS), width="stretch")

    # --- Customer review / ticket pipeline (table) -----------------------
    st.subheader("Customer review / ticket pipeline")
    st.caption("`ai_usage_%` = how much AI was used to handle the incident. "
               "Plus severity, status, lifecycle stage, and the causing commit.")
    jdf = pdf[["ticket_id", "module", "customer", "severity", "status",
               "lifecycle_status", "assigned_to", "automation_percentage",
               "raised_time", "resolve_time", "commit_id"]].rename(
        columns={"automation_percentage": "ai_usage_%"})
    st.dataframe(jdf, width="stretch", hide_index=True)
