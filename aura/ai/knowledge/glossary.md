# Glossary, enums, and interpretation rules

## Outcome / operational metrics (reported separately from risk_score)

- **MTTR** — mean time to resolution, in days: average of (resolve_time − raised_time) over
  resolved Jira tickets. Available per module and per account.
- **AI tooling efficiency** (per account) — `manual_triage_hours_saved`,
  `mttr_reduction_percentage` (percent improvement in MTTR from AI assistance), and
  `ai_resolved_tickets_count`.
- **Punctuality / avg_days_late** — average of (actual_delivery − targeted_delivery) in days.
  Positive = shipping late.
- **Customer issues** — Jira tickets, counted by severity and status. "Open" excludes Resolved.
- **ai_generated_percentage** — share of a commit authored by an AI agent (0–100; 0 when no
  agent). **ai_agent_used** — e.g. GitHub Copilot, Devin Agent, or N/A.
- **code_churn_score** — low / medium / high (heuristic on lines added).
- **Review comments** — counted by severity: major vs minor.

## Enums (the exact allowed values)

- Ticket / customer-issue severity: **low, medium, high, critical**.
- Review-comment severity: **major, minor**.
- Ticket status: **Pending, In Progress, Resolved**.
- Ticket lifecycle_status: **study stage, implementation stage, review stage, testing stage,
  deployment stage**.
- issue_status (module), customer_status (account), risk_level: **low, medium, high**.
- Module type: **network, backend, frontend, ai**.

## Interpretation rules (avoid these mistakes)

- **quality_trend** is the percent change in quality **RISK** over the window. A **positive**
  value means risk ROSE → quality got **WORSE**. A negative value means it improved. Never call
  a positive quality_trend an "improvement".
- **quality_risk is only one component (50%) of risk_score**, not the whole thing. Do not equate
  them, and do not describe quality_risk as including build/integration/review (those are
  delivery and collaboration risk).
- A **module** is a single codebase (e.g. "Ledger Clearing Engine"). A **project** is a program
  of work (e.g. "5G Core Rollout") that contains modules. Don't confuse the two.
- `team_lead_id` is an engineer id, not a name — resolve it to a person before naming a lead.
- Review comments (major/minor) are not a target to maximize — never recommend "increase
  review comments". The collaboration signal is unreviewed_pct (commits merged with no review)
  and review latency.
