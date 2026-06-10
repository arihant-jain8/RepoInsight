# Engineering Intelligence Copilot
## Final Project Plan — MVP

---

## Project Overview

Engineering Intelligence Copilot is an AI-powered management assistant that consolidates
engineering activity across a **unit → project → module → commit** hierarchy and generates
**role-based** intelligence — executive reports, risk assessments, trend analysis,
punctuality scoring, customer-issue traceability, and actionable recommendations — all from a
single dashboard backed by one central database.

The system is built around the idea from `arch.md`: each **module** is owned by a team and has
its own git repository, and a per-module **ingestion agent** pushes that module's commits,
owners, reviewers, and review comments into a **central database**. Analytics, a risk engine,
and a local LLM then turn that raw activity into answers tailored to three audiences:

- **Unit Head** — non-technical, org-wide health, punctuality, customer impact
- **Project Manager** — their project only: delivery, per-module comments, customer→commit tracing
- **Team Lead** — deeply technical, per-commit drill-down on quality and review signals

This MVP uses **fabricated but git-shaped synthetic data**, SQLite, an analytics engine, a
risk-scoring engine, a pluggable local LLM, and a Streamlit dashboard. Real git/GitHub, CI, and
issue-tracker integrations are designed-for but deferred — the schema is shaped so a real git
ingestion worker drops in later with no schema change.

---

## Elevator Pitch

Engineering Intelligence Copilot consolidates software delivery and quality signals from every
module's repository into one central database, scores team risk and punctuality, traces customer
issues back to the exact commit that caused them, and generates role-based, executive-ready
recommendations using a fully local, swappable LLM deployment.

---

## Architecture

```
repo: backend   ─ agent(backend)  ┐
repo: frontend  ─ agent(frontend) ├─→  engineering.db  (central, SQLite)
repo: ai        ─ agent(ai)       │         │
repo: network   ─ agent(network)  ┘         ├─ analytics.py + risk_engine.py
                                            │     (metrics, risk, punctuality,
                                            │      per-customer + customer→commit trace)
                                            │
                                            ├─ llm_service.py  (pluggable LLM:
                                            │   Ollama local now → vLLM/Qwen on AMD later)
                                            │
                                            └─ Streamlit — role-based pages:
                                                 Unit Head · Project Manager · Team Lead
                                                 + AI Reports + Management Copilot
```

> For the MVP the "agents" are simulated by `generate_data.py`, which fabricates git-shaped data
> directly into the central DB. The real per-module ingestion workers (`ingest.py`) are the
> documented drop-in — same target schema, real data source.

### Deliberately Excluded from MVP (designed-for, deferred)

- Real GitHub / GitLab ingestion (schema is git-ready; worker is the drop-in)
- Jenkins / CI log parsing (build/clang/ASAN/integration stay synthetic until then)
- Jira / issue-tracker integration (customer DB + targeted delivery stay synthetic until then)
- Real webhook / event triggers (MVP uses batch backfill)
- Knowledge graph, vector databases, heavyweight multi-agent frameworks

---

## Tech Stack — Final Decisions

| Concern | Choice | Reason |
|---|---|---|
| Dashboard | **Streamlit** | Python-native, no frontend work, charts in 3 lines |
| Charts | **Plotly Express** via `st.plotly_chart` | Native Streamlit support, interactive by default |
| Database | **SQLite** — single central file `data/engineering.db` via `sqlite3` | Zero config; the one "central database" all module agents write into; perfect for MVP scale |
| DB scale-path | **PostgreSQL** (future) | Swap only `database.py` when concurrent users / larger data demand it |
| Repo layout | **Multi-repo** — one git repo per module | Matches arch.md: each module owned by a team, one ingestion agent per repo |
| Modules | **Generic** (backend / frontend / ai / network / …) | Not limited to cpp; a module is any owned codebase |
| Data source (MVP) | **Synthetic, git-shaped** | Fast to a working demo; schema is git-ready so real ingestion drops in later |
| LLM model (now) | **Small local model via Ollama** (e.g. `qwen2.5:3b` / `llama3.2:3b`) | Runs on this Windows PC, no AMD/ROCm setup needed |
| LLM model (later) | **Qwen2.5-7B-Instruct on vLLM + ROCm** | Higher-quality prose on the AMD machine; swap `base_url` + `model` only |
| Inference API | **OpenAI-compatible `/v1/chat/completions`** | Identical code for Ollama and vLLM |
| HTTP client | **httpx** | Async-capable, simple API |

> **Why pluggable LLM?** Ollama and vLLM both expose the OpenAI-compatible chat API, so the
> client code never changes. Develop locally against a small model; on the AMD/ROCm box, point
> `LLM_BASE_URL` at the vLLM server and set `LLM_MODEL` to `Qwen/Qwen2.5-7B-Instruct`. That's it.

---

## Project Structure

```
RepoInsight/
│
├── app.py                  # Streamlit entrypoint + sidebar / role selector
├── config.py               # LLM + DB config (model-swappable: Ollama now, vLLM later)
├── database.py             # SQLite connection + query helpers (single DB path)
├── schema.sql              # all table + view DDL
├── generate_data.py        # run once to seed the central engineering.db (simulates agents)
├── ingest.py               # (future) per-module git ingestion worker → central DB
├── analytics.py            # metric computation (rollups, punctuality, customer trace)
├── risk_engine.py          # risk score + level per module/project
├── llm_service.py          # OpenAI-compatible LLM client + role-aware prompt builder
│
├── pages/
│   ├── 01_unit_head.py        # Unit Head: non-technical, org-wide health
│   ├── 02_project_manager.py  # Project Manager: own project; delivery; customer→commit trace
│   ├── 03_team_lead.py        # Team Lead: technical per-commit drill-down
│   ├── 04_reports.py          # AI report generator (role-aware)
│   └── 05_copilot.py          # Management copilot: natural-language chat
│
├── prompts/
│   ├── team_report.txt     # prompt template for module/team reports
│   ├── org_report.txt      # prompt template for org-wide reports
│   └── copilot.txt         # system prompt for chat interface
│
├── data/
│   └── engineering.db      # generated central SQLite database
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
# when real ingestion lands: GitPython, requests
```

---

## Database Design

One central SQLite file (`data/engineering.db`) holding two logical groups of tables — an
**internal DB** (engineering activity) and a **customer DB** (support signals) — joined by
**`commit_id`** so any customer issue can be traced back to the commit that caused it.

### Why Per-Commit (git-ready) and a separate customer DB

`arch.md` requires commit-level granularity: a customer issue references a `commit-id`, and a
Team Lead must drill into individual commits (author, reviewer, comments, quality signals). A
PR-only or weekly-aggregate schema loses that. Modeling per-commit also makes the schema
**git-shaped** — a real ingestion worker can later fill `commit_id / author / reviewer / module /
review comments / actual delivery` straight from `git log` + the GitHub API with no schema change.

### Internal DB

```sql
-- Organisational hierarchy
CREATE TABLE units (
    id      INTEGER PRIMARY KEY,
    name    TEXT,
    head    TEXT            -- Unit Head (persona)
);

CREATE TABLE projects (
    id      INTEGER PRIMARY KEY,
    unit_id INTEGER,
    name    TEXT,
    manager TEXT            -- Project Manager (persona)
);

CREATE TABLE modules (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER,
    name        TEXT,       -- e.g. 'auth-service'
    type        TEXT,       -- generic: backend | frontend | ai | network | ...
    repo_url    TEXT,       -- multi-repo: each module = its own git repo
    team_lead   TEXT,       -- Team Lead (persona)
    team_size   INTEGER     -- people on the team (for Unit Head's team-size view)
);

CREATE TABLE engineers (
    id    INTEGER PRIMARY KEY,
    name  TEXT
);

-- Core commit table (one row per commit; git-ready)
CREATE TABLE commits (
    id                  INTEGER PRIMARY KEY,
    commit_id           TEXT,       -- SHA-like; join key for customer issues
    pr_id               TEXT,       -- nullable; git-ready (e.g. 'NET-PR-047')
    module_id           INTEGER,
    project_id          INTEGER,
    unit_id             INTEGER,
    week                TEXT,       -- 'W01'..'W12'
    committed_at        TEXT,       -- ISO timestamp

    author_id           INTEGER,
    reviewer_id         INTEGER,

    -- Delivery (for punctuality)
    targeted_delivery   TEXT,       -- planned date (synthetic / from planning tool later)
    actual_delivery     TEXT,       -- merge date (from git later)

    -- Build / CI (synthetic until CI integration)
    build_success           INTEGER,    -- 1 or 0
    compile_warnings        INTEGER,
    clang_warnings          INTEGER,
    codechecker_findings    INTEGER,
    codechecker_critical    INTEGER,
    asan_failures           INTEGER,
    integration_total       INTEGER,
    integration_failed      INTEGER,

    -- Review / collaboration
    review_latency_hours    REAL,
    lines_changed           INTEGER
);

-- Review comments as a first-class entity (NOT pre-aggregated counts)
CREATE TABLE review_comments (
    id          INTEGER PRIMARY KEY,
    commit_id   TEXT,       -- FK -> commits.commit_id
    reviewer_id INTEGER,
    comment     TEXT,       -- the comment itself
    severity    TEXT,       -- 'major' or 'minor'
    created_at  TEXT
);
```

> A commit has 0..N `review_comments` rows of mixed severity. Major/minor **counts** are derived
> with `GROUP BY severity` — never stored as columns. When real ingestion lands, comments come
> from PR review comments and severity from a label or heuristic.

### Customer DB

```sql
CREATE TABLE customers (
    id    INTEGER PRIMARY KEY,
    name  TEXT
);

CREATE TABLE customer_issues (
    id            INTEGER PRIMARY KEY,
    customer_id   INTEGER,
    project_id    INTEGER,
    module_id     INTEGER,
    commit_id     TEXT,         -- FK -> commits.commit_id  (which commit caused this issue)
    error_info    TEXT,
    severity      TEXT,         -- e.g. 'low' | 'medium' | 'high' | 'critical'
    report_time   TEXT,
    resolve_time  TEXT          -- nullable while open
);
```

### Views

```sql
-- Per module / week aggregates (rebuilt on the commits table)
CREATE VIEW weekly_summary AS
SELECT
    week,
    module_id,
    project_id,
    COUNT(*)                                                AS commits_merged,
    ROUND(100.0 * SUM(build_success) / COUNT(*), 1)        AS build_success_rate,
    SUM(clang_warnings)                                     AS total_clang_warnings,
    ROUND(SUM(clang_warnings) * 1.0 / COUNT(*), 1)         AS avg_clang_warnings_per_commit,
    SUM(asan_failures)                                      AS total_asan_failures,
    SUM(integration_failed)                                 AS integration_failures,
    ROUND(100.0 * SUM(integration_failed) /
          NULLIF(SUM(integration_total), 0), 1)             AS integration_fail_pct,
    ROUND(AVG(review_latency_hours), 1)                    AS avg_review_latency
FROM commits
GROUP BY week, module_id;

-- Punctuality: how late delivery was vs plan, per module
CREATE VIEW punctuality AS
SELECT
    module_id,
    project_id,
    COUNT(*)                                                          AS delivered,
    ROUND(AVG(julianday(actual_delivery) - julianday(targeted_delivery)), 1)
                                                                      AS avg_days_late
FROM commits
WHERE targeted_delivery IS NOT NULL AND actual_delivery IS NOT NULL
GROUP BY module_id;

-- Customer issue -> commit -> author/module lineage
CREATE VIEW customer_trace AS
SELECT
    ci.id            AS issue_id,
    cu.name          AS customer,
    ci.severity      AS issue_severity,
    ci.error_info,
    ci.commit_id,
    m.name           AS module,
    e.name           AS author
FROM customer_issues ci
JOIN customers  cu ON cu.id = ci.customer_id
LEFT JOIN commits   c  ON c.commit_id = ci.commit_id
LEFT JOIN modules   m  ON m.id = c.module_id
LEFT JOIN engineers e  ON e.id = c.author_id;
```

---

## Synthetic Data Strategy

`generate_data.py` simulates the per-module ingestion agents by fabricating git-shaped data
directly into the central DB. It keeps the **storyline + `lerp`** approach so the LLM has
meaningful trends, not noise.

Generate: units → projects → modules (each a repo, with a `team_lead` and `team_size`) →
engineers. Then, per module, ~8 **commits** per week over 12 weeks, each with:

- a SHA-like `commit_id`, an author and a reviewer
- a handful of `review_comments` rows (each its own `comment` text + `severity` major/minor)
- `targeted_delivery` vs `actual_delivery` — some modules slip (bad punctuality)
- synthetic build / clang / CodeChecker / ASAN / integration / review-latency signals trending
  along the module's storyline

Then generate 3 `customers` and a set of `customer_issues`, with a subset pointing at **real
generated `commit_id`s** in the worst-quality modules so the customer→commit traceability demo
lights up.

### Team / Module Storylines

| Module | Trend | Key signals |
|---|---|---|
| **Networking** | Deteriorating fast | Build 94% → 78%, clang warnings ~doubling/month, rising customer issues |
| **Auth** | Critical | ASAN on every other commit, frequent integration failures, build often fails |
| **Security** | Improving | Warnings halving week-over-week, build stable 96%+, high review participation |
| **Platform** | Rock solid | Best scores org-wide, low latency, on-time delivery |
| **Cloud** | Tech debt creeping | Build stable but warnings +5%/week, review latency rising |
| **ML Pipeline** | Volatile | New team, inconsistent metrics, high review latency, late delivery |
| **Backend** | Steady | Average everything, dependable |
| **UI/UX** | Slight decline | Review latency climbing, fewer comments, build slipping |

### Example: Networking module weekly trend

| Week | Build Success | Clang Warnings | ASAN Failures | Customer Issues |
|---|---|---|---|---|
| W01 | 94% | 18 | 0 | 0 |
| W04 | 88% | 34 | 1 | 1 |
| W08 | 83% | 67 | 2 | 3 |
| W12 | 78% | 118 | 4 | 5 |

### Approach (sketch)

```python
import sqlite3, random
from faker import Faker

fake = Faker()

MODULE_CONFIGS = {
    "Networking": {"build_start": 0.94, "build_end": 0.78,
                   "clang_start": 18, "clang_end": 118,
                   "asan_rate": 0.10, "issue_rate": 0.20, "late_days": 14},
    "Auth":       {"build_start": 0.85, "build_end": 0.72,
                   "clang_start": 30, "clang_end": 80,
                   "asan_rate": 0.40, "issue_rate": 0.30, "late_days": 10},
    "Security":   {"build_start": 0.88, "build_end": 0.97,
                   "clang_start": 60, "clang_end": 12,
                   "asan_rate": 0.01, "issue_rate": 0.01, "late_days": 0},
    # ... other modules
}

def lerp(a, b, t):
    """Linear interpolate; t in [0, 1]."""
    return a + (b - a) * t

def fake_sha():
    return "".join(random.choice("0123456789abcdef") for _ in range(12))
```

---

## Analytics Engine

`analytics.py` transforms raw commits into role-ready metrics.

```python
def get_org_summary(db) -> dict:
    """Org health: module/project counts, avg build rate, top-risk module, customer impact."""

def get_module_health(db, module_id: int, weeks: int = 4) -> dict:
    """Aggregate metrics for a module over the last N weeks."""

def get_module_trends(db, module_id: int) -> list[dict]:
    """Week-by-week history for trend charts."""

def get_punctuality(db, scope_id: int, level: str) -> dict:
    """Avg days-late vs plan, per module/project — the punctuality score."""

def get_customer_impact(db, project_id: int | None = None) -> list[dict]:
    """Errors reported per customer (optionally scoped to a project)."""

def trace_issue_to_commit(db, issue_id: int) -> dict:
    """Customer issue -> commit -> author/module (the customer_trace view)."""

def get_commit_comments(db, module_id: int) -> list[dict]:
    """Per-commit comment counts by severity (GROUP BY severity)."""

def get_all_module_rankings(db) -> list[dict]:
    """All modules ranked by risk score, with health level."""
```

**Metrics:** delivery (commit velocity, build success, **punctuality**), quality (clang /
CodeChecker / ASAN / integration trends), collaboration (review latency, reviewer load, comment
density by severity), business (customer issues per customer, escaped-defect → commit lineage).

---

## Risk Engine

`risk_engine.py` combines dimensions into one normalised score per module/project. All
sub-values are normalised to 0–100 before weighting.

```python
def compute_module_risk(m: dict) -> dict:
    """m: dict from analytics.get_module_health(). Returns {score, level, breakdown}."""

    warning_score = min(m['avg_clang_warnings_per_commit'] * 3, 100)
    asan_score    = min(m['avg_asan_per_commit'] * 25, 100)
    integ_score   = min(m['integration_fail_pct'] * 1.5, 100)
    quality_risk  = 0.40 * warning_score + 0.35 * asan_score + 0.25 * integ_score

    delivery_risk = 100 - m['build_success_rate']

    latency_norm  = min(m['avg_review_latency_hours'] / 48 * 100, 100)
    reviewer_pen  = max(0, (3 - m['avg_reviewers']) * 15)
    collab_risk   = min(latency_norm * 0.7 + reviewer_pen * 0.3, 100)

    risk_score = 0.50 * quality_risk + 0.30 * delivery_risk + 0.20 * collab_risk

    level = ('GREEN' if risk_score < 30 else
             'AMBER' if risk_score < 60 else 'RED')

    return {'score': round(risk_score, 1), 'level': level,
            'breakdown': {'quality_risk':  round(quality_risk, 1),
                          'delivery_risk': round(delivery_risk, 1),
                          'collab_risk':   round(collab_risk, 1)}}
```

| Score | Level | Meaning |
|---|---|---|
| 0 – 29 | GREEN | Healthy, no action needed |
| 30 – 59 | AMBER | Watch closely, consider intervention |
| 60 – 100 | RED | Immediate attention required |

---

## Dashboard — Role-Based (Streamlit)

A **role selector** in the sidebar switches between three personas, ordered most → least
technical. Same central data; each page frames it for its audience.

### app.py — Entry Point

```python
import streamlit as st

st.set_page_config(page_title="Engineering Intelligence Copilot",
                   page_icon="🔬", layout="wide")

st.sidebar.title("Engineering Copilot")
role = st.sidebar.selectbox("Role",
    ["Unit Head", "Project Manager", "Team Lead", "AI Reports", "Management Copilot"])
```

### Page 1 — Unit Head (non-technical, org-wide)

- **Code-quality bar graph** per team/module, annotated with **team size** (people per team)
- **Punctuality score** per team (e.g. "planned 1 month, slipped 2–3 weeks")
- **Errors reported per customer** (3 customers) — which customer is hurting most
- KPI cards: healthy / warning / critical modules, avg build success
- 2–3 chart types; business framing, no raw commit detail

### Page 2 — Project Manager (semi-technical, own project only)

- Scoped to the manager's **own project / team**
- **Per-module, commit-wise comment counts** (major vs minor)
- **Customer-issue → commit traceability**: a table where each customer issue links to the
  commit (and author/module) that caused it
- Delivery & punctuality for the project's modules; per-module risk badges

### Page 3 — Team Lead (most technical, own module/team)

- **Per-commit drill-down**: author, reviewer, major/minor comments, lines changed, review latency
- **Raw quality signals per commit** and trend: clang / CodeChecker / ASAN / integration failures
- **Reviewer load / review participation**
- The **specific commits** behind each customer issue and each quality regression — actionable at
  the individual-commit level, not summaries

```python
trend_df = analytics.get_module_trends(db, module_id)
st.plotly_chart(px.line(trend_df, x="week", y="build_success_rate",
                        title="Build Success Rate", markers=True),
                use_container_width=True)
```

### Page 4 — AI Reports (role-aware)

- Scope selector: module / project / org-wide
- "Generate Report" button → LLM call with summarised JSON context
- Tone/detail tuned per persona (Unit Head = business prose; PM = delivery + risk; TL =
  technical specifics with commit-level evidence)

### Page 5 — Management Copilot (chat)

- Chat input + history in `st.session_state`; org context injected each turn
- Example questions: "Which module should I focus on?", "Why is Networking deteriorating?",
  "Which commit caused Acme's latest issue?", "Is Auth getting better or worse?",
  "Which team is slipping on delivery?"

---

## Multi-Agent Ingestion (git-ready, mostly future)

Each module is its own git repo, and each has an **ingestion agent** — a scoped worker, not
necessarily an LLM — that pushes that repo's activity into the central `engineering.db`:

```bash
python ingest.py --repo https://git.example/auth-service.git --module auth
```

The worker parses `git log` + the GitHub API for that repo and writes `commits`
(commit_id, author, reviewer, module, lines changed, actual_delivery = merge date) and
`review_comments` (text + severity). A loop or scheduler runs one worker per module; all write to
the same central DB — exactly arch.md's "Agent N for module N → central database."

**Triggering, easiest → hardest:**
1. **Batch backfill (start here):** one pass over history populates the DB.
2. **Polling (cron):** run every N minutes/nightly; process only new commits. No public endpoint
   needed — fine on a Windows PC.
3. **Webhooks (real-time):** GitHub POSTs on push/PR-merge → routed to the module's worker.

**What git provides** vs **what stays synthetic / needs other systems:**

| Field | Source |
|---|---|
| commit_id, author, reviewer, module, lines_changed, actual_delivery | git / GitHub ✅ |
| review comments + severity | PR comments (severity via label/heuristic) ✅⚠️ |
| build / clang / CodeChecker / ASAN / integration | **CI logs** (synthetic until then) |
| targeted_delivery | **planning tool** / manual (synthetic until then) |
| customer issues + issue→commit link | **support/issue tracker** + convention (synthetic until then) |

For the MVP, `generate_data.py` stands in for all agents; `ingest.py` is the documented drop-in
that targets the identical schema.

---

## LLM Integration

### Pluggable, config-driven

```python
# config.py
import os

DB_PATH      = os.path.join("data", "engineering.db")

# Default: small local model via Ollama (OpenAI-compatible API)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL    = os.getenv("LLM_MODEL",    "qwen2.5:3b")     # or "llama3.2:3b"
LLM_API_KEY  = os.getenv("LLM_API_KEY",  "not-needed-for-local")

# On the AMD/ROCm machine, switch to vLLM by setting:
#   LLM_BASE_URL = http://localhost:8000/v1
#   LLM_MODEL    = Qwen/Qwen2.5-7B-Instruct
# No code changes — same OpenAI-compatible endpoint.
```

### llm_service.py

```python
import httpx, json
import config

URL = f"{config.LLM_BASE_URL}/chat/completions"

def _call(messages: list[dict], max_tokens: int = 600) -> str:
    try:
        r = httpx.post(URL, json={
            "model": config.LLM_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }, headers={"Authorization": f"Bearer {config.LLM_API_KEY}"}, timeout=120.0)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ LLM unavailable ({e}). Showing data without AI narrative."

def generate_team_report(metrics: dict, risk: dict, role: str = "Project Manager") -> str:
    with open("prompts/team_report.txt") as f:
        template = f.read()
    context = {**metrics, "risk_score": risk["score"], "risk_level": risk["level"]}
    prompt = template.format(role=role, context=json.dumps(context, indent=2))
    return _call([{"role": "user", "content": prompt}], max_tokens=800)

def chat(user_message: str, org_context: dict, history: list[dict]) -> str:
    with open("prompts/copilot.txt") as f:
        system_prompt = f.read().format(context=json.dumps(org_context, indent=2))
    messages = [{"role": "system", "content": system_prompt}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    messages += [{"role": "user", "content": user_message}]
    return _call(messages, max_tokens=500)
```

### Prompt Strategy — Never Send Raw Rows

Always summarise analytics output into a structured JSON context block before sending to the LLM.
Raw rows waste tokens, degrade output, and hit context limits.

**Good context:**
```json
{
  "module": "Networking",
  "risk_score": 82, "risk_level": "RED",
  "build_success_rate": 78,
  "avg_clang_warnings_per_commit": 24.6,
  "warning_trend": "+38% over 4 weeks",
  "asan_failures": 4, "integration_fail_pct": 18.2,
  "avg_review_latency_hrs": 31.4,
  "punctuality_days_late": 14,
  "customer_issues": 5
}
```

### prompts/team_report.txt

```
You are an Engineering Director writing a management report for a {role}.

Context (JSON):
{context}

Write a concise report with exactly these sections:

## Executive Summary
2-3 sentences: overall health and the single most important risk.

## Key Risks
3–4 specific risks with supporting numbers from the context.

## Root Causes
What is driving the degradation? Be specific.

## Recommended Actions
3–4 concrete, prioritised actions for this week.

Match the depth to the role: Unit Head = business framing, Project Manager =
delivery + risk, Team Lead = technical specifics with commit-level evidence.
Be direct. Use numbers. No filler.
```

### prompts/copilot.txt

```
You are an AI engineering management copilot.

Current organisation context (JSON):
{context}

Answer concisely with specific data from the context. Use numbers for comparisons.
If asked which commit caused a customer issue, use the customer→commit trace.
Do not invent data. If something is unknown, say so.
```

---

## Build Plan — DB-First, Incremental

Each step leaves a runnable, visible app.

| Step | Goal | Done when |
|---|---|---|
| **1. Database first** | `schema.sql` + `database.py` + `generate_data.py` → central `engineering.db` | Tables/views exist; `generate_data.py` seeds units/projects/modules/engineers/commits/review_comments/customers/customer_issues; row counts spot-checked |
| **2. Streamlit viewer** | `app.py` + a page that renders raw tables | `streamlit run app.py` loads; module picker shows that module's commits + `weekly_summary` |
| **3. Analytics + risk** | `analytics.py` + `risk_engine.py` on the new grain | Each module yields a plausible GREEN/AMBER/RED matching its storyline; punctuality + customer-impact + customer→commit trace return correct dicts |
| **4. Role-based pages + charts** | Unit Head / Project Manager / Team Lead pages | All three render; charts show storyline trends; punctuality, per-customer counts, commit-wise comments, and customer→commit traceability all display |
| **5. Pluggable LLM** | `config.py` + `llm_service.py` + prompts + AI Reports + Copilot pages | With Ollama running, a module report generates coherent prose; copilot answers a data-grounded question; switching config to vLLM/Qwen needs no code change |
| **6. (Future) Real ingestion** | `ingest.py` per repo | A real repo's commits/authors/reviewers/comments land in the central DB |

---

## Future Enhancements

**Real data integrations**
- Per-module git/GitHub ingestion workers (multi-repo), webhook-triggered
- CI/CD log ingestion — real clang-tidy YAML, CodeChecker JSON, ASAN traces, JUnit XML → quality signals
- Issue-tracker integration (Jira/Zendesk) — real customer issues + targeted delivery dates

**Infrastructure**
- PostgreSQL — replace SQLite for concurrent dashboard users
- Redis — cache LLM report outputs
- Celery / background jobs — async report + ingestion runs

**Intelligence**
- Knowledge graph linking engineers, modules, commits, incidents
- Vector DB — semantic search over reports and review comments
- Anomaly detection — flag spikes before they go RED
- Manager-vs-TL technical-depth tuning per report

**LLM upgrades**
- Promote to `Qwen2.5-14B/32B-Instruct` on ROCm once validated
- Streaming output to the Streamlit chat
- Fine-tune on internal report examples

---

*Plan version: merged — incorporates `arch.md` (unit→project→module→commit hierarchy,
author/reviewer, first-class review comments with severity, targeted-vs-actual delivery /
punctuality, separate customer DB with commit-id traceability, role-based Unit Head / Project
Manager / Team Lead dashboards, per-module ingestion agents → central DB) with the original MVP's
synthetic-data, analytics, risk, Streamlit, and pluggable-LLM design. Decisions locked: SQLite
central DB, synthetic-but-git-ready, multi-repo, generic modules, Ollama-now/vLLM-later LLM,
DB-first incremental build.*
