"""Unit Head view — non-technical, org-wide health.

Code-quality bar graph (with team size), punctuality per team, and errors
reported per customer. Business framing; no per-commit detail.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

import analytics
import ui

st.set_page_config(page_title="Unit Head", page_icon="🏢", layout="wide")
ui.require_db()

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
c3.metric("🔴 Critical", sum(1 for r in view if r["risk_level"] == "RED"))
c4.metric("Avg Build Success",
          f"{(sum(r['build_success_rate'] for r in view) / len(view)):.1f}%")

st.divider()

# --- 1) Code-quality bar graph (with team size) --------------------------
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

# --- 2) Punctuality per team ---------------------------------------------
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

# --- 3) Errors reported per customer -------------------------------------
st.subheader("Customer-reported errors")
impact = analytics.get_customer_impact()
idf = pd.DataFrame(impact)
ec1, ec2 = st.columns(2)
with ec1:
    fig_c = px.bar(
        idf, x="customer", y="issues", text="issues", color="customer",
        labels={"issues": "Issues reported", "customer": "Customer"},
    )
    fig_c.update_traces(textposition="outside")
    fig_c.update_layout(showlegend=False)
    st.plotly_chart(fig_c, width="stretch")
with ec2:
    fig_pie = px.pie(idf, names="customer", values="issues",
                     title="Share of reported issues", hole=0.4)
    st.plotly_chart(fig_pie, width="stretch")
st.caption("High/critical issues per customer: " +
           ", ".join(f"{r['customer']} ({r['high_critical']})" for r in impact))
