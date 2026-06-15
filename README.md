# Engineering Intelligence Copilot

An AI-powered engineering-management dashboard. It consolidates engineering activity across a
multi-tenant **vertical → account → project → module → commit** hierarchy into one central
SQLite database, scores team risk, tracks delivery punctuality and ticket MTTR, traces
customer-reported issues back to the **exact commit** that caused them, and presents
**role-based** views for Unit Heads, Project Managers, and Team Leads.

It also includes a **federated-ingestion showcase** (an edge agent pushes a project into the
central DB live through an API gateway) and an **inference-performance benchmark** (tokens,
latency, and GPU usage of the AI core).

The demo runs on **static, synthetic, git-shaped data** so the whole system works end-to-end
with no external services. The current dataset: **2 verticals (Telecomm, BFSI) → 2 accounts
→ 4 projects → 12 modules**.

> **This deployment targets the AMD/ROCm machine running a 70B-class model** — Qwen2.5 **72B**
> served by Ollama. The LLM layer is pluggable, so a smaller model still works for low-VRAM dev
> (see [Using a smaller model](#using-a-smaller-model)). Commands below are for **Linux** (the
> AMD box); Windows/macOS notes are inline where they differ.

---

## Prerequisites

- **Python 3.12+** and **git**
- An **AMD GPU with ROCm** (Linux). The 70B-class model needs **~48 GB of VRAM** (Qwen2.5 72B,
  4-bit). GPU metrics on the Performance page use `rocm-smi` / `amd-smi`.
- **Ollama** — serves the OpenAI-compatible `/v1/chat/completions` API the app speaks, with
  ROCm acceleration on AMD.

---

## Setup

Run these in order, from a shell on the AMD machine.

### 1. Get the code

```bash
git clone <repo-url> RepoInsight
cd RepoInsight
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

<details>
<summary>Windows / macOS</summary>

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# If activation is blocked: Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
```bash
# macOS
python3 -m venv .venv && source .venv/bin/activate
```
</details>

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Start the 70B model (Ollama on ROCm)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve                 # OpenAI-compatible API on :11434; uses the AMD GPU via ROCm
ollama pull qwen2.5:72b      # ~47 GB — the 70B-class model
curl http://localhost:11434/v1/models    # verify it's serving
```

Point the app at the 70B model (the only var that differs from the local default):

```bash
export LLM_MODEL=qwen2.5:72b
# LLM_BASE_URL already defaults to http://localhost:11434/v1 (Ollama)
# 70B is slower than 7B — if requests time out, raise the per-request timeout:
export LLM_TIMEOUT=240
```

> The app is **stub-first**: with no model running, every AI surface falls back to a
> deterministic, data-driven summary (sidebar shows `LLM: ⚪ offline`). With Ollama up and the
> model pulled, the same buttons produce real generated prose (`LLM: 🟢 connected`).
> Full env-var reference: [LLM configuration](#llm-configuration).

### 5. Generate the synthetic database

This seeds the central `data/engineering.db` (12 modules × 12 weeks of commits, type-aware
quality metrics, review comments, Jira tickets, and telemetry).

```bash
python -m aura.data.generate_data
```

Expected output:

```
Seeded central engineering.db:
  engineers       : 68 (across teams)
  commits         : 1152
  commit_metrics  : 4608
  review_comments : ~2900
  jira_logs       : 127
  performance_data: 72
  held back       : proj_ran_5g -> data/sources/proj_ran_5g.json (3 modules, 288 commits) - ingest live via the agent
```

> **One project is held back for the live-ingestion demo.** The seeder lifts **5G Core Rollout**
> out of the central DB into `data/sources/proj_ran_5g.json`, so the app ships with **3 of 4
> projects**. You ingest the 4th live on the **🛰️ Architecture** page (see
> [Federated ingestion demo](#federated-ingestion-demo)). To keep all 4 projects in the DB
> instead: `python -m aura.data.generate_data --full`.
>
> A pre-generated `data/engineering.db` is committed, so this step is optional — re-run it any
> time to reset the data.

### 6. Run the dashboard

```bash
python -m streamlit run app.py
```

Then open **http://localhost:8501** (Streamlit usually opens it for you).

---

## Using the dashboard

The sidebar lists these views:

| View | Audience | What it shows |
|---|---|---|
| **Executive Overview** (home) | Everyone | Org KPIs, risk-ranked modules (high/medium/low), highest-risk / fastest-improving callouts, raw-table browser |
| **🏢 Unit Head** | Non-technical, org-wide | AI-tool-efficiency per client (MTTR reduction, hours saved) with a derived **account risk tier**, merged customer-reported-errors (raised vs still-open by severity + share), code quality, punctuality |
| **📋 Project Manager** | One project | Delivery KPI row (open / high-crit / MTTR / build % / AI usage), **ticket pipeline governance** (by status / lifecycle / severity), customer ticket pipeline |
| **🛠️ Team Lead** | One module | Task overview, type-specific quality metrics, per-commit drill-down, trends, team roster, live telemetry, commits behind customer issues |
| **📝 AI Reports** | Any | Generate a role-aware report for a module / project / org, export as Markdown |
| **💬 Management Copilot** | Any | Tool-using **agent** — queries the live DB (analytics + read-only SQL) and shows the tools it called |
| **🛰️ Architecture** | Demo | Federated ingestion showcase — run the edge agent to ingest 5G Core Rollout live (see below) |
| **⚡ Performance** | Demo | Inference benchmark — tokens, end-to-end latency, and GPU usage of the AI core |

Each role page also has an inline **🧠 Generate AI insight** button.

**Type-aware quality:** each module has a `type` (network / backend / frontend / ai) and is
scored on that type's own metrics via `metric_catalog` + `commit_metrics`:
- **network** — ASAN failures, clang warnings, packet-drop rate, p99 latency
- **backend** — test coverage, transaction error rate, SAST findings, lint errors
- **ai** — eval accuracy, false-positive rate, model drift, data-validation failures

Risk is `0.50·quality + 0.30·delivery + 0.20·collaboration`, banded into **low (<30) /
medium (30–59) / high (≥60)**. Modules are benchmarked against **same-type** peers.

---

## Federated ingestion demo

Demonstrates the AURA architecture: a local **edge agent** pushes a project through an **API
gateway** into the **central staging DB**, live. (The other 3 projects ship pre-loaded; only
5G Core Rollout is ingested on demand.)

**1. Start the gateway** in a second terminal (stdlib `http.server`, no extra deps):

```bash
python -m aura.ingestion.gateway            # serves on http://localhost:8000
```

**2. In the app**, open **🛰️ Architecture**:
- The gateway badge shows 🟢 online; 3 projects are **pre-loaded ✓**, 5G Core Rollout is **pending**.
- Click **▶ Run 5G Core Rollout edge agent** → it posts the held-back project through the gateway
  into the DB → the project (and its high-risk **RAN Packet Parser** module) appears, **4 projects** now.
- Click **↺ Reset demo** to hold it back again and repeat.

You can also run the agent from the CLI: `python -m aura.ingestion.edge_agent proj_ran_5g`.

---

## Inference performance

The **⚡ Performance** page benchmarks the AI core live. With the model running, click
**▶ Run benchmark** to run 3 scenarios (org report · module deep-dive · agentic copilot Q&A)
and see, per scenario: prompt/completion/total **tokens**, **end-to-end latency**, tokens/sec,
and **peak GPU util + memory** during the run vs an **idle baseline**.

GPU reads are **vendor-aware** — on this AMD box it uses `rocm-smi` / `amd-smi` (and `nvidia-smi`
on an NVIDIA dev machine). The page degrades gracefully if no model or GPU tool is present.

---

## Resetting

```bash
python -m aura.data.generate_data            # re-seed (3 projects + held-back 5G Core)
python -m aura.data.generate_data --full     # re-seed with all 4 projects in the DB
```

The generator deletes and recreates the DB on each run, so it is safe to re-run any time.
> Stop Streamlit before re-seeding (an open connection can lock the DB file).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `streamlit: command not found` | Use `python -m streamlit run app.py`. |
| Dashboard says "No database found" | Run `python -m aura.data.generate_data` first. |
| Copilot / reports say `LLM: ⚪ offline` | Start Ollama (`ollama serve`) and confirm `LLM_MODEL` is pulled (`ollama list`). |
| Copilot requests time out | 70B is slow on first load — raise `LLM_TIMEOUT` (e.g. `export LLM_TIMEOUT=240`). |
| Performance page: GPU metrics blank | Ensure `rocm-smi` / `amd-smi` is on `PATH` (ships with ROCm). |
| Architecture page: gateway 🔴 offline | Start it: `python -m aura.ingestion.gateway`. |
| Only 3 projects / 5G Core missing | Intended — ingest it on the Architecture page, or seed with `--full`. |
| Port 8501 already in use | `python -m streamlit run app.py --server.port 8502`. |

---

## LLM configuration

The LLM layer is **pluggable** via `config.py` and speaks the OpenAI-compatible
`/v1/chat/completions` API, so the same code runs against Ollama on the AMD box and (if you
prefer) a vLLM server, with no code changes. Configure with environment variables:

| Variable | Default | This (AMD / 70B) deployment |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:11434/v1` (Ollama) | same — Ollama on the AMD box |
| `LLM_MODEL` | `qwen2.5:7b` | **`qwen2.5:72b`** |
| `LLM_API_KEY` | `not-needed-for-local` | — |
| `LLM_TIMEOUT` | `120` (seconds/request) | `240` (70B is slower) |
| `LLM_MAX_TOKENS` | `800` | `800` |
| `GATEWAY_URL` | `http://localhost:8000` (ingestion gateway) | same |

<details>
<summary>Run the 70B model via vLLM instead of Ollama</summary>

```bash
vllm serve Qwen/Qwen2.5-72B-Instruct --port 8000        # OpenAI-compatible on :8000
export LLM_BASE_URL=http://localhost:8000/v1
export LLM_MODEL=Qwen/Qwen2.5-72B-Instruct
```
</details>

### Using a smaller model

For a low-VRAM dev machine, the defaults already point at a small model — just pull it and
leave `LLM_MODEL` unset:

```bash
ollama pull qwen2.5:7b      # ≈4.7 GB, needs ~6 GB VRAM  (or qwen2.5:3b for less)
```

The copilot's tool-use and proactive charting are **noticeably more reliable on the 70B** than
on a 7B; smaller models are best for offline/stub development.

---

## Project structure

```
RepoInsight/
├── app.py                    # Streamlit entrypoint (Executive Overview); imports from aura.*
├── pages/                    # Streamlit views (01 unit head … 07 performance)
│   ├── 01_unit_head.py  02_project_manager.py  03_team_lead.py  04_reports.py  05_copilot.py
│   ├── 06_architecture.py    # federated ingestion showcase
│   └── 07_performance.py     # inference metrics (tokens / latency / GPU)
├── aura/                     # core logic, a package grouped by concern
│   ├── config.py             # central DB path + pluggable LLM + GATEWAY_URL
│   ├── ui.py                 # risk colours, cached loaders, AI insight widget
│   ├── data/                 # database.py, schema.sql, generate_data.py, repository.py
│   ├── analytics/            # analytics.py (metrics), risk_engine.py (low/medium/high scoring)
│   ├── ai/                   # llm_service.py, agent.py (copilot), perf.py (benchmark), prompts/
│   └── ingestion/            # edge_agent.py, gateway.py (stdlib /ingest /healthz /stats)
├── data/
│   ├── engineering.db        # generated SQLite database (ships with 3 of 4 projects)
│   └── sources/              # held-back project bundle for the live-ingestion demo
├── docs/                     # design + architecture notes (AURA.md is the blueprint)
├── requirements.txt
└── README.md
```

> `app.py` and `pages/` stay at the project root because Streamlit requires the entrypoint and
> its `pages/` directory together. They add the repo root to the import path so they can
> `from aura.* import …`. Run the CLI tools as modules from the root, e.g.
> `python -m aura.data.generate_data` and `python -m aura.ingestion.gateway`.
