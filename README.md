# Engineering Intelligence Copilot

An AI-powered engineering-management dashboard. It consolidates engineering activity
across a **unit → project → module → commit** hierarchy into one central SQLite database,
scores team risk, tracks delivery punctuality, traces customer-reported issues back to the
**exact commit** that caused them, and presents **role-based** views for Unit Heads, Project
Managers, and Team Leads.

The MVP runs on **synthetic, git-shaped data** so the whole system works end-to-end with no
external services. The schema is designed so a real per-module git ingestion worker can drop
in later with no schema change.

---

## Prerequisites

- **Python 3.12+** (developed on 3.12.6)
- **git**
- Windows, macOS, or Linux. Commands below show **Windows PowerShell**; equivalents are noted.

---

## Setup

From the project root (`RepoInsight/`):

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # PowerShell
```

<details>
<summary>Other shells</summary>

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows cmd.exe
python -m venv .venv
.\.venv\Scripts\activate.bat
```
</details>

> If PowerShell blocks the activation script, run once:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
> Or skip activation and prefix commands with `.\.venv\Scripts\python.exe`.

### 2. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Generate the synthetic database

This seeds the central `data/engineering.db` (8 modules × 12 weeks of commits, review
comments, customers, and customer issues).

```powershell
python src/generate_data.py
```

Expected output:

```
Seeded central engineering.db:
  engineers       : 24
  commits         : 768
  review_comments : 2007
  customers       : 3
  customer_issues : 75
```

> A pre-generated `data/engineering.db` is committed to the repo, so this step is optional —
> but re-run it any time to reset the data.

### 4. Run the dashboard

```powershell
python -m streamlit run app.py
```

Then open **http://localhost:8501** in your browser. (Streamlit usually opens it for you.)

---

## Using the dashboard

The sidebar lists these views:

| View | Audience | What it shows |
|---|---|---|
| **Executive Overview** (home) | Everyone | Org KPIs, risk-ranked modules, highest-risk / fastest-improving callouts, raw-table browser |
| **🏢 Unit Head** | Non-technical, org-wide | Code-quality bars with team size, punctuality, customer-reported errors |
| **📋 Project Manager** | One project | Module risk, major/minor review comments, **customer issue → commit traceability** |
| **🛠️ Team Lead** | One module | Type-specific quality metrics, per-commit drill-down, trend charts, team roster, same-type benchmark, commits behind customer issues |
| **📝 AI Reports** | Any | Generate a role-aware report for a module / project / org, and download it as Markdown |
| **💬 Management Copilot** | Any | Tool-using **agent** — queries the live DB (analytics + read-only SQL) to answer, and shows the tools it called |

Each role page also has an inline **🧠 Generate AI insight** button that writes a
report for that page's data, right next to its charts.

**Type-aware quality:** each module has a `type` (network / backend / frontend / ai)
and is scored on that type's own metrics (clang/ASAN for network; ESLint/accessibility/
Lighthouse/bundle for frontend; coverage/lint/API-error/SAST for backend; eval-accuracy/
drift for ai) via `metric_catalog` + `commit_metrics`. Modules are benchmarked against
**same-type** peers. Engineers belong to a module's team, so "who's on the UI/UX team"
is a real answer.

### AI behaviour (works with or without a model)

The AI features are **stub-first**: with no model running, every AI surface falls back
to a deterministic, data-driven summary (the sidebar shows `LLM: ⚪ offline`). Start a
local model (below) and the same buttons produce real generated prose (`LLM: 🟢 connected`).

---

## Project structure

```
RepoInsight/
├── app.py                  # Streamlit entrypoint (Executive Overview)
├── pages/                  # Streamlit views
│   ├── 01_unit_head.py
│   ├── 02_project_manager.py
│   ├── 03_team_lead.py
│   ├── 04_reports.py       # AI reports (scope + role selector, export)
│   └── 05_copilot.py       # management copilot chat
├── src/                    # core logic (importable modules)
│   ├── config.py           # central DB path + pluggable LLM settings
│   ├── database.py         # SQLite connection + query helpers
│   ├── schema.sql          # all table + view DDL
│   ├── generate_data.py    # seed the central engineering.db (run once)
│   ├── analytics.py        # metric computation (health, trends, punctuality, ...)
│   ├── risk_engine.py      # GREEN/AMBER/RED risk scoring per module
│   ├── llm_service.py      # pluggable LLM client + data-driven fallback
│   ├── prompts/            # report.txt, copilot.txt
│   └── ui.py               # risk colors, cached loaders, AI insight widget
├── data/engineering.db     # generated SQLite database
├── docs/
│   ├── Engineering_Intelligence_Plan.md   # full design doc
│   └── arch.md             # original architecture notes
├── requirements.txt
└── README.md
```

> `app.py` and `pages/` stay at the project root because Streamlit requires the
> entrypoint and its `pages/` directory to live together. They add `src/` to the
> import path at startup, so the views can `import analytics`, `import ui`, etc.

---

## LLM configuration (for upcoming AI Reports + Copilot)

The LLM layer is **pluggable** via `config.py` and speaks the OpenAI-compatible
`/v1/chat/completions` API, so the same code works against a small local model now and a
larger model later. Configure with environment variables:

| Variable | Default (local) | On the AMD/ROCm machine (vLLM) |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:11434/v1` (Ollama) | `http://localhost:8000/v1` |
| `LLM_MODEL` | `qwen2.5:3b` | `Qwen/Qwen2.5-7B-Instruct` |
| `LLM_API_KEY` | `not-needed-for-local` | — |

To run a small local model now:

```powershell
# install Ollama from https://ollama.com, then:
ollama pull qwen2.5:3b
ollama serve            # exposes the OpenAI-compatible API on :11434
```

> The AI Reports and Management Copilot pages are part of the next build step and will use
> this configuration.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `streamlit: command not found` | Use `python -m streamlit run app.py` (the script dir may not be on PATH). |
| Dashboard says "No database found" | Run `python src/generate_data.py` first. |
| PowerShell won't activate the venv | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use `.\.venv\Scripts\python.exe` directly. |
| Port 8501 already in use | `python -m streamlit run app.py --server.port 8502`. |

---

## Resetting

```powershell
python src/generate_data.py     # re-seed the database from scratch
```

The generator drops and recreates all tables on each run, so it is safe to re-run any time.
