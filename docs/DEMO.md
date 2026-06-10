# Demo Script — Engineering Intelligence Copilot

A tight 4–5 minute walkthrough. The goal: land the **problem**, show the **hero moment**
(customer bug → exact commit), and close on the **fully-local AI** angle.

---

## One-line pitch

> "Engineering managers drown in build, quality, and review signals across many teams and
> can't tell *which* team is actually at risk or *why*. This copilot pulls every module's
> activity into one place, scores risk, traces customer bugs back to the exact commit that
> caused them, and explains it all — with a **fully local LLM**, no cloud."

---

## Before you start (setup checklist)

- [ ] Ollama running with the model: `ollama list` shows `qwen2.5:7b`
- [ ] Data seeded: `python src/generate_data.py`
- [ ] App running: `python -m streamlit run app.py` → http://localhost:8501
- [ ] Sidebar shows **`LLM: 🟢 connected · qwen2.5:7b`**
- [ ] (Optional) pre-click each AI button once so the model is warm (first call loads it)

---

## The 5-minute path

### 1. Executive Overview (45s) — the problem + the landscape
- Open the home page. Point at the KPI row: **1 critical, 3 warning, 4 healthy**.
- Point at the **risk bar chart**: "One glance — **Auth is RED**, Networking is climbing,
  Platform and Security are solid."
- Callouts: **highest risk = Auth**, **fastest improving = Security**.
- *Line:* "This is the whole org on one screen. Now let's see who needs help and why."

### 2. Unit Head (45s) — non-technical, business view
- Switch to **🏢 Unit Head**.
- Code-quality bar (with 👥 team size), **punctuality** (Auth/Networking slipping ~10–16 days),
  **errors per customer**.
- Click **🧠 Generate AI insight** → a business-framed org summary appears next to the charts.
- *Line:* "Same data, but written for a non-technical exec — no jargon."

### 3. Team Lead (90s) — the technical depth + AI
- Switch to **🛠️ Team Lead**, select **Auth**.
- Risk breakdown: **quality risk is the driver**; trend charts show build sliding and clang
  warnings climbing over 12 weeks.
- Scroll to **per-commit drill-down**: author, reviewer, major/minor comments, ASAN, clang.
- Click **🧠 Generate AI insight** → "Watch — the **local 7B model** writes a Team-Lead-level
  report grounded in these exact numbers, in ~15s, on this laptop's GPU."

### 4. Project Manager (60s) — the HERO MOMENT
- Switch to **📋 Project Manager**, select **Core Services** (Auth's project).
- Scroll to **Customer issues → commit traceability**.
- *Hero line:* "A customer — **Acme Corp** — reported a **high-severity latency spike**. We can
  trace it to the **exact commit `860030c6adb3` by Michele Williams**. Not 'the Auth team' —
  *this commit*. That's the difference between a dashboard and an answer."

### 5. Copilot (45s) — close
- Switch to **💬 Management Copilot**.
- Ask: **"Which module should I focus on this week and why?"**
- It answers with real numbers (Auth, RED, the drivers).
- *Closing line:* "Every number is deterministic and auditable; the LLM only explains it —
  and it runs **entirely local on an AMD/NVIDIA GPU**, so no engineering data ever leaves the
  building. Swapping to the AMD ROCm box is one config line."

---

## Anticipated judge questions (have these ready)

**"Is this real data?"**
> "No — it's synthetic for the demo, but the schema is **git-shaped**: a real per-repo
> ingestion worker drops in with no schema change. Commit IDs, authors, reviewers, and review
> comments map straight from `git log` + the GitHub API."

**"What's the AI actually doing — isn't it just another LLM wrapper?"**
> "The differentiator isn't the LLM — it's the **commit-level traceability** and **role-based
> intelligence**. The LLM is a thin explanation layer over deterministic analytics; we feed it
> a summarised JSON context and it never invents numbers. If it's offline, every view still
> works with a data-driven fallback."

**"Why local instead of GPT-4?"**
> "Engineering activity is sensitive IP. Fully local means it can run inside a company's
> network with zero data egress. It's pluggable — same OpenAI-compatible code runs on Ollama
> here and vLLM + Qwen on an AMD ROCm box."

**"How is risk scored?"**
> "A normalised 0–100 blend: 50% quality (clang/ASAN/integration), 30% delivery (build
> success), 20% collaboration (review latency + unreviewed commits). Transparent and tunable."

---

## If something breaks on stage

- **AI button spins forever / errors** → the sidebar will show `⚪ offline`; the page still
  renders a data-driven fallback. Say: "and it degrades gracefully when the model's busy."
- **App won't start** → `python -m streamlit run app.py` (not bare `streamlit`).
- **Empty dashboard** → re-seed: `python src/generate_data.py`.

> Note: exact commit hashes/authors are regenerated each `generate_data.py` run. Re-grab a
> fresh Auth example before the demo, or seed once and don't re-run.
