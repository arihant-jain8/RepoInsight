# Project Aura — Upgrade Plan

**Current code → `AURA.md` blueprint.** Evolve the existing codebase (Streamlit +
SQLite + local Ollama, type-aware risk engine) toward `AURA.md`: multi-tenant
verticals, Jira + telemetry data, AI-tooling metrics, persona dashboards, and AI
insights — all served from a **static, pre-seeded database**.

| | |
|---|---|
| **Scope** | App **logic + persona dashboards** over a **static seeded DB**. Frontend stays **Streamlit**. |
| **Live ingestion** | NOT a real pipeline — a **showcase** of the architecture only. See [API_GATEWAY_DECISION](#-api_gateway_decision-revisit-later). |
| **Dropped** | Identity hashing/anonymisation — higher-ups (Unit Head/PM) see aggregates, not developer ids; **real names stay in the DB** (Team Lead needs them). |
| **Deferred** | Next.js rewrite → [Appendix](#appendix--nextjs-frontend-deferred). MongoDB → [Phase 7](#phase-7--storage-migration-sqlite--mongodb). |
| **Frozen** | Risk-engine math (`src/risk_engine.py`) — only its module→type *input* changed. |
| **Frozen** | OpenAI-compatible LLM seam — model swap is config-only, done later on the ROCm box. |

> ### 🔖 API_GATEWAY_DECISION (revisit later)
>
> **Decided 2026-06-15 (revised — real but scoped).** Federated ingestion =
> edge agents → API gateway → central staging DB, built for real but limited to one agent:
> - **4 agents conceptually** (one per project). For this demo we build **exactly one real
>   agent**, for **5G Core Rollout**. The other 3 are pre-loaded and shown as diagram boxes.
> - **Real fill-in (2A):** the seeder **holds back the whole 5G Core Rollout project** (its 3
>   modules + all activity) from the central DB. Running the one agent **actually writes** that
>   project in through the gateway, so it appears live — including the RED **RAN Packet Parser**.
> - The gateway **does write** to the central DB (real ingestion) via a shared `repository.py`
>   insert seam. The other 3 projects ship pre-loaded. So the demo DB ships with **3 of 4
>   projects**; running the agent completes it.
> - Hashing/anonymisation **out of scope**.
>
> **To revisit:** search `API_GATEWAY_DECISION` — e.g. build the other 3 agents, give each a
> separate per-source DB, the [Phase 7](#phase-7--storage-migration-sqlite--mongodb) Mongo
> backend, or privacy hashing.

---

## Table of contents

- [🔖 API_GATEWAY_DECISION](#-api_gateway_decision-revisit-later)
- [Phase 0 — Gap snapshot](#phase-0--gap-snapshot)
- [Reference — Data structures](#reference--data-structures-verbatim-from-auramd)
- [Phase 1 — Data model](#phase-1--data-model) ✅ done
- [Phase 2 — Ingestion architecture showcase](#phase-2--ingestion-architecture-showcase) 🔖
- [Phase 3 — ~~Live data generator~~ (dropped)](#phase-3--live-data-generator-dropped)
- [Phase 4 — Analytics rollups](#phase-4--analytics-rollups)
- [Phase 5 — Persona dashboards + view scoping](#phase-5--persona-dashboards--view-scoping)
- [Phase 6 — AI core](#phase-6--ai-core)
- [Phase 7 — Storage migration](#phase-7--storage-migration-sqlite--mongodb)
- [Execution order](#execution-order)
- [File-by-file change map](#file-by-file-change-map)
- [Appendix — Next.js frontend](#appendix--nextjs-frontend-deferred)

---

## Phase 0 — Gap snapshot

> **Goal:** baseline of where the current code differs from the `AURA.md` target (logic only; UI excluded).

| Concern | Current code | `AURA.md` target (logic) |
|---|---|---|
| Storage | SQLite `data/engineering.db` (`src/database.py`) | 4 document collections (SQLite now, Mongo later) |
| Hierarchy | unit → project → module → commit | vertical → account → project → module (+ jira + perf) |
| Verticals | single org | Telecomm + BFSI only (the 2 with data in `AURA.md`) |
| Ingestion | `generate_data.py` writes DB directly | edge agent → FastAPI gateway → DB (federated) |
| Identity privacy | plain engineer names | salted SHA-256 `author_hash` |
| Jira / telemetry | thin `customer_issues` table | `jira_logs` + `performance_data` |
| AI metrics | none | `ai_generated_percentage`, MTTR reduction, automation % |
| Agent | single tool-loop (`src/agent.py`) | multi-agent + RBAC scope enforcement |
| Charts | server-side Plotly | LLM emits validated JSON chart spec (rendered in Streamlit) |
| Model | Ollama `qwen2.5:7b` (local) | keep 7B locally; 70B on ROCm box later (config-only) |

---

## Reference — Data structures (verbatim from `AURA.md`)

> Copied **as-is** from `AURA.md` §2 (collections) and §5 (mock payload). This is the
> data spec that the Phase 1 schema and the Phase 2–3 ingestion path must reproduce.
> ⚠️ `AURA.md` gives the full `vertical_units` JSON for **Telecomm only**; **BFSI** is
> given as the tree below (no full JSON in the source — not fabricated here).

### Org tree (2 verticals → 2 accounts → 4 projects → 12 modules)

**📶 Telecomm — Account: GlobalTel Wireless**

- **5G Core Rollout** (Customer: AT&T)
  - Module 1 (Team 1 / Lead 1): `RAN Packet Parser` — High Risk 🔴
  - Module 2 (Team 2 / Lead 2): `Baseband Processing` — Medium Risk 🟡
  - Module 3 (Team 3 / Lead 3): `OSS/BSS Billing Interface` — Low Risk 🟢
- **Edge Computing Layer** (Customer: Verizon)
  - Module 4 (Team 4 / Lead 4): `MEC Signal Handler` — Low Risk 🟢
  - Module 5 (Team 5 / Lead 5): `Baseband Telemetry Stream` — Low Risk 🟢
  - Module 6 (Team 6 / Lead 6): `RAN Automation Engine` — Medium Risk 🟡

**🏦 BFSI — Account: Nexus Digital Bank**

- **Instant Payments Core** (Customer: Citibank)
  - Module 7 (Team 7 / Lead 7): `ISO20022 Message Parser` — Medium Risk 🟡
  - Module 8 (Team 8 / Lead 8): `Ledger Clearing Engine` — High Risk 🔴
  - Module 9 (Team 9 / Lead 9): `Fraud Analytics Stream` — Low Risk 🟢
- **Wealth Management APIs** (Customer: Barclays)
  - Module 10 (Team 10 / Lead 10): `Portfolio Valuation Engine` — Low Risk 🟢
  - Module 11 (Team 11 / Lead 11): `KYC Document Sanitizer` — Low Risk 🟢
  - Module 12 (Team 12 / Lead 12): `Trade Execution Broker` — Low Risk 🟢

### `module_id` keys (from `AURA.md` §5 `DEMO_MATRIX`)

```python
DEMO_MATRIX = {
    "proj_ran_5g":    ["mod_ran_packet_parser", "mod_baseband_proc", "mod_oss_bss_billing"],
    "proj_edge_comp": ["mod_mec_signal", "mod_baseband_stream", "mod_ran_automation"],
    "proj_pay_core":  ["mod_iso_parser", "mod_ledger_engine", "mod_fraud_stream"],
    "proj_wealth_api":["mod_portfolio_val", "mod_kyc_sanitize", "mod_trade_broker"]
}
```

### Collection 1 — `vertical_units` (master operational matrix)

```json
{
  "_id": "ObjectId('666b4f72c1a8a2b34c000001')",
  "unit_name": "Telecomm",
  "scale_matrix": {
    "total_projects": 2,
    "active_teams": 6,
    "designated_leads": 6
  },
  "accounts": [
    {
      "account_name": "GlobalTel Wireless",
      "customer_status": "high",
      "ai_tool_efficiency": {
        "manual_triage_hours_saved": 45.5,
        "mttr_reduction_percentage": 88.0,
        "ai_resolved_tickets_count": 24
      },
      "projects": [
        {
          "project_id": "proj_ran_5g",
          "project_name": "5G Core Rollout",
          "customer": "AT&T",
          "critical_modules": [
            { "module_id": "mod_ran_packet_parser", "module_name": "RAN Packet Parser", "issue_status": "high" },
            { "module_id": "mod_baseband_proc", "module_name": "Baseband Processing", "issue_status": "medium" },
            { "module_id": "mod_oss_bss_billing", "module_name": "OSS/BSS Billing Interface", "issue_status": "low" }
          ]
        },
        {
          "project_id": "proj_edge_comp",
          "project_name": "Edge Computing Layer",
          "customer": "Verizon",
          "critical_modules": [
            { "module_id": "mod_mec_signal", "module_name": "MEC Signal Handler", "issue_status": "low" },
            { "module_id": "mod_baseband_stream", "module_name": "Baseband Telemetry Stream", "issue_status": "low" },
            { "module_id": "mod_ran_automation", "module_name": "RAN Automation Engine", "issue_status": "medium" }
          ]
        }
      ]
    }
  ]
}
```

### Collection 2 — `git_logs` (engineering transaction layer)

```json
{
  "_id": "ObjectId('666b4f72c1a8a2b34c000002')",
  "unit_name": "Telecomm",
  "project_id": "proj_ran_5g",
  "module_id": "mod_ran_packet_parser",
  "commit_hash": "a8f3b2c1d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4",
  "author_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "timestamp": "2026-06-13T14:22:00Z",
  "lines_added": 240,
  "lines_removed": 12,
  "code_churn_score": "high",
  "ai_metrics": {
    "ai_agent_used": "GitHub Copilot",
    "ai_generated_percentage": 78.5
  }
}
```

### Collection 3 — `jira_logs` (operational & task lifecycle layer)

```json
{
  "_id": "ObjectId('666b4f72c1a8a2b34c000003')",
  "unit_name": "Telecomm",
  "account_name": "GlobalTel Wireless",
  "project_id": "proj_ran_5g",
  "module_id": "mod_ran_packet_parser",
  "ticket_type": "customer_incident",
  "pm_view_data": {
    "ticket_id": "JIRA-TEL-9821",
    "customer": "AT&T",
    "summary": "L3 Telecom Packet Drop during peak RAN congestion",
    "severity": "high",
    "status": "In Progress",
    "raised_time": "2026-06-13T10:14:00Z",
    "resolve_time": null,
    "ai_assistance": {
      "ai_agent_used": "Aura-Triage-Agent",
      "automation_percentage": 85.0
    }
  },
  "tl_view_data": {
    "task_name": "Optimize RAN Packet Parsing Loops",
    "assigned_to": "Dev_0931",
    "assigned_on": "2026-06-13T11:00:00Z",
    "lifecycle_status": "implementation stage",
    "completed_date": null
  }
}
```

### Collection 4 — `performance_data` (real-time infrastructure telemetry)

```json
{
  "_id": "ObjectId('666b4f72c1a8a2b34c000004')",
  "unit_name": "Telecomm",
  "account_name": "GlobalTel Wireless",
  "project_id": "proj_ran_5g",
  "module_id": "mod_ran_packet_parser",
  "metric_source": "Baseband Telemetry Stream",
  "timestamp": "2026-06-13T19:00:00Z",
  "issue_status": "high",
  "telemetry_payload": {
    "packet_drop_rate": 0.08,
    "latency_ms": 42.1,
    "cpu_utilization_percentage": 94.2
  },
  "associated_incidents": ["JIRA-TEL-9821"]
}
```

### Mock payload (from `AURA.md` §5 `mock_generators.py`)

```python
def generate_mock_git_log():
    # Loop mimics a developer committing code to fix a raised customer incident
    payload = {
        "unit_name": "Telecomm",
        "project_id": "proj_ran_5g",
        "module_id": "mod_ran_packet_parser",
        "commit_hash": "a8f3b2c1d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4",
        "raw_author_email": "engineer.one@globaltel.com",  # Stripped/Hashed at Edge Agent layer
        "timestamp": datetime.utcnow().isoformat(),
        "lines_added": random.randint(50, 300),
        "lines_removed": random.randint(5, 50),
        "code_churn_score": "high",
        "ai_metrics": {
            "ai_agent_used": random.choice(["GitHub Copilot", "Devin Agent", "N/A"]),
            "ai_generated_percentage": round(random.uniform(20.0, 95.0), 2)
        }
    }
    return payload
```

---

## Phase 1 — Data model

> **Goal:** make the schema represent everything in `AURA.md` §2 — still on SQLite.
> **Touches:** `src/schema.sql`, `src/generate_data.py`

### Steps

- [ ] **1.1 — Extend the hierarchy** in `src/schema.sql` to `vertical_units → accounts → projects → modules`:
  - [ ] **1.1.1** Add the new tables to the `DROP TABLE` block at the top of `schema.sql` (children-first), so reseed stays idempotent.
  - [ ] **1.1.2** `CREATE TABLE vertical_units(id, name)`.
  - [ ] **1.1.3** `CREATE TABLE accounts(id, vertical_id FK→vertical_units, name, customer, customer_status)`.
  - [ ] **1.1.4** Alter `projects`: add `account_id FK→accounts`, drop `unit_id`.
  - [ ] **1.1.5** Alter `modules`: add `issue_status` (low / medium / high).
  - [ ] **1.1.6** Update every view/query that referenced `units` / `unit_id` (`weekly_summary`, `customer_trace`, any joins) to walk `accounts → vertical_units`.
- [ ] **1.2 — Add AI-tooling fields:**
  - [ ] **1.2.1** Alter `commits`: `ai_agent_used TEXT`, `ai_generated_percentage REAL`, `lines_added INT`, `lines_removed INT`, `code_churn_score TEXT`.
  - [ ] **1.2.2** `CREATE TABLE ai_tool_efficiency(account_id FK, manual_triage_hours_saved, mttr_reduction_percentage, ai_resolved_tickets_count)`.
- [ ] **1.3 — Add Jira lifecycle:**
  - [ ] **1.3.1** `CREATE TABLE jira_logs(ticket_id, module_id, ticket_type, customer, summary, severity, status, raised_time, resolve_time, automation_percentage, assigned_to, task_name, lifecycle_status, completed_date)` — `lifecycle_status` ∈ {study, implementation, review, testing, deployment}.
    > **Decision (flatten):** `AURA.md`'s `jira_logs` nests `pm_view_data.*` / `tl_view_data.*`; SQLite has no nested type, so we **flatten** to the columns above and rebuild the nesting in Phase 7 (Mongo). Field map — PM: `ticket_id, customer, summary, severity, status, raised_time, resolve_time, automation_percentage` (from `pm_view_data.ai_assistance.automation_percentage`); TL: `assigned_to, lifecycle_status, completed_date` (+ `task_name` from `tl_view_data`).
  - [ ] **1.3.2** `CREATE VIEW customer_issues` over `jira_logs` (back-compat shim for `analytics.py`).
  - [ ] **1.3.3** Confirm existing customer queries in `analytics.py` still resolve through the view.
- [ ] **1.4 — Add telemetry** — `CREATE TABLE performance_data(module_id, metric_source, timestamp, issue_status, packet_drop_rate, latency_ms, cpu_utilization_percentage, associated_incidents)`.
- [ ] **1.5 — Seed in `src/generate_data.py`:**
  - [ ] **1.5.1** Replace the `METRIC_CATALOG` dict with the retuned values from [§1.5b](#-15b--retuned-metric_catalog).
  - [ ] **1.5.2** Seed `vertical_units` (Telecomm, BFSI) and `accounts` (GlobalTel Wireless, Nexus Digital Bank).
  - [ ] **1.5.3** Seed the 4 projects (5G Core/AT&T, Edge/Verizon, Payments/Citibank, Wealth/Barclays).
  - [ ] **1.5.4** Seed the 12 modules with the types from [§1.5a](#-15a--module--type-mapping).
  - [ ] **1.5.5** Bias each module's metric severity so computed risk matches its `AURA.md` label (RAN Packet Parser, Ledger Clearing → RED; etc.).
  - [ ] **1.5.6** Populate the new commit AI fields + one `ai_tool_efficiency` row per account.
  - [ ] **1.5.7** Generate `jira_logs` (ticket lifecycle) and `performance_data` (telemetry) rows per module.
- [ ] **1.6 — Verify:**
  - [ ] **1.6.1** Run the seeder; sanity-check row counts (2 / 2 / 4 / 12).
  - [ ] **1.6.2** Run `risk_engine.compute_module_risk` over all 12; confirm RED/AMBER/GREEN match `AURA.md` labels.
  - [ ] **1.6.3** Launch Streamlit; confirm Overview + persona pages render with no errors.

### § 1.5a — Module → type mapping

> `2 → 2 → 4 → 12`. Distribution: **network ×4, backend ×6, ai ×2**. `frontend` stays defined but unused (no UI modules — harmless).

| Module | Account → Project | Type |
|---|---|---|
| RAN Packet Parser | GlobalTel → 5G Core | `network` |
| Baseband Processing | GlobalTel → 5G Core | `network` |
| OSS/BSS Billing Interface | GlobalTel → 5G Core | `backend` |
| MEC Signal Handler | GlobalTel → Edge | `network` |
| Baseband Telemetry Stream | GlobalTel → Edge | `network` |
| RAN Automation Engine | GlobalTel → Edge | `backend` |
| ISO20022 Message Parser | Nexus → Payments | `backend` |
| Ledger Clearing Engine | Nexus → Payments | `backend` |
| Fraud Analytics Stream | Nexus → Payments | `ai` |
| Portfolio Valuation Engine | Nexus → Wealth | `backend` |
| KYC Document Sanitizer | Nexus → Wealth | `ai` |
| Trade Execution Broker | Nexus → Wealth | `backend` |

> ⚠️ **Seeder must bias metric values so computed risk matches `AURA.md`'s labels** — e.g. RAN Packet Parser & Ledger Clearing Engine get bad metrics so the engine independently lands them RED; Low-risk modules get good values.

### § 1.5b — Retuned `metric_catalog`

> Same math, domain-fit metrics, weights sum ≈ 1.0 per type. `dir` = direction (↑ higher-is-better, ↓ lower-is-better).

**`network`** — telecom signal/packet C/C++ *(memory safety + static + runtime)*

| metric | unit | dir | good | bad | weight |
|---|---|---|---|---|---|
| `asan_failures` | count | ↓ | 0 | 3 | 0.30 |
| `clang_warnings` | count | ↓ | 10 | 120 | 0.20 |
| `packet_drop_rate_pct` | % | ↓ | 0.05 | 2.0 | 0.30 |
| `p99_latency_ms` | ms | ↓ | 20 | 150 | 0.20 |

**`backend`** — services / payments *(coverage + txn correctness + security + lint)*

| metric | unit | dir | good | bad | weight |
|---|---|---|---|---|---|
| `test_coverage_pct` | % | ↑ | 85 | 50 | 0.25 |
| `transaction_error_rate_pct` | % | ↓ | 0.1 | 3.0 | 0.30 |
| `sast_findings` | count | ↓ | 0 | 10 | 0.25 |
| `lint_errors` | count | ↓ | 2 | 40 | 0.20 |

**`ai`** — fraud / KYC ML *(accuracy + false-positives + drift + data validation)*

| metric | unit | dir | good | bad | weight |
|---|---|---|---|---|---|
| `eval_accuracy_pct` | % | ↑ | 92 | 70 | 0.30 |
| `false_positive_rate_pct` | % | ↓ | 1 | 15 | 0.25 |
| `model_drift` | ratio | ↓ | 0.02 | 0.3 | 0.25 |
| `data_validation_failures` | count | ↓ | 0 | 10 | 0.20 |

**`frontend`** — unchanged, unused (kept for future UI modules).

> 📌 **MTTR is *not* a catalog metric.** It is an **outcome** metric (see Phase 4) from `jira_logs` (`raised_time → resolve_time`), surfaced in the Unit-Head / PM panels — kept out of `quality_risk` to avoid conflating runtime ops with code quality and double-counting against `delivery_risk`.
>
> 📌 `packet_drop_rate_pct` / `p99_latency_ms` overlap with `performance_data` telemetry **by design** — in the catalog they are the per-commit aggregated quality value; the seeder derives them consistently with the telemetry stream.

---

## Phase 2 — Ingestion architecture showcase

> **Decision:** [API_GATEWAY_DECISION](#-api_gateway_decision-revisit-later) — real write-through, one agent (5G Core Rollout), real fill-in (2A).
> **Goal:** one real edge agent ingests the held-back **5G Core Rollout** project through the API gateway into the central DB, live. Other 3 projects pre-loaded.
> **Touches:** `src/repository.py` *(new)*, `src/gateway/main.py` *(new)*, `src/edge_agent.py` *(new)*, `src/generate_data.py`, `src/config.py`, a new Architecture page in `pages/`.

### Steps

- [x] **2.1 — Deps** — `fastapi`, `uvicorn[standard]`, `pydantic` added (edge agent posts via existing `httpx`; no `requests`).
- [x] **2.2 — AURA id columns** — `projects.proj_key` + `modules.mod_key` added & seeded ([§1.5a](#-15a--module--type-mapping) names ↔ AURA slugs).
- [ ] **2.3 — Write seam** `src/repository.py` — `ingest_project_bundle(bundle)`: insert a project + its modules, engineers, commits (+ commit_metrics, review_comments), jira_logs, performance_data into the central DB, resolving the account by name. Reused by gateway *and* seeder (single insert path).
- [ ] **2.4 — Seeder split** `src/generate_data.py` — after the full seed, **export 5G Core Rollout** (project + 3 modules + all activity) to `data/sources/proj_ran_5g.json`, then **delete those rows** from the central DB. Central ships with 3 projects. (Add a `--full` flag to skip the split for dev.)
- [ ] **2.5 — Gateway** `src/gateway/main.py` — `POST /ingest/project` (accepts the bundle → `repository.ingest_project_bundle`), `GET /healthz`, `GET /stats` (row counts for the page). Pydantic-validated.
- [ ] **2.6 — Edge agent** `src/edge_agent.py` — reads `data/sources/proj_ran_5g.json`, `filter_fields()` ($exists semantics), `forward()` → POST to the gateway via `httpx`.
- [ ] **2.7 — Architecture page** `pages/0X_architecture.py` — diagram (4 edge agents → API gateway → central staging DB); 3 boxes "loaded ✓", the 5G Core one with a **"Run agent"** button that triggers the ingest; live row counts from `/stats`; the project appears after running.
- [ ] **2.8 — Config** `src/config.py`: `GATEWAY_URL` (default `http://localhost:8000`).
- [ ] **2.9 — Verify** — fresh seed → app shows 3 projects → run agent → 5G Core Rollout + RED RAN Packet Parser appear; risk labels still 12/12.

---

## Phase 3 — Live data generator (dropped)

> **Dropped** per [API_GATEWAY_DECISION](#-api_gateway_decision-revisit-later): the demo DB is
> **static** (no live rows), so there is no streaming generator. The one-shot seeder
> (`src/generate_data.py`, Phase 1) is the only data source. If real ingestion is
> revisited, the original streaming design is in git history.

---

## Phase 4 — Analytics rollups

> **Goal:** turn the new data into role-ready numbers in `src/analytics.py` (the module the Streamlit pages already read).
> **Touches:** `src/analytics.py`

### Steps

- [ ] **4.1 — MTTR** `get_mttr_by_module()` / `get_mttr_by_account()` — aggregate `resolve_time − raised_time` over `jira_logs` (the base signal for 4.2).
- [ ] **4.2 — AI efficiency** `get_account_ai_efficiency()` — manual-hours-saved, MTTR-reduction %, AI-resolved ticket counts per account (reads `ai_tool_efficiency` + 4.1).
- [ ] **4.3 — Jira pipeline** `get_jira_pipeline(project_id)` — ticket table (severity, status, raised/resolve, assigned_to, lifecycle stage) for the PM / TL views.
- [ ] **4.4 — Telemetry** `get_telemetry(module_id)` — latest perf samples + associated incidents from `performance_data`.
- [ ] **4.5 — AI-authored share** — extend `get_commit_comments` to surface `ai_generated_percentage` per commit for the commit-level tracking matrix.
- [ ] **4.6 — Expose to the agent** — register the new functions as tools in `src/agent.py` (`_DISPATCH` + `TOOLS`) so the copilot can call them.
- [ ] **4.7 — Contract check** — confirm every new return is JSON-serialisable (feeds both UI and agent).

---

## Phase 5 — Persona dashboards + view scoping

> **Goal:** the three `AURA.md` §3 persona views, each showing role-appropriate data
> from the **static DB**. *Light* scoping (filter to the persona's slice) — **not** heavy
> RBAC/auth (dropped along with hashing; this is a demo). Team Lead sees **real names**;
> Unit Head / PM see **aggregates** (no developer ids).
> **Touches:** `pages/01–03_*.py`, `src/analytics.py`, optionally `src/agent.py`.

### Steps

- [ ] **5.1 — Unit Head** (`pages/01_unit_head.py`) — strategic/customer view: vertical → account → project drill-down, customer-status buckets, AI-tool-efficiency panel, customer-reported errors. Aggregates only.
- [ ] **5.2 — Project Manager** (`pages/02_project_manager.py`) — delivery view: jira ticket pipeline (severity / status / lifecycle), commit-level tracking with AI-authored %, customer review table.
- [ ] **5.3 — Team Lead** (`pages/03_team_lead.py`) — local workspace: task lifecycle, **real engineer names**, per-commit comments, the module's customer-issue → commit table. Scoped to the lead's own module(s).
- [ ] **5.4 — Light scoping** — a small helper that filters each page's data to its slice (vertical / project / module). No auth tokens, no hard-fail — just the right data per view.
- [ ] **5.5 — (optional) Agent boundary** — keep the `AURA.md` narrative: the Team Lead copilot only answers about its own module. Soft guard in `src/agent.py`. Skip if time-boxed.

---

## Phase 6 — AI core

> **Goal:** the `AURA.md` §4 AI core — multi-agent orchestration + validated JSON-over-code charts. Runs on the **local 7B** model.
> **Touches:** `src/chart_spec.py` *(new)*, `src/prompts/chart.txt` *(new)*, `src/orchestrator.py` *(new)*, `src/agent.py`

### Steps

- [ ] **6.1 — Stay on local 7B.** Keep `qwen2.5:7b` via Ollama (`config.py`); all work below runs against it. The vLLM / Llama-3-70B move is a later **config-only change** (`LLM_BASE_URL` / `LLM_MODEL`) on the ROCm box — not now.
- [ ] **6.2 — Chart-spec schema** `src/chart_spec.py` — strict Pydantic model (`type` ∈ bar/line/pie, `x`, `series`, `title`, …) + a `to_plotly(spec)` renderer.
- [ ] **6.3 — Chart prompt** `src/prompts/chart.txt` — force the model to output **only** valid chart-spec JSON, never raw JS/HTML.
- [ ] **6.4 — Validate-and-repair** — parse model output against the schema; on mismatch, re-prompt with the error (bounded retries) before giving up.
- [ ] **6.5 — Render in Streamlit** — map a validated spec → Plotly in the copilot page (Next.js/Recharts later).
- [ ] **6.6 — Multi-agent graph** `src/orchestrator.py` (LangGraph or CrewAI):
  - [ ] **6.6.1** Nodes: **Planner → Retriever** (reuse `_DISPATCH` / `TOOLS`) **→ Chart-Builder** (6.2–6.5) **→ Verifier**.
  - [ ] **6.6.2** Keep the `is_available()` fallback to the simple `agent.py` loop when the endpoint is down.
- [ ] **6.7 — Guardrails stay** — `_scrub_sql`, read-only SQL, and the Phase-5 RBAC scope apply to **every** node in the graph.

> ⚠️ **7B caveat:** a 7B model is weaker at multi-agent orchestration and strict-JSON output than a 70B. Lean on **tight schemas + validate-and-repair loops**, not on the model getting it right first try. Same code works better once you swap to 70B.

---

## Phase 7 — Storage migration: SQLite → MongoDB

> **Goal:** realize the `AURA.md` §2 document model. Do this **last**, after data shapes are stable, behind a repository seam so nothing else changes.
> **Touches:** `src/repository.py` *(new)*, `src/analytics.py`, `src/config.py`

### Steps

- [ ] **7.1 — Formalize the seam** `src/repository.py` — promote the Phase-2 write seam into a full interface (`insert_*`, `find_modules`, `aggregate_*`) and refactor gateway + analytics to depend only on it.
- [ ] **7.2 — `SqliteRepository`** — wrap today's `database.py` behind the interface (no behavior change; proves the seam).
- [ ] **7.3 — Add deps** — `pymongo` (or `motor`) to `requirements.txt`.
- [ ] **7.4 — `MongoRepository`** — implement the 4 collections per `AURA.md` §2: `vertical_units` (nested accounts → projects → modules), `git_logs`, `jira_logs`, `performance_data`.
- [ ] **7.5 — Port aggregations** — rewrite each analytics query as a Mongo pipeline (`$match` / `$group` / `$lookup`); keep function names + return shapes identical so UI and risk engine are untouched.
- [ ] **7.6 — Config switch** — `AURA_DB_BACKEND=sqlite|mongo` (default `sqlite` locally) selects the repository impl.
- [ ] **7.7 — Sparse-safe queries** — use `$exists` filters so sparse documents are valid ("ingest gracefully without structural breaking").
- [ ] **7.8 — Parity check** — run the same persona views against both backends; confirm identical numbers.

---

## Execution order

```
Phase 1 (data model) ✅ ─► Phase 4 (analytics rollups) ─► Phase 5 (persona dashboards)
   ─► Phase 6 (AI core)   ◄── demo-ready
   ─► Phase 2 (ingestion showcase, anytime)   ·   Phase 7 (MongoDB, optional / last)
```

**Static-DB demo path:** the data is already seeded (Phase 1), so the value flow is
**analytics → persona dashboards → AI insights**. Phase 2 is a self-contained *showcase*
(API_GATEWAY_DECISION) that can slot in whenever. Phase 3 is dropped. Phase 7 (Mongo)
and the [Appendix](#appendix--nextjs-frontend-deferred) (Next.js) are deferred.

---

## File-by-file change map

| File | Phase | Action |
|---|---|---|
| `src/schema.sql` | 1 | + verticals/accounts, AI cols, `jira_logs`, `performance_data` |
| `src/generate_data.py` | 1, 3 | reseed 12 modules + retuned catalog; stays one-shot backfill |
| `mock_generators.py` *(new)* | 3 | live streaming POST loop + anomaly trigger |
| `src/gateway/main.py` *(new)* | 2 | FastAPI ingestion endpoints |
| `src/edge_agent.py` *(new)* | 2 | filter + sanitize + salted SHA-256 + POST |
| `src/rbac.py` *(new)* | 5 | `Principal`, scope filters, persona guardrails |
| `src/chart_spec.py` *(new)* | 6 | Pydantic chart-spec schema + validation |
| `src/orchestrator.py` *(new)* | 6 | multi-agent over existing tools |
| `src/repository.py` *(new)* | 7 | storage seam; SQLite + Mongo impls |
| `src/analytics.py` | 4, 7 | AI efficiency, MTTR, Jira/telemetry rollups; Mongo pipelines |
| `src/agent.py` | 5, 6 | inject RBAC scope into dispatch + run_sql |
| `src/config.py` | 2, 7 | `GATEWAY_URL`, `AURA_HASH_SALT`, `AURA_DB_BACKEND` |
| `pages/01–03_*.py` | 5 | build `Principal` per role; render scoped data + chart specs |
| `requirements.txt` | 2, 6, 7 | + fastapi, uvicorn, pydantic, langgraph, (pymongo in P7) |
| `README.md`, `docs/DEMO.md` | — | new run path (gateway + `mock_generators`) |

> **Frozen:** `src/risk_engine.py` math stays untouched; only its module→type input mapping changes.

---

## Appendix — Next.js frontend (deferred)

Deferred until the logic above is solid. When we get there:

- Scaffold `frontend/` — Next.js (App Router) + shadcn/ui + Tailwind.
- Expose read endpoints from the gateway (`/api/org-summary`, `/api/rankings`, `/api/module/{id}`, `/api/chat`).
- Gate the three persona routes by RBAC (Phase 5) — server-side role check + tenant token in session.
- Render validated JSON chart specs via a `<DynamicChart spec={…}/>` component (Recharts/Plotly) — **never** `eval` / `dangerouslySetInnerHTML`.

Until then, **Streamlit is the frontend.**
