"""Team Lead view — most technical, scoped to one module.

Per-commit drill-down (author, reviewer, major/minor comments, quality signals),
trend charts, reviewer load, risk breakdown, and the specific commits behind
this module's customer issues.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

import analytics
import database
import risk_engine
import ui

st.set_page_config(page_title="Team Lead", page_icon="🛠️", layout="wide")
ui.require_db()

st.title("🛠️ Team Lead — Module Deep Dive")
st.caption("Most technical view: per-commit detail and quality signals.")

modules = analytics.list_modules()
mlabels = {f"{m['name']}  ·  {m['project']}  (lead: {m['team_lead']})": m
           for m in modules}
mod = mlabels[st.selectbox("Module", list(mlabels.keys()))]
module_id = mod["id"]

health = analytics.get_module_health(module_id)
risk = risk_engine.compute_module_risk(health)

# --- Header metrics + risk breakdown -------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Risk", f"{ui.RISK_EMOJI[risk['level']]} {risk['score']}", risk["level"])
c2.metric("Build success", f"{health['build_success_rate']:.1f}%")
c3.metric("Clang/commit", health["avg_clang_warnings_per_commit"])
c4.metric("Days late", health["punctuality_days_late"])

bd = risk["breakdown"]
b1, b2, b3 = st.columns(3)
b1.metric("Quality risk", bd["quality_risk"])
b2.metric("Delivery risk", bd["delivery_risk"])
b3.metric("Collab risk", bd["collab_risk"])
st.caption(f"Window: last {health['window_weeks']} weeks · "
           f"{health['commits']} commits · "
           f"major comments {health['major_comments']}, "
           f"minor {health['minor_comments']} · "
           f"unreviewed {health['unreviewed_pct']}% · "
           f"clang trend {health['warning_trend']}")

st.divider()

# --- Trend charts ---------------------------------------------------------
st.subheader("Trends over 12 weeks")
trends = pd.DataFrame(analytics.get_module_trends(module_id))
t1, t2 = st.columns(2)
with t1:
    st.plotly_chart(
        px.line(trends, x="week", y="build_success_rate", markers=True,
                title="Build success rate (%)"),
        width="stretch")
with t2:
    st.plotly_chart(
        px.line(trends, x="week", y="avg_clang_warnings_per_commit", markers=True,
                title="Avg clang warnings per commit"),
        width="stretch")
st.plotly_chart(
    px.bar(trends, x="week", y="integration_failures",
           title="Integration failures per week"),
    width="stretch")

st.divider()

# --- Per-commit drill-down -----------------------------------------------
st.subheader("Per-commit drill-down")
commit_df = database.query_df(
    "SELECT c.week, c.commit_id, c.pr_id, "
    "a.name AS author, r.name AS reviewer, "
    "SUM(CASE WHEN rc.severity='major' THEN 1 ELSE 0 END) AS major_comments, "
    "SUM(CASE WHEN rc.severity='minor' THEN 1 ELSE 0 END) AS minor_comments, "
    "c.build_success, c.clang_warnings, c.asan_failures, c.integration_failed, "
    "c.review_latency_hours, c.lines_changed "
    "FROM commits c "
    "LEFT JOIN engineers a ON a.id=c.author_id "
    "LEFT JOIN engineers r ON r.id=c.reviewer_id "
    "LEFT JOIN review_comments rc ON rc.commit_id=c.commit_id "
    "WHERE c.module_id=? "
    "GROUP BY c.id ORDER BY c.committed_at DESC",
    (module_id,),
)
st.dataframe(commit_df, width="stretch", hide_index=True)

st.divider()

# --- Reviewer load --------------------------------------------------------
st.subheader("Reviewer load")
reviewer_df = database.query_df(
    "SELECT e.name AS reviewer, COUNT(DISTINCT c.id) AS commits_reviewed, "
    "COUNT(rc.id) AS comments_left, "
    "SUM(CASE WHEN rc.severity='major' THEN 1 ELSE 0 END) AS major "
    "FROM commits c "
    "LEFT JOIN engineers e ON e.id=c.reviewer_id "
    "LEFT JOIN review_comments rc ON rc.commit_id=c.commit_id "
    "WHERE c.module_id=? GROUP BY c.reviewer_id "
    "ORDER BY commits_reviewed DESC",
    (module_id,),
)
st.dataframe(reviewer_df, width="stretch", hide_index=True)

st.divider()

# --- Commits behind this module's customer issues ------------------------
st.subheader("Commits behind customer issues")
issue_df = database.query_df(
    "SELECT cu.name AS customer, ci.severity, ci.error_info, ci.commit_id, "
    "a.name AS author, ci.report_time, ci.resolve_time "
    "FROM customer_issues ci "
    "JOIN customers cu ON cu.id=ci.customer_id "
    "LEFT JOIN commits c ON c.commit_id=ci.commit_id "
    "LEFT JOIN engineers a ON a.id=c.author_id "
    "WHERE ci.module_id=? ORDER BY ci.severity DESC",
    (module_id,),
)
if issue_df.empty:
    st.info("No customer issues linked to this module. 🎉")
else:
    st.dataframe(issue_df, width="stretch", hide_index=True)
