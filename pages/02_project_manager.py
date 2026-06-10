"""Project Manager view — scoped to one project.

Per-module risk, commit-wise review-comment counts, delivery/punctuality, and
customer-issue -> commit traceability for the manager's project only.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

import analytics
import ui

st.set_page_config(page_title="Project Manager", page_icon="📋", layout="wide")
ui.require_db()

st.title("📋 Project Manager — Project View")
st.caption("Scoped to one project: delivery, review activity, and customer impact.")

projects = analytics.list_projects()
plabels = {f"{p['name']}  ·  {p['unit']}  (mgr: {p['manager']})": p for p in projects}
proj = plabels[st.selectbox("Project", list(plabels.keys()))]
project_id = proj["id"]

# Modules in this project (with risk), filtered by project name.
ranks = [r for r in ui.load_rankings() if r["project"] == proj["name"]]

st.divider()

# --- Module health in this project ---------------------------------------
st.subheader("Modules in this project")
mdf = pd.DataFrame([{
    "module": r["module"], "risk_level": r["risk_level"],
    "risk": r["risk_score"], "build %": r["build_success_rate"],
    "days late": r["punctuality_days_late"], "cust. issues": r["customer_issues"],
    "clang trend": r["warning_trend"],
} for r in ranks])
st.dataframe(ui.style_risk_level(mdf), width="stretch", hide_index=True)

# --- Commit-wise comment counts per module -------------------------------
st.subheader("Review comments by module (major vs minor)")
comment_rows = []
for r in ranks:
    for cc in analytics.get_commit_comments(r["module_id"]):
        comment_rows.append({"module": r["module"], "major": cc["major"],
                             "minor": cc["minor"]})
if comment_rows:
    cdf = (pd.DataFrame(comment_rows).groupby("module")[["major", "minor"]]
           .sum().reset_index().melt(id_vars="module", var_name="severity",
                                     value_name="comments"))
    fig = px.bar(cdf, x="module", y="comments", color="severity",
                 barmode="group",
                 color_discrete_map={"major": "#e74c3c", "minor": "#95a5a6"},
                 labels={"comments": "Review comments", "module": "Module"})
    st.plotly_chart(fig, width="stretch")

# --- Drill into one module's commit-wise comments ------------------------
st.subheader("Commit-wise comment counts")
mod_pick = st.selectbox("Module", [r["module"] for r in ranks])
mod_id = next(r["module_id"] for r in ranks if r["module"] == mod_pick)
ccdf = pd.DataFrame(analytics.get_commit_comments(mod_id))
if not ccdf.empty:
    ccdf = ccdf[["commit_id", "pr_id", "week", "author", "major", "minor", "total"]]
st.dataframe(ccdf, width="stretch", hide_index=True)

st.divider()

# --- Customer issue -> commit traceability -------------------------------
st.subheader("Customer issues → commit traceability")
st.caption("Which commit (and author/module) is linked to each customer issue.")
trace = analytics.get_customer_trace(project_id)
if trace:
    tdf = pd.DataFrame(trace)[
        ["customer", "issue_severity", "module", "author", "commit_id", "error_info"]]
    st.dataframe(tdf, width="stretch", hide_index=True)
else:
    st.info("No customer issues linked to this project. 🎉")
