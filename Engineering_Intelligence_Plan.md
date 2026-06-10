# Engineering Intelligence Copilot
## Final Project Plan — MVP

---

## Project Overview

Engineering Intelligence Copilot is an AI-powered management assistant that consolidates
engineering activity across repositories and generates executive reports, risk assessments,
trend analysis, and actionable recommendations — all from a single dashboard.

The system is designed to help an engineering manager quickly identify:

- Which teams are performing well and which need intervention
- Why quality or delivery is deteriorating (with specific signals, not just summaries)
- What concrete actions to take

This MVP uses **fabricated per-PR synthetic data**, SQLite, an analytics engine, a
risk-scoring engine, a local LLM running on vLLM + ROCm, and a Streamlit dashboard.
No Git, GitHub, GitLab, or CI integrations are included — those are future enhancements.

---

## Elevator Pitch

Engineering Intelligence Copilot is an AI-powered engineering management platform that
consolidates software delivery and quality signals, identifies team risk, analyzes health
trends, and generates executive-ready recommendations using a fully local LLM deployment
on AMD GPU hardware.

---

## Architecture

```
generate_data.py   (fabricates all synthetic PR events)
        ↓
engineering.db     (SQLite — 8 teams, 12 weeks of history)
        ↓               ↓
analytics.py  →  risk_engine.py       (compute metrics + risk scores)
        ↓                   ↓
llm_service.py          Streamlit pages 1 & 2
(calls vLLM → Qwen2.5-7B-Instruct)
        ↓
Streamlit pages 3 & 4   (AI reports + management copilot chat)
```

### Deliberately Excluded from MVP

These can be added later but are not needed to demonstrate the core idea:

- GitHub / GitLab integration
- Jenkins / CI pipeline integration
- Jira integration
- Real webhook / event triggers
- Knowledge graph
- MCP servers
- Vector databases
- Multi-agent frameworks

---

## Tech Stack — Final Decisions

| Concern | Choice | Reason |
|---|---|---|
| Dashboard | **Streamlit** | Python-native, no frontend work, charts in 3 lines |
| Charts | **Plotly Express** via `st.plotly_chart` | Native Streamlit support, interactive by default |
| Database | **SQLite** | Zero config, perfect for MVP scale |
| LLM model | **Qwen2.5-7B-Instruct** | Reliable on ROCm, fast enough for demo, fits in VRAM safely |
| Inference server | **vLLM** (OpenAI-compatible API) | Straightforward HTTP calls, easy to swap model later |
| Hardware | **AMD GPU via ROCm** | As specified |
| HTTP client | **httpx** | Async-capable, simple API |

> **Why 7B and not 14B?** The 14B model on ROCm can be unpredictable in a 2-day timeline —
> load times, VRAM pressure, and quantization issues can eat hours. The 7B delivers
> good-quality management prose at 2–5× the speed. Upgrade after the demo if needed.

---

## Project Structure

```
engineering-copilot/
│
├── app.py                  # Streamlit entrypoint + sidebar navigation
├── generate_data.py        # Run once to seed engineering.db
├── database.py             # SQLite connection + raw query helpers
├── analytics.py            # All metric computation (health, trends, org summary)
├── risk_engine.py          # Risk score + risk level per team
├── llm_service.py          # vLLM HTTP client + prompt builder
│
├── pages/
│   ├── 01_overview.py      # Executive overview: org KPIs, team rankings
│   ├── 02_teams.py         # Team drill-down: metrics + trend charts
│   ├── 03_reports.py       # AI report generator (per team or org-wide)
│   └── 04_copilot.py       # Management copilot: natural language chat
│
├── prompts/
│   ├── team_report.txt     # Prompt template for team-level reports
│   ├── org_report.txt      # Prompt template for org-wide reports
│   └── copilot.txt         # System prompt for chat interface
│
├── data/
│   └── engineering.db      # Generated SQLite database
│
└── requirements.txt
```

### requirements.txt

```
streamlit
plotly
pandas
httpx
faker
```

---

## Database Design

### Why Per-PR Events (Not Weekly Aggregates)

The original weekly aggregate schema loses all per-PR signal. Without it, the LLM can
only say "warnings went up this week" — with it, the LLM can say "PR #47 introduced
23 new clang warnings, all in `auth/session.c`." Weekly summaries are computed via a
SQL view on top of the event table.

### teams

```sql
CREATE TABLE teams (
    id      INTEGER PRIMARY KEY,
    name    TEXT,
    manager TEXT,
    product TEXT
);
```

Example teams: Networking, Auth, Security, Platform, Cloud, ML Pipeline, Backend, UI/UX

### repositories

```sql
CREATE TABLE repositories (
    id      INTEGER PRIMARY KEY,
    team_id INTEGER,
    name    TEXT
);
```

Each team has 2–3 repos. Example: `5g-core`, `auth-service`, `web-ui`, `telemetry`, `scheduler`

### pr_events — the core table

```sql
CREATE TABLE pr_events (
    id          INTEGER PRIMARY KEY,
    pr_id       TEXT,           -- e.g. 'NET-PR-047'
    repo_id     INTEGER,
    team_id     INTEGER,
    week        TEXT,           -- 'W01' through 'W12'

    -- Build
    build_success           INTEGER,  -- 1 or 0
    compile_warnings        INTEGER,

    -- Static analysis
    clang_warnings          INTEGER,
    codechecker_findings    INTEGER,
    codechecker_critical    INTEGER,

    -- Runtime checks
    asan_failures           INTEGER,

    -- Integration tests
    integration_total       INTEGER,
    integration_failed      INTEGER,

    -- Code review
    review_comments         INTEGER,
    review_latency_hours    REAL,
    reviewer_count          INTEGER,

    -- Business
    client_complaints       INTEGER,
    lines_changed           INTEGER
);
```

### weekly_summary — computed view

```sql
CREATE VIEW weekly_summary AS
SELECT
    week,
    team_id,
    COUNT(*)                                                AS prs_merged,
    ROUND(100.0 * SUM(build_success) / COUNT(*), 1)        AS build_success_rate,
    SUM(clang_warnings)                                     AS total_clang_warnings,
    ROUND(SUM(clang_warnings) * 1.0 / COUNT(*), 1)         AS avg_clang_warnings_per_pr,
    SUM(asan_failures)                                      AS total_asan_failures,
    SUM(integration_failed)                                 AS integration_failures,
    ROUND(100.0 * SUM(integration_failed) /
          NULLIF(SUM(integration_total), 0), 1)             AS integration_fail_pct,
    ROUND(AVG(review_latency_hours), 1)                    AS avg_review_latency,
    ROUND(AVG(reviewer_count), 1)                          AS avg_reviewers,
    SUM(client_complaints)                                  AS client_complaints
FROM pr_events
GROUP BY week, team_id;
```

---

## Synthetic Data Strategy

Generate ~8 PRs per team per week over 12 weeks. Each team follows a clear storyline
so the LLM has meaningful trends to report on — not random noise.

### Team Storylines

| Team | Trend | Key signals |
|---|---|---|
| **Networking** | Deteriorating fast | Build success: 94% → 78%, clang warnings ~doubling each month, client complaints rising |
| **Auth** | Critical | ASAN failures on every other PR, frequent integration failures, build often fails |
| **Security** | Improving | Warnings halving week-over-week, build stable at 96%+, review participation high |
| **Platform** | Rock solid | Best scores org-wide, low latency, consistent metrics |
| **Cloud** | Tech debt creeping | Build stable but warnings +5% per week, review latency slowly rising |
| **ML Pipeline** | Volatile | New team, inconsistent metrics, high review latency |
| **Backend** | Steady | Average everything, dependable, no alarms |
| **UI/UX** | Slight decline | Review latency climbing, fewer review comments, build slipping |

### Example: Networking Team Weekly Data

| Week | Build Success | Clang Warnings | ASAN Failures | Client Complaints |
|---|---|---|---|---|
| W01 | 94% | 18 | 0 | 0 |
| W04 | 88% | 34 | 1 | 1 |
| W08 | 83% | 67 | 2 | 3 |
| W12 | 78% | 118 | 4 | 5 |

### generate_data.py Approach

```python
import sqlite3, random
from faker import Faker

fake = Faker()

TEAM_CONFIGS = {
    "Networking": {
        "build_success_start": 0.94, "build_success_end": 0.78,
        "clang_start": 18,           "clang_end": 118,
        "asan_rate": 0.10,           "complaint_rate": 0.20,
    },
    "Auth": {
        "build_success_start": 0.85, "build_success_end": 0.72,
        "clang_start": 30,           "clang_end": 80,
        "asan_rate": 0.40,           "complaint_rate": 0.30,
    },
    "Security": {
        "build_success_start": 0.88, "build_success_end": 0.97,
        "clang_start": 60,           "clang_end": 12,
        "asan_rate": 0.01,           "complaint_rate": 0.01,
    },
    # ... other teams
}

def lerp(start, end, t):
    """Linear interpolate between start and end; t in [0, 1]."""
    return start + (end - start) * t

def generate_pr(team_name, week_idx, team_id, repo_id, pr_num):
    cfg = TEAM_CONFIGS[team_name]
    t = week_idx / 11  # normalised week position
    build_prob = lerp(cfg["build_success_start"], cfg["build_success_end"], t)
    clang_base = lerp(cfg["clang_start"], cfg["clang_end"], t)

    return {
        "pr_id": f"{team_name[:3].upper()}-PR-{pr_num:04d}",
        "repo_id": repo_id,
        "team_id": team_id,
        "week": f"W{week_idx+1:02d}",
        "build_success": 1 if random.random() < build_prob else 0,
        "clang_warnings": max(0, int(random.gauss(clang_base, clang_base * 0.15))),
        "codechecker_findings": max(0, int(random.gauss(clang_base * 0.4, 3))),
        "codechecker_critical": max(0, int(random.gauss(clang_base * 0.05, 1))),
        "asan_failures": 1 if random.random() < cfg["asan_rate"] else 0,
        "integration_total": random.randint(40, 80),
        "integration_failed": random.randint(0, 5) if build_prob > 0.85 else random.randint(3, 12),
        "review_comments": max(1, int(random.gauss(8, 3))),
        "review_latency_hours": max(1, random.gauss(24, 8)),
        "reviewer_count": random.randint(1, 4),
        "client_complaints": 1 if random.random() < cfg["complaint_rate"] else 0,
        "lines_changed": random.randint(50, 800),
    }
```

---

## Analytics Engine

`analytics.py` transforms raw PR events into actionable metrics for the dashboard and LLM.

### Functions

```python
def get_org_summary(db) -> dict:
    """High-level org health: team counts, average build rate, top risk team."""

def get_team_health(db, team_id: int, weeks: int = 4) -> dict:
    """Aggregate metrics for a team over the last N weeks."""

def get_team_trends(db, team_id: int) -> list[dict]:
    """Week-by-week metric history for trend charts."""

def compare_teams(db, team_a_id: int, team_b_id: int) -> dict:
    """Side-by-side comparison of two teams."""

def get_all_team_rankings(db) -> list[dict]:
    """All teams ranked by risk score, with health level."""
```

### Metrics Computed

**Delivery**
- PR velocity (PRs merged per week)
- Build success rate
- Release frequency (optional)

**Quality**
- Clang warning trend (week-over-week delta)
- CodeChecker findings trend
- ASAN failure rate
- Integration test failure rate

**Collaboration**
- Average review latency (hours)
- Average reviewer count per PR
- Review comment density

**Business**
- Client complaints per week
- Escaped defect rate

---

## Risk Engine

`risk_engine.py` combines multiple dimensions into a single normalised risk score.
All intermediate values are normalised to 0–100 before weighting, so dimensions
are dimensionally consistent.

```python
def compute_team_risk(m: dict) -> dict:
    """
    m: dict from analytics.get_team_health()
    Returns: {'score': float, 'level': str, 'breakdown': dict}
    """

    # Quality risk (0–100)
    warning_score = min(m['avg_clang_warnings_per_pr'] * 3, 100)
    asan_score    = min(m['avg_asan_per_pr'] * 25, 100)
    integ_score   = min(m['integration_fail_pct'] * 1.5, 100)
    quality_risk  = 0.40 * warning_score + 0.35 * asan_score + 0.25 * integ_score

    # Delivery risk (0–100): directly the build failure rate
    delivery_risk = 100 - m['build_success_rate']

    # Collaboration risk (0–100): latency normalised to a 48-hour ceiling
    # Note: review_latency and reviewer_count are kept separate —
    # never subtract a count from a duration.
    latency_norm  = min(m['avg_review_latency_hours'] / 48 * 100, 100)
    reviewer_pen  = max(0, (3 - m['avg_reviewers']) * 15)  # penalty if avg < 3 reviewers
    collab_risk   = min(latency_norm * 0.7 + reviewer_pen * 0.3, 100)

    # Weighted final score
    risk_score = (
        0.50 * quality_risk +
        0.30 * delivery_risk +
        0.20 * collab_risk
    )

    level = (
        'GREEN' if risk_score < 30 else
        'AMBER' if risk_score < 60 else
        'RED'
    )

    return {
        'score': round(risk_score, 1),
        'level': level,
        'breakdown': {
            'quality_risk':  round(quality_risk, 1),
            'delivery_risk': round(delivery_risk, 1),
            'collab_risk':   round(collab_risk, 1),
        }
    }
```

### Risk Levels

| Score | Level | Meaning |
|---|---|---|
| 0 – 29 | GREEN | Healthy, no action needed |
| 30 – 59 | AMBER | Watch closely, consider intervention |
| 60 – 100 | RED | Immediate attention required |

---

## Dashboard Pages (Streamlit)

### app.py — Entry Point

```python
import streamlit as st

st.set_page_config(
    page_title="Engineering Intelligence Copilot",
    page_icon="🔬",
    layout="wide",
)

st.sidebar.title("Engineering Copilot")
page = st.sidebar.selectbox(
    "Navigate",
    ["Executive Overview", "Team Explorer", "AI Reports", "Management Copilot"]
)
```

### Page 1: Executive Overview

**What it shows:**

- KPI cards: Healthy teams / Warning teams / Critical teams / Avg build success
- Team health table ranked by risk score, with colour-coded risk badges
- Org-level bar chart: risk score per team
- Callout: highest-risk team + fastest-improving team

```python
# Key Streamlit patterns for this page
col1, col2, col3, col4 = st.columns(4)
col1.metric("Healthy Teams", healthy_count)
col2.metric("Warning Teams", warning_count, delta=f"{delta} vs last week")
col3.metric("Critical Teams", critical_count)
col4.metric("Avg Build Success", f"{avg_build:.1f}%")

st.dataframe(
    rankings_df.style.applymap(colour_risk, subset=["Risk Level"]),
    use_container_width=True
)
```

### Page 2: Team Explorer

**What it shows:**

- Team selector (dropdown)
- 4 metric cards: Quality Score, Delivery Score, Collaboration Score, Risk Score
- Line chart: build success rate over 12 weeks
- Line chart: clang warnings over 12 weeks
- Bar chart: integration failures over 12 weeks
- Risk breakdown (quality / delivery / collaboration sub-scores)

```python
team_name = st.selectbox("Select team", team_names)
trend_df  = analytics.get_team_trends(db, team_id)

st.plotly_chart(
    px.line(trend_df, x="week", y="build_success_rate",
            title="Build Success Rate", markers=True),
    use_container_width=True
)
```

### Page 3: AI Executive Reports

**What it shows:**

- Report scope selector: individual team or entire org
- "Generate Report" button (triggers LLM call)
- Rendered markdown report with spinner while loading

```python
scope = st.radio("Report scope", ["Team Report", "Org-wide Report"])
if scope == "Team Report":
    team = st.selectbox("Team", team_names)

if st.button("Generate Report"):
    with st.spinner("Generating executive report..."):
        context = analytics.get_team_health(db, team_id)
        risk    = risk_engine.compute_team_risk(context)
        report  = llm_service.generate_team_report(context, risk)
    st.markdown(report)
```

### Page 4: Management Copilot

**What it shows:**

- Chat input box
- Conversation history
- Each user message injects current org context into the LLM prompt

```python
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).markdown(msg["content"])

if prompt := st.chat_input("Ask about your engineering org..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    context = analytics.get_org_summary(db)
    response = llm_service.chat(prompt, context, st.session_state.messages)
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()
```

**Example questions the copilot should handle:**
- "Which team should I focus on this week?"
- "Why is the Networking team deteriorating?"
- "Compare Platform and Cloud."
- "What are the top 3 engineering concerns right now?"
- "Is the Auth situation getting better or worse?"

---

## LLM Integration

### vLLM Setup on ROCm + AMD GPU

```bash
# Install
pip install vllm

# Start the server — run this FIRST THING on Day 2
# The model download alone (~15 GB) can take 20–40 minutes
ROCR_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-7B-Instruct \
    --port 8000 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.85 \
    --trust-remote-code

# Verify it's up
curl http://localhost:8000/health
```

> **If VRAM allows (>28 GB):** swap `Qwen2.5-7B-Instruct` for `Qwen2.5-14B-Instruct`
> for higher-quality reports. The code is identical — just change the model string.

### llm_service.py

```python
import httpx

VLLM_URL = "http://localhost:8000/v1/chat/completions"
MODEL    = "Qwen/Qwen2.5-7B-Instruct"

def _call(messages: list[dict], max_tokens: int = 600) -> str:
    r = httpx.post(VLLM_URL, json={
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }, timeout=60.0)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def generate_team_report(team_metrics: dict, risk: dict) -> str:
    with open("prompts/team_report.txt") as f:
        template = f.read()

    context_json = {
        "team":                  team_metrics["name"],
        "risk_score":            risk["score"],
        "risk_level":            risk["level"],
        "build_success_rate":    team_metrics["build_success_rate"],
        "avg_clang_warnings":    team_metrics["avg_clang_warnings_per_pr"],
        "asan_failures":         team_metrics["total_asan_failures"],
        "integration_fail_pct":  team_metrics["integration_fail_pct"],
        "avg_review_latency_hrs": team_metrics["avg_review_latency"],
        "client_complaints":     team_metrics["client_complaints"],
        "warning_trend":         team_metrics["clang_warning_trend"],  # '+38%' or '-12%'
    }

    prompt = template.format(context=context_json)
    return _call([{"role": "user", "content": prompt}], max_tokens=800)


def chat(user_message: str, org_context: dict, history: list[dict]) -> str:
    with open("prompts/copilot.txt") as f:
        system_prompt = f.read().format(context=org_context)

    messages = [{"role": "system", "content": system_prompt}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    messages += [{"role": "user", "content": user_message}]

    return _call(messages, max_tokens=500)
```

### Prompt Strategy — Never Send Raw Rows

Always summarise analytics output into a structured JSON context block before sending
to the LLM. Raw database rows waste tokens, degrade output quality, and hit context limits.

**Bad:**
```
1000 rows of pr_events data...
```

**Good:**
```json
{
  "team": "Networking",
  "risk_score": 82,
  "risk_level": "RED",
  "build_success_rate": 78,
  "avg_clang_warnings_per_pr": 24.6,
  "warning_trend": "+38% over 4 weeks",
  "asan_failures": 4,
  "integration_fail_pct": 18.2,
  "avg_review_latency_hrs": 31.4,
  "client_complaints": 5
}
```

### prompts/team_report.txt

```
You are an Engineering Director writing a management report.

Team context:
{context}

Write a concise executive report with exactly these four sections:

## Executive Summary
2-3 sentences. State the team's overall health and the single most important risk.

## Key Risks
List 3–4 specific risks with supporting numbers from the context.

## Root Causes
What is likely driving the degradation? Be specific.

## Recommended Actions
3–4 concrete, prioritised actions the manager should take this week.

Be direct. Use numbers. No filler sentences.
```

### prompts/copilot.txt

```
You are an AI engineering management copilot assisting a senior engineering director.

Current organisation context:
{context}

Answer questions concisely and with specific data from the context.
If asked to compare teams, use numbers. If asked for recommendations, be concrete.
Do not make up data that is not in the context. If something is unknown, say so.
```

---

## Two-Day Implementation Plan

### Day 1 — Data + Analytics + Dashboard (Goal: data → charts working end-to-end)

| Time | Task | Done when |
|---|---|---|
| Hour 0–1 | Project setup: create folder structure, install deps, write SQLite schema, init `engineering.db` | `engineering.db` exists with all tables and view |
| Hour 1–3 | Write `generate_data.py` with all 8 team storylines using lerp-based trend generation | DB has ~8 teams × 12 weeks × 8 PRs = ~768 PR event rows |
| Hour 3–5 | Write `analytics.py`: `get_team_health()`, `get_team_trends()`, `get_org_summary()`, `compare_teams()` | Functions return correct dicts, manually spot-checked in a Python shell |
| Hour 5–6 | Write `risk_engine.py` with corrected formula | Each team shows a plausible GREEN / AMBER / RED and score |
| Hour 6–9 | Build Streamlit pages 1 (overview) and 2 (team explorer) with charts | Dashboard loads, KPI cards correct, trend charts render, team dropdown works |
| Hour 9–10 | End-to-end check: run `generate_data.py` → open dashboard → verify all charts | No errors in console, charts show expected storyline trends |

### Day 2 — LLM + Reports + Chat (Goal: full 4-page demo-ready app)

| Time | Task | Done when |
|---|---|---|
| **Hour 0** | **FIRST: start vLLM server + model download. Do this before writing any code.** | `curl localhost:8000/health` returns 200 |
| Hour 1–2 | Write `llm_service.py`, `prompts/team_report.txt`, `prompts/copilot.txt` | Test call from Python shell returns coherent text |
| Hour 2–5 | Build page 3 (AI Reports): team/org selector, generate button, spinner, rendered output | Full Networking team report generates in < 30s |
| Hour 5–7 | Build page 4 (Management Copilot): chat input, message history, context injection | "Which team is at risk?" returns a correct, data-grounded answer |
| Hour 7–9 | Polish: loading spinners, LLM timeout handling (`try/except`), clean up chart titles and labels | No crashes during a full demo run |
| Hour 9–10 | Write demo script, prepare PPT, rehearse the 5-minute walkthrough | You know exactly what to click in what order |

### Day 2 Risk: vLLM Startup Time

The model download is ~15 GB and can take 20–40 minutes on a slow connection.
**Start it the night before Day 2** if possible. Everything else on Day 2 can be
written while the model is loading — `llm_service.py` and the prompt templates do
not require the server to be running.

---

## Future Enhancements

These are intentionally excluded from the MVP but are the natural next steps:

**Real data integrations**
- GitHub / GitLab webhooks — trigger the agent on actual PR merges
- CI/CD log ingestion — parse real clang-tidy YAML, CodeChecker JSON, ASAN stack traces, JUnit XML
- Jira integration — link issues to code quality signals

**Infrastructure**
- PostgreSQL — replace SQLite when multiple concurrent users hit the dashboard
- Redis — cache LLM report outputs so they do not regenerate on every page load
- Celery / background jobs — run report generation asynchronously

**Intelligence**
- Knowledge graph — link teams, engineers, repos, and incidents
- Vector database — semantic search over historical reports and PR comments
- Multi-agent framework — separate agents for data collection, analysis, and report generation
- Anomaly detection — flag sudden spikes before they become RED

**LLM upgrades**
- Upgrade to `Qwen2.5-14B-Instruct` or `Qwen2.5-32B-Instruct` once validated on ROCm
- Fine-tune on internal engineering report examples for domain-specific language
- Streaming output — pipe LLM tokens directly to the Streamlit chat interface

---

*Plan version: final — incorporates corrected schema (per-PR events + weekly view),
fixed risk formula (dimensionally consistent), Streamlit dashboard, vLLM + Qwen2.5-7B,
and hour-by-hour 2-day schedule.*
