"""Seed the central engineering.db with synthetic, git-shaped, type-aware data.

Each module is a repo of a given TYPE (network/backend/frontend/ai) and follows a
storyline via a 0..1 "severity" trajectory. For each commit we emit shared process
signals (build, integration, review, delivery) plus that module type's own quality
metrics (from METRIC_CATALOG) into commit_metrics. Engineers belong to a module's
team; one is the team lead. A subset of customer issues point at real commit ids in
the worst modules so the customer->commit traceability demo lights up.

Run once:  python src/generate_data.py
"""

import os
import random
from datetime import datetime, timedelta

from faker import Faker

import config
import database

fake = Faker()
random.seed(42)
Faker.seed(42)

WEEKS = 12
COMMITS_PER_WEEK = 8
BASE_DATE = datetime(2025, 1, 6)  # a Monday; W01 starts here

# --- Organisation: 2 verticals -> 2 accounts -> 4 projects -> 12 modules ------
# Unit Heads + Project Managers are named (The Office); team leads/engineers are
# Faker-generated. customer = end client (AT&T/Verizon/Citibank/Barclays).
ORG = [
    {
        "vertical": "Telecomm", "head": "Michael Scott",
        "accounts": [
            {
                "account": "GlobalTel Wireless", "customer_status": "high",
                "projects": [
                    {"name": "5G Core Rollout", "customer": "AT&T",
                     "manager": "Jim Halpert",
                     "modules": ["RAN Packet Parser", "Baseband Processing",
                                 "OSS/BSS Billing Interface"]},
                    {"name": "Edge Computing Layer", "customer": "Verizon",
                     "manager": "Pam Beesly",
                     "modules": ["MEC Signal Handler", "Baseband Telemetry Stream",
                                 "RAN Automation Engine"]},
                ],
            },
        ],
    },
    {
        "vertical": "BFSI", "head": "David Wallace",
        "accounts": [
            {
                "account": "Nexus Digital Bank", "customer_status": "high",
                "projects": [
                    {"name": "Instant Payments Core", "customer": "Citibank",
                     "manager": "Dwight Schrute",
                     "modules": ["ISO20022 Message Parser", "Ledger Clearing Engine",
                                 "Fraud Analytics Stream"]},
                    {"name": "Wealth Management APIs", "customer": "Barclays",
                     "manager": "Oscar Martinez",
                     "modules": ["Portfolio Valuation Engine", "KYC Document Sanitizer",
                                 "Trade Execution Broker"]},
                ],
            },
        ],
    },
]

# Per-module storyline. type -> which metric_catalog applies. issue_status is the
# AURA.md label; build/qual trajectories are tuned so the risk engine INDEPENDENTLY
# lands each module on that label (high >=60, medium 30-59, low <30). qual_* is a
# 0..1 quality SEVERITY trajectory (1 = worst); late_days -> punctuality,
# latency -> review hours, major_rate -> major comments, issue_rate -> incidents.
MODULE_CONFIGS = {
    # --- high : bad quality + falling builds ------------------------------
    "RAN Packet Parser":         {"type": "network", "team_size": 7, "issue_status": "high",
                                  "build_start": 0.85, "build_end": 0.65,
                                  "qual_start": 0.45, "qual_end": 0.88,
                                  "late_days": 14, "latency": 38, "major_rate": 0.55, "issue_rate": 0.30},
    "Ledger Clearing Engine":    {"type": "backend", "team_size": 8, "issue_status": "high",
                                  "build_start": 0.82, "build_end": 0.66,
                                  "qual_start": 0.50, "qual_end": 0.86,
                                  "late_days": 12, "latency": 36, "major_rate": 0.55, "issue_rate": 0.32},
    # --- medium -----------------------------------------------------------
    "Baseband Processing":       {"type": "network", "team_size": 6, "issue_status": "medium",
                                  "build_start": 0.90, "build_end": 0.80,
                                  "qual_start": 0.30, "qual_end": 0.52,
                                  "late_days": 7, "latency": 26, "major_rate": 0.40, "issue_rate": 0.12},
    "RAN Automation Engine":     {"type": "backend", "team_size": 5, "issue_status": "medium",
                                  "build_start": 0.89, "build_end": 0.81,
                                  "qual_start": 0.28, "qual_end": 0.50,
                                  "late_days": 6, "latency": 25, "major_rate": 0.38, "issue_rate": 0.11},
    "ISO20022 Message Parser":   {"type": "backend", "team_size": 6, "issue_status": "medium",
                                  "build_start": 0.88, "build_end": 0.82,
                                  "qual_start": 0.32, "qual_end": 0.54,
                                  "late_days": 8, "latency": 27, "major_rate": 0.42, "issue_rate": 0.13},
    # --- low : good quality + healthy builds ------------------------------
    "OSS/BSS Billing Interface": {"type": "backend", "team_size": 6, "issue_status": "low",
                                  "build_start": 0.95, "build_end": 0.96,
                                  "qual_start": 0.16, "qual_end": 0.14,
                                  "late_days": 1, "latency": 12, "major_rate": 0.25, "issue_rate": 0.03},
    "MEC Signal Handler":        {"type": "network", "team_size": 5, "issue_status": "low",
                                  "build_start": 0.94, "build_end": 0.95,
                                  "qual_start": 0.18, "qual_end": 0.15,
                                  "late_days": 2, "latency": 13, "major_rate": 0.24, "issue_rate": 0.04},
    "Baseband Telemetry Stream": {"type": "network", "team_size": 5, "issue_status": "low",
                                  "build_start": 0.95, "build_end": 0.97,
                                  "qual_start": 0.15, "qual_end": 0.12,
                                  "late_days": 1, "latency": 11, "major_rate": 0.22, "issue_rate": 0.03},
    "Fraud Analytics Stream":    {"type": "ai", "team_size": 4, "issue_status": "low",
                                  "build_start": 0.93, "build_end": 0.95,
                                  "qual_start": 0.20, "qual_end": 0.16,
                                  "late_days": 2, "latency": 14, "major_rate": 0.26, "issue_rate": 0.05},
    "Portfolio Valuation Engine":{"type": "backend", "team_size": 6, "issue_status": "low",
                                  "build_start": 0.96, "build_end": 0.96,
                                  "qual_start": 0.14, "qual_end": 0.13,
                                  "late_days": 1, "latency": 10, "major_rate": 0.22, "issue_rate": 0.02},
    "KYC Document Sanitizer":    {"type": "ai", "team_size": 4, "issue_status": "low",
                                  "build_start": 0.94, "build_end": 0.95,
                                  "qual_start": 0.18, "qual_end": 0.15,
                                  "late_days": 2, "latency": 13, "major_rate": 0.24, "issue_rate": 0.04},
    "Trade Execution Broker":    {"type": "backend", "team_size": 6, "issue_status": "low",
                                  "build_start": 0.95, "build_end": 0.96,
                                  "qual_start": 0.15, "qual_end": 0.13,
                                  "late_days": 1, "latency": 11, "major_rate": 0.23, "issue_rate": 0.03},
}

# Type-aware quality metrics: (metric, label, unit, higher_is_better, weight, good, bad).
# good -> ~0 risk, bad -> ~100 risk. Weights per type sum to ~1.0.
METRIC_CATALOG = {
    "network": [   # telecom signal/packet C/C++: memory safety + static + runtime
        ("asan_failures", "ASAN failures / commit", "count", 0, 0.30, 0, 3),
        ("clang_warnings", "Clang warnings / commit", "count", 0, 0.20, 10, 120),
        ("packet_drop_rate_pct", "Packet drop rate", "%", 0, 0.30, 0.05, 2.0),
        ("p99_latency_ms", "p99 latency", "ms", 0, 0.20, 20, 150),
    ],
    "backend": [   # services/payments: coverage + txn correctness + security + lint
        ("test_coverage_pct", "Test coverage", "%", 1, 0.25, 85, 50),
        ("transaction_error_rate_pct", "Transaction error rate", "%", 0, 0.30, 0.1, 3.0),
        ("sast_findings", "SAST findings", "count", 0, 0.25, 0, 10),
        ("lint_errors", "Lint errors / commit", "count", 0, 0.20, 2, 40),
    ],
    "frontend": [  # unused (no UI modules among the 12) — kept for future use
        ("eslint_errors", "ESLint errors / commit", "count", 0, 0.25, 2, 50),
        ("accessibility_score", "Accessibility score", "score", 1, 0.25, 95, 70),
        ("lighthouse_perf", "Lighthouse performance", "score", 1, 0.25, 90, 50),
        ("bundle_size_kb", "Bundle size", "KB", 0, 0.25, 200, 1200),
    ],
    "ai": [        # fraud/KYC ML: accuracy + false-positives + drift + data validation
        ("eval_accuracy_pct", "Eval accuracy", "%", 1, 0.30, 92, 70),
        ("false_positive_rate_pct", "False positive rate", "%", 0, 0.25, 1, 15),
        ("model_drift", "Model drift", "ratio", 0, 0.25, 0.02, 0.3),
        ("data_validation_failures", "Data validation failures", "count", 0, 0.20, 0, 10),
    ],
}

COMMENT_TEMPLATES = {
    "major": [
        "Possible null deref on the error path here.",
        "This introduces a race condition under concurrent access.",
        "Memory leak: the buffer is never freed on early return.",
        "This breaks the public API contract — needs a migration.",
        "Unbounded loop could hang on malformed input.",
        "Security: input is not validated before use.",
    ],
    "minor": [
        "Nit: rename this variable for clarity.",
        "Consider extracting this into a helper.",
        "Missing a docstring on this function.",
        "Style: prefer early return here.",
        "Add a unit test for this branch.",
        "Typo in the log message.",
    ],
}

ERROR_TEMPLATES = [
    "Intermittent 500 errors under load",
    "Login fails for SSO users",
    "Data corruption in export job",
    "Latency spike on the read path",
    "Crash on malformed payload",
    "Incorrect totals in the dashboard",
    "Timeout connecting to upstream service",
]


def lerp(a, b, t):
    """Linear interpolate between a and b; t in [0, 1]."""
    return a + (b - a) * t


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def fake_sha():
    return "".join(random.choice("0123456789abcdef") for _ in range(12))


def metric_value(good, bad, sev, unit):
    """A per-commit metric value at severity sev (0..1), respecting unit + noise."""
    v = good + (bad - good) * sev + random.gauss(0, abs(bad - good) * 0.08)
    if unit == "count":
        return float(max(0, round(v)))
    if unit == "ratio":
        return round(clamp(v, 0.0, 1.0), 3)
    if unit in ("KB", "min"):
        return float(max(0, round(v)))
    if unit in ("%", "score"):
        return round(clamp(v, 0.0, 100.0), 1)
    return round(max(0.0, v), 2)


def seed_module(cur, project_id, mod_name, pools):
    """Seed one module: row + team + 12 weeks of commits, metrics, comments.
    Mutates `pools` (shared engineer pool, per-module commit ids, running counts).
    """
    cfg = MODULE_CONFIGS[mod_name]
    repo = mod_name.lower().replace(" ", "-").replace("/", "-")
    # Insert module first (team_lead_id filled after engineers exist).
    cur.execute(
        "INSERT INTO modules (project_id, name, type, repo_url, team_lead_id, "
        "team_size, issue_status) VALUES (?, ?, ?, ?, NULL, ?, ?)",
        (project_id, mod_name, cfg["type"], f"https://git.example/{repo}.git",
         cfg["team_size"], cfg["issue_status"]))
    module_id = cur.lastrowid

    # Team: team_size engineers belonging to this module (first is the lead).
    team = []
    for _ in range(cfg["team_size"]):
        cur.execute("INSERT INTO engineers (name, module_id) VALUES (?, ?)",
                    (fake.name(), module_id))
        team.append(cur.lastrowid)
    pools["engineers"] += len(team)
    pools["all_engineer_ids"].extend(team)
    cur.execute("UPDATE modules SET team_lead_id = ? WHERE id = ?",
                (team[0], module_id))

    pools["module_commit_ids"][mod_name] = []
    catalog = METRIC_CATALOG[cfg["type"]]
    pr_seq = 0
    for w in range(WEEKS):
        t = w / (WEEKS - 1)
        build_prob = lerp(cfg["build_start"], cfg["build_end"], t)
        sev_base = lerp(cfg["qual_start"], cfg["qual_end"], t)

        for _ in range(COMMITS_PER_WEEK):
            pr_seq += 1
            sha = fake_sha()
            sev = clamp(sev_base + random.gauss(0, 0.05), 0.0, 1.0)
            committed_at = BASE_DATE + timedelta(
                days=w * 7 + random.randint(0, 6), hours=random.randint(0, 23))
            targeted = committed_at + timedelta(days=7)
            days_late = max(0, random.gauss(cfg["late_days"],
                                            cfg["late_days"] * 0.4 + 1))
            actual = targeted + timedelta(days=days_late)

            build_success = 1 if random.random() < build_prob else 0
            author_id = random.choice(team)
            # Reviewer: usually a teammate, occasionally cross-team.
            pool = pools["all_engineer_ids"]
            if random.random() < 0.15 and len(pool) > 1:
                reviewer_id = random.choice([e for e in pool if e != author_id])
            else:
                reviewer_id = random.choice(
                    [e for e in team if e != author_id] or [author_id])
            integ_total = random.randint(40, 80)
            integ_failed = (random.randint(0, 5) if build_prob > 0.85
                            else random.randint(3, 12))

            # AI tooling fields (AURA.md git_logs). N/A agent => 0% AI-generated.
            lines_added = random.randint(50, 300)
            lines_removed = random.randint(5, 50)
            churn = ("high" if lines_added > 200 else
                     "medium" if lines_added > 100 else "low")
            ai_agent = random.choice(["GitHub Copilot", "Devin Agent", "N/A"])
            ai_pct = 0.0 if ai_agent == "N/A" else round(random.uniform(20.0, 95.0), 2)

            cur.execute(
                "INSERT INTO commits (commit_id, pr_id, module_id, project_id, "
                "week, committed_at, author_id, reviewer_id, targeted_delivery, "
                "actual_delivery, build_success, integration_total, "
                "integration_failed, review_latency_hours, lines_changed, "
                "lines_added, lines_removed, code_churn_score, ai_agent_used, "
                "ai_generated_percentage) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sha, f"{mod_name[:3].upper()}-PR-{pr_seq:04d}", module_id,
                 project_id, f"W{w+1:02d}",
                 committed_at.isoformat(timespec="seconds"),
                 author_id, reviewer_id,
                 targeted.date().isoformat(), actual.date().isoformat(),
                 build_success, integ_total, integ_failed,
                 max(1.0, random.gauss(cfg["latency"], 8)),
                 lines_added + lines_removed,
                 lines_added, lines_removed, churn, ai_agent, ai_pct))
            pools["commits"] += 1
            pools["module_commit_ids"][mod_name].append((sha, w, build_success))

            # Type-specific quality metrics for this commit.
            for (metric, _l, unit_, _h, _w, good, bad) in catalog:
                cur.execute(
                    "INSERT INTO commit_metrics (commit_id, metric, value) "
                    "VALUES (?,?,?)",
                    (sha, metric, metric_value(good, bad, sev, unit_)))
                pools["metrics"] += 1

            # Review comments (first-class rows, with severity).
            for _ in range(max(0, int(random.gauss(3, 2)))):
                severity = ("major" if random.random() < cfg["major_rate"]
                            else "minor")
                cur.execute(
                    "INSERT INTO review_comments (commit_id, reviewer_id, "
                    "comment, severity, created_at) VALUES (?,?,?,?,?)",
                    (sha, reviewer_id,
                     random.choice(COMMENT_TEMPLATES[severity]), severity,
                     (committed_at + timedelta(hours=random.randint(1, 48)))
                     .isoformat(timespec="seconds")))
                pools["comments"] += 1


def main():
    # Fresh reseed: start from a clean DB so schema changes (e.g. the
    # customer_issues table->view transition) never collide with stale objects.
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
    conn = database.connect()
    database.init_schema(conn)
    cur = conn.cursor()

    # --- Metric catalog ---------------------------------------------------
    for mtype, metrics in METRIC_CATALOG.items():
        for (metric, label, unit, hib, weight, good, bad) in metrics:
            cur.execute(
                "INSERT INTO metric_catalog (metric, module_type, label, unit, "
                "higher_is_better, weight, good, bad) VALUES (?,?,?,?,?,?,?,?)",
                (metric, mtype, label, unit, hib, weight, good, bad))

    pools = {"all_engineer_ids": [], "module_commit_ids": {},
             "engineers": 0, "commits": 0, "metrics": 0, "comments": 0}

    # --- Hierarchy: vertical -> account -> project -> module -------------
    for vertical in ORG:
        cur.execute("INSERT INTO vertical_units (name, head) VALUES (?, ?)",
                    (vertical["vertical"], vertical["head"]))
        vertical_id = cur.lastrowid

        for account in vertical["accounts"]:
            cur.execute(
                "INSERT INTO accounts (vertical_id, name, customer_status) "
                "VALUES (?, ?, ?)",
                (vertical_id, account["account"], account["customer_status"]))
            account_id = cur.lastrowid

            # Per-account AI tooling efficiency (illustrative figures).
            cur.execute(
                "INSERT INTO ai_tool_efficiency (account_id, "
                "manual_triage_hours_saved, mttr_reduction_percentage, "
                "ai_resolved_tickets_count) VALUES (?,?,?,?)",
                (account_id, round(random.uniform(30, 60), 1),
                 round(random.uniform(70, 90), 1), random.randint(15, 30)))

            for proj in account["projects"]:
                cur.execute(
                    "INSERT INTO projects (account_id, name, customer, manager) "
                    "VALUES (?, ?, ?, ?)",
                    (account_id, proj["name"], proj["customer"], proj["manager"]))
                project_id = cur.lastrowid

                for mod_name in proj["modules"]:
                    seed_module(cur, project_id, mod_name, pools)

    # --- Jira tickets (customer incidents) + telemetry -------------------
    mod_lookup = {r["name"]: r["id"]
                  for r in conn.execute("SELECT id, name FROM modules").fetchall()}
    severities = ["low", "medium", "high", "critical"]
    lifecycles = ["study stage", "implementation stage", "review stage",
                  "testing stage"]
    # Telemetry bands per issue_status: (drop_lo,drop_hi, lat_lo,lat_hi, cpu_lo,cpu_hi)
    perf_band = {"high":   (0.04, 0.10, 40, 90, 85, 96),
                 "medium": (0.01, 0.04, 25, 45, 65, 85),
                 "low":    (0.00, 0.01, 10, 25, 40, 65)}
    total_tickets = total_perf = tkt_seq = 0

    for mod_name, cfg in MODULE_CONFIGS.items():
        module_id = mod_lookup[mod_name]
        module_tickets = []
        # Tickets traced to specific commits (issue -> commit lineage).
        for (sha, w, build_success) in pools["module_commit_ids"][mod_name]:
            prob = cfg["issue_rate"] * (0.4 + w / WEEKS)
            if build_success == 0:
                prob *= 1.8
            if random.random() < prob:
                tkt_seq += 1
                ticket_id = f"JIRA-{mod_name[:3].upper()}-{tkt_seq:04d}"
                report = BASE_DATE + timedelta(days=w * 7 + random.randint(7, 21))
                resolved = (report + timedelta(days=random.randint(1, 20))
                            if random.random() < 0.7 else None)
                summary = random.choice(ERROR_TEMPLATES)
                cur.execute(
                    "INSERT INTO jira_logs (ticket_id, module_id, commit_id, "
                    "ticket_type, summary, severity, status, raised_time, "
                    "resolve_time, automation_percentage, assigned_to, task_name, "
                    "lifecycle_status, completed_date) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ticket_id, module_id, sha, "customer_incident", summary,
                     random.choices(severities, weights=[3, 4, 2, 1])[0],
                     "Resolved" if resolved else "In Progress",
                     report.date().isoformat(),
                     resolved.date().isoformat() if resolved else None,
                     round(random.uniform(60, 95), 1),
                     f"Dev_{random.randint(100, 9999):04d}", f"Fix: {summary}",
                     "deployment stage" if resolved else random.choice(lifecycles),
                     resolved.date().isoformat() if resolved else None))
                module_tickets.append(ticket_id)
                total_tickets += 1

        # Telemetry samples (6 per module), severity-tuned to issue_status.
        lo_d, hi_d, lo_l, hi_l, lo_c, hi_c = perf_band[cfg["issue_status"]]
        incidents = (",".join(module_tickets[:2])
                     if cfg["issue_status"] == "high" else "")
        for s in range(6):
            ts = BASE_DATE + timedelta(days=s * 14 + random.randint(0, 6),
                                       hours=random.randint(0, 23))
            cur.execute(
                "INSERT INTO performance_data (module_id, metric_source, timestamp, "
                "issue_status, packet_drop_rate, latency_ms, "
                "cpu_utilization_percentage, associated_incidents) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (module_id, f"{mod_name} APM", ts.isoformat(timespec="seconds"),
                 cfg["issue_status"], round(random.uniform(lo_d, hi_d), 3),
                 round(random.uniform(lo_l, hi_l), 1),
                 round(random.uniform(lo_c, hi_c), 1), incidents))
            total_perf += 1

    conn.commit()
    conn.close()

    print("Seeded central engineering.db:")
    print(f"  engineers       : {pools['engineers']} (across teams)")
    print(f"  commits         : {pools['commits']}")
    print(f"  commit_metrics  : {pools['metrics']}")
    print(f"  review_comments : {pools['comments']}")
    print(f"  jira_logs       : {total_tickets}")
    print(f"  performance_data: {total_perf}")


if __name__ == "__main__":
    main()
