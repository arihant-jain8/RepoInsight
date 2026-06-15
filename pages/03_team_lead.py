"""Team Lead view — most technical, scoped to one module.

Type-aware quality metrics, per-commit drill-down, trend charts, the team roster,
a same-type benchmark, reviewer load, and the commits behind customer issues.
"""

import os
import sys

# Make the modules in src/ importable (pages live one level below the root).
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import pandas as pd
import plotly.express as px
import streamlit as st

import analytics
import database
import llm_service
import risk_engine
import ui

st.set_page_config(page_title="Team Lead", page_icon="🛠️", layout="wide")
ui.require_db()
ui.llm_badge()

st.title("🛠️ Team Lead — Module Deep Dive")
st.caption("Most technical view: per-commit detail and type-specific quality signals.")

modules = analytics.list_modules()
mlabels = {f"{m['name']}  ·  {m['type']}  ·  {m['project']}  (lead: {m['team_lead']})": m
           for m in modules}
mod = mlabels[st.selectbox("Module", list(mlabels.keys()))]
module_id = mod["id"]

health = analytics.get_module_health(module_id)
risk = risk_engine.compute_module_risk(health)
catalog = {c["metric"]: c for c in analytics.get_metric_catalog(health["type"])}
bm = analytics.get_type_benchmark(module_id)

# --- Header metrics + risk breakdown -------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Risk", f"{ui.RISK_EMOJI[risk['level']]} {risk['score']}", risk["level"])
c2.metric("Type", health["type"])
c3.metric("Build success", f"{health['build_success_rate']:.1f}%")
c4.metric("Days late", health["punctuality_days_late"])

bd = risk["breakdown"]
b1, b2, b3 = st.columns(3)
b1.metric("Quality risk", bd["quality_risk"])
b2.metric("Delivery risk", bd["delivery_risk"])
b3.metric("Collab risk", bd["collab_risk"])
if bm:
    st.caption(f"Benchmark: among **{bm['peers']} {bm['type']}** modules this ranks "
               f"**#{bm['rank']}** (better than {bm['better_than_pct']}% of peers) · "
               f"window last {health['window_weeks']}w · {health['commits']} commits · "
               f"major {health['major_comments']} / minor {health['minor_comments']} "
               f"comments · unreviewed {health['unreviewed_pct']}% · "
               f"quality trend {health['quality_trend']}")

st.divider()

# --- AI insight (this module, Team Lead tone) ----------------------------
ui.render_ai_insight(
    f"Module deep-dive — {mod['name']}",
    f"ai_tl_{module_id}",
    lambda: llm_service.generate_module_report(module_id, "Team Lead"),
)

st.divider()

# --- Task overview (AURA.md Team Lead "Task Overview Table") --------------
st.subheader("Task overview")
st.caption("Jira tasks for this module — assignee, lifecycle stage, completion.")
tasks = database.query_df(
    "SELECT ticket_id, task_name, assigned_to, severity, status, "
    "lifecycle_status, raised_time, completed_date, commit_id "
    "FROM jira_logs WHERE module_id=? "
    "ORDER BY CASE severity WHEN 'critical' THEN 4 WHEN 'high' THEN 3 "
    "WHEN 'medium' THEN 2 ELSE 1 END DESC, raised_time DESC",
    (module_id,),
)
if tasks.empty:
    st.info("No tasks logged for this module. 🎉")
else:
    st.dataframe(tasks, width="stretch", hide_index=True)

st.divider()

# --- Type-specific quality metrics ---------------------------------------
st.subheader(f"Quality metrics — {health['type']}")
qrows = []
for metric, value in health["quality_metrics"].items():
    c = catalog.get(metric, {})
    qrows.append({
        "metric": c.get("label", metric),
        "value": value, "unit": c.get("unit", ""),
        "risk (0-100)": risk["quality_contrib"].get(metric, 0.0),
        "good": c.get("good"), "bad": c.get("bad"),
    })
qdf = pd.DataFrame(qrows).sort_values("risk (0-100)", ascending=False)
qa, qb = st.columns([3, 2])
with qa:
    st.dataframe(qdf, width="stretch", hide_index=True)
with qb:
    st.plotly_chart(
        px.bar(qdf, x="risk (0-100)", y="metric", orientation="h",
               range_x=[0, 100], title="Per-metric risk contribution",
               color="risk (0-100)", color_continuous_scale="OrRd"),
        width="stretch")

st.divider()

# --- Trend charts ---------------------------------------------------------
st.subheader("Trends over 12 weeks")
trends = analytics.get_module_trends(module_id)
st.plotly_chart(
    px.line(pd.DataFrame(trends["build"]), x="week", y="build_success_rate",
            markers=True, title="Build success rate (%)"),
    width="stretch")
mdf = pd.DataFrame(trends["metrics"])
if not mdf.empty:
    fig = px.line(mdf, x="week", y="avg_value", color="label", markers=True,
                  facet_col="label", facet_col_wrap=2,
                  title=f"{health['type']} quality metrics per week")
    fig.update_yaxes(matches=None)        # independent y per metric (different scales)
    fig.update_xaxes(matches=None)
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    fig.update_layout(showlegend=False, height=420)
    st.plotly_chart(fig, width="stretch")

st.divider()

# --- Live telemetry (AURA.md performance_data) ---------------------------
st.subheader("Live telemetry")
st.caption("Real-time infrastructure readings for this module.")
tel = analytics.get_telemetry(module_id)
if tel:
    st.dataframe(pd.DataFrame(tel), width="stretch", hide_index=True)
else:
    st.caption("No telemetry samples for this module.")

st.divider()

# --- Per-commit drill-down (shared signals + this type's metrics) --------
st.subheader("Per-commit drill-down")
base = database.query_df(
    "SELECT c.week, c.commit_id, c.pr_id, "
    "a.name AS author, r.name AS reviewer, "
    "SUM(CASE WHEN rc.severity='major' THEN 1 ELSE 0 END) AS major, "
    "SUM(CASE WHEN rc.severity='minor' THEN 1 ELSE 0 END) AS minor, "
    "c.build_success, c.integration_failed, c.review_latency_hours, c.lines_changed, "
    "c.committed_at "
    "FROM commits c "
    "LEFT JOIN engineers a ON a.id=c.author_id "
    "LEFT JOIN engineers r ON r.id=c.reviewer_id "
    "LEFT JOIN review_comments rc ON rc.commit_id=c.commit_id "
    "WHERE c.module_id=? GROUP BY c.id",
    (module_id,),
)
mlong = database.query_df(
    "SELECT cm.commit_id, cm.metric, cm.value FROM commit_metrics cm "
    "JOIN commits c ON c.commit_id=cm.commit_id WHERE c.module_id=?",
    (module_id,),
)
if not mlong.empty:
    wide = mlong.pivot(index="commit_id", columns="metric", values="value").reset_index()
    base = base.merge(wide, on="commit_id", how="left")
base = base.sort_values("committed_at", ascending=False).drop(columns=["committed_at"])
st.dataframe(base, width="stretch", hide_index=True)

st.divider()

# --- Team roster ----------------------------------------------------------
st.subheader("Team roster")
members = analytics.get_team_members(module_id)
mem_df = pd.DataFrame([{
    "engineer": m["name"] + (" 👑" if m["is_lead"] else ""),
    "commits authored": m["commits_authored"],
    "commits reviewed": m["commits_reviewed"],
} for m in members])
st.dataframe(mem_df, width="stretch", hide_index=True)

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
    "SELECT ci.customer AS customer, ci.severity, ci.error_info, ci.commit_id, "
    "a.name AS author, ci.report_time, ci.resolve_time "
    "FROM customer_issues ci "
    "LEFT JOIN commits c ON c.commit_id=ci.commit_id "
    "LEFT JOIN engineers a ON a.id=c.author_id "
    "WHERE ci.module_id=? ORDER BY ci.severity DESC",
    (module_id,),
)
if issue_df.empty:
    st.info("No customer issues linked to this module. 🎉")
else:
    st.dataframe(issue_df, width="stretch", hide_index=True)
