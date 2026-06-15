"""Federated ingestion architecture (API_GATEWAY_DECISION showcase).

Shows the flow: local edge agents -> API gateway -> central staging DB. Three
projects are pre-loaded; the 5G Core Rollout agent ingests live through the real
gateway when you click "Run agent".
"""

import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."))

import httpx
import streamlit as st

from aura import config
from aura.data import database
from aura.ingestion import edge_agent
from aura.data import repository
from aura import ui

st.set_page_config(page_title="Architecture", page_icon="🛰️", layout="wide")
ui.require_db()

st.title("🛰️ Federated Ingestion Architecture")
st.caption(
    "Local edge agents → API gateway → central staging DB. Three projects are "
    "pre-loaded; the **5G Core Rollout** agent ingests **live** through the real gateway."
)


def gateway_get(path):
    try:
        r = httpx.get(f"{config.GATEWAY_URL}{path}", timeout=2)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# Loaded projects + counts come straight from the DB (always available), so the
# board is correct even when the gateway is offline. The gateway is only used for
# the online/offline badge and the actual ingest POST.
def db_stats():
    def n(table):
        return database.query(f"SELECT COUNT(*) AS c FROM {table}")[0]["c"]
    return {
        "verticals": n("vertical_units"), "accounts": n("accounts"),
        "projects": n("projects"), "modules": n("modules"),
        "commits": n("commits"), "jira_logs": n("jira_logs"),
        "project_names": [r["name"] for r in
                          database.query("SELECT name FROM projects ORDER BY id")],
    }


stats = db_stats()
present = set(stats["project_names"])
online = gateway_get("/healthz") is not None

LIVE_KEY = "proj_ran_5g"
AGENTS = [
    {"project": "5G Core Rollout", "account": "GlobalTel Wireless", "key": LIVE_KEY, "live": True},
    {"project": "Edge Computing Layer", "account": "GlobalTel Wireless", "key": "proj_edge_comp", "live": False},
    {"project": "Instant Payments Core", "account": "Nexus Digital Bank", "key": "proj_pay_core", "live": False},
    {"project": "Wealth Management APIs", "account": "Nexus Digital Bank", "key": "proj_wealth_api", "live": False},
]

# ── 1. Edge agents ───────────────────────────────────────────────────────
st.subheader("① Local edge agents")
cols = st.columns(len(AGENTS))
for col, a in zip(cols, AGENTS):
    loaded = a["project"] in present
    with col:
        st.markdown(f"**🛰️ {a['project']}**")
        st.caption(a["account"])
        if a["live"] and loaded:
            st.success("ingested ✓")
        elif a["live"]:
            st.warning("pending — run it →")
        elif loaded:
            st.success("pre-loaded ✓")
        else:
            st.info("not loaded")

st.markdown("<div style='text-align:center;font-size:1.5rem'>⬇️ &nbsp; POST /ingest/project</div>",
            unsafe_allow_html=True)

# ── 2. API gateway ───────────────────────────────────────────────────────
st.subheader("② API gateway")
if online:
    st.success(f"🟢 Gateway online — `{config.GATEWAY_URL}`")
else:
    st.error(
        f"🔴 Gateway offline (`{config.GATEWAY_URL}`). Start it from the project root:\n\n"
        "```\npython -m aura.ingestion.gateway\n```"
    )

# Live-agent trigger
live_loaded = "5G Core Rollout" in present
if live_loaded:
    st.success("5G Core Rollout is ingested into central staging. 🎉")
    if edge_agent.has_source(LIVE_KEY):
        st.caption("Demo control — put it back so you can ingest again:")
        if st.button("↺ Reset demo (hold 5G Core back)"):
            repository.remove_project(LIVE_KEY)
            st.cache_data.clear()
            st.rerun()
elif not edge_agent.has_source(LIVE_KEY):
    st.info("No held-back source bundle found (seeded with `--full`?). Nothing to ingest.")
else:
    disabled = not online
    if st.button("▶ Run 5G Core Rollout edge agent", type="primary", disabled=disabled):
        try:
            res = edge_agent.forward(LIVE_KEY)
            st.success(
                f"Ingested **{res['project']}** → {res['modules']} modules, "
                f"{res['commits']} commits, {res['jira_logs']} tickets staged."
            )
            st.cache_data.clear()   # bust cached analytics so dashboards refresh
            st.rerun()
        except Exception as e:
            st.error(f"Ingestion failed: {e}")
    if disabled:
        st.caption("Start the gateway first (see above).")

st.markdown("<div style='text-align:center;font-size:1.5rem'>⬇️ &nbsp; write</div>",
            unsafe_allow_html=True)

# ── 3. Central staging DB ────────────────────────────────────────────────
st.subheader("③ Central staging DB")
c = st.columns(6)
c[0].metric("Verticals", stats["verticals"])
c[1].metric("Accounts", stats["accounts"])
c[2].metric("Projects", stats["projects"])
c[3].metric("Modules", stats["modules"])
c[4].metric("Commits", stats["commits"])
c[5].metric("Tickets", stats["jira_logs"])
