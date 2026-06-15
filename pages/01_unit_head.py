"""Unit Head view — non-technical, org-wide health.

Code-quality bar graph (with team size), punctuality per team, and errors
reported per customer. Business framing; no per-commit detail.
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

st.set_page_config(page_title="Unit Head", page_icon="🏢", layout="wide")
ui.require_db()
ui.llm_badge()

st.title("🏢 Unit Head — Organisation Health")
st.caption("Non-technical, org-wide. Quality, punctuality, and customer impact.")

ranks = ui.load_rankings()

# Optional unit filter
units = ["All units"] + sorted({r["unit"] for r in ranks})
unit = st.selectbox("Unit", units)
view = ranks if unit == "All units" else [r for r in ranks if r["unit"] == unit]

# --- KPI row --------------------------------------------------------------
total_people = sum(r["team_size"] for r in view)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Teams / Modules", len(view))
c2.metric("People", total_people)
c3.metric("🔴 Critical", sum(1 for r in view if r["risk_level"] == "high"))
c4.metric("Avg Build Success",
          f"{(sum(r['build_success_rate'] for r in view) / len(view)):.1f}%")

st.divider()

# --- AI Tool Efficiency per client (AURA.md Unit Head headline) -----------
st.subheader("AI tool efficiency — per client")
st.caption("How much the AI tooling cuts customer MTTR and manual effort, per account.")
eff = analytics.get_account_ai_efficiency()
if unit != "All units":
    eff = [e for e in eff if e["unit"] == unit]
for col, e in zip(st.columns(max(len(eff), 1)), eff):
    with col:
        st.markdown(f"**{e['account']}**")
        reason = (f" — {e['n_critical']} critical ({', '.join(e['critical_modules'])})"
                  if e["n_critical"] else "")
        st.caption(f"{e['unit']} · account risk tier: **{e['risk_tier']}**{reason}")
        st.metric("MTTR reduction", f"{e['mttr_reduction_percentage']:.0f}%")
        st.metric("Manual hours saved", f"{e['manual_triage_hours_saved']:.0f}")
        st.metric("AI-resolved tickets", e["ai_resolved_tickets_count"])
        st.caption(f"Current MTTR ≈ {e['mttr_days']:.1f} days")

st.divider()

# --- AI insight (org-wide, Unit Head tone) -------------------------------
ui.render_ai_insight(
    "Organisation health summary",
    "ai_unit_head",
    lambda: llm_service.generate_org_report("Unit Head"),
)

st.divider()


# --- 1) Customer-reported errors (raised / open by severity + share) -----
st.subheader("Customer-reported errors")
st.caption("Per customer: tickets raised, how many are still unresolved (by "
           "severity), and each customer's share of reported issues.")
cis = analytics.get_customer_issue_status()
if unit != "All units":
    cis = [r for r in cis if r["unit"] == unit]
cisdf = pd.DataFrame(cis)
if cisdf.empty:
    st.info("No customer tickets.")
else:
    SEV_ORDER = ["low", "medium", "high", "critical"]
    SEV_COLORS = {"low": "#2ecc71", "medium": "#f39c12",
                  "high": "#e67e22", "critical": "#e74c3c"}
    raised_by_cust = cisdf.groupby("customer")["raised"].sum().reset_index()
    g1, g2, g3 = st.columns(3)
    with g1:
        st.plotly_chart(px.bar(
            cisdf, x="customer", y="raised", color="severity",
            category_orders={"severity": SEV_ORDER}, color_discrete_map=SEV_COLORS,
            title="Raised", labels={"raised": "Tickets raised", "customer": "Customer"},
        ), width="stretch")
    with g2:
        st.plotly_chart(px.bar(
            cisdf, x="customer", y="open_count", color="severity",
            category_orders={"severity": SEV_ORDER}, color_discrete_map=SEV_COLORS,
            title="Still open (unresolved)",
            labels={"open_count": "Tickets still open", "customer": "Customer"},
        ), width="stretch")
    with g3:
        st.plotly_chart(px.pie(
            raised_by_cust, names="customer", values="raised",
            title="Share of issues", hole=0.4,
        ), width="stretch")
    hc = (cisdf[cisdf["severity"].isin(["high", "critical"])]
          .groupby("customer")["raised"].sum())
    st.caption("High/critical issues per customer: " +
               (", ".join(f"{c} ({int(n)})" for c, n in hc.items()) or "none"))

# --- 2) Code-quality bar graph (with team size) --------------------------
st.subheader("Code quality by team")
st.caption("Quality score = 100 − quality risk. Bar labels show team size (people).")
qdf = pd.DataFrame([{
    "module": r["module"],
    "quality_score": round(100 - r["breakdown"]["quality_risk"], 1),
    "team_size": r["team_size"],
    "risk_level": r["risk_level"],
} for r in view]).sort_values("quality_score")
fig_q = px.bar(
    qdf, x="module", y="quality_score", color="risk_level",
    color_discrete_map=ui.RISK_COLORS, text="team_size",
    labels={"quality_score": "Code quality (0-100)", "module": "Team / Module",
            "risk_level": "Risk"},
)
fig_q.update_traces(texttemplate="👥 %{text}", textposition="outside")
fig_q.update_layout(yaxis_range=[0, 100])
st.plotly_chart(fig_q, width="stretch")

# --- 3) Punctuality per team ---------------------------------------------
st.subheader("Punctuality — average days late vs plan")
punc = analytics.get_punctuality_by_module()
if unit != "All units":
    keep = {r["module"] for r in view}
    punc = [p for p in punc if p["module"] in keep]
pdf = pd.DataFrame(punc)
fig_p = px.bar(
    pdf, x="module", y="avg_days_late", text="avg_days_late",
    color="avg_days_late", color_continuous_scale="OrRd",
    labels={"avg_days_late": "Avg days late", "module": "Team / Module"},
)
fig_p.update_traces(textposition="outside")
st.plotly_chart(fig_p, width="stretch")
