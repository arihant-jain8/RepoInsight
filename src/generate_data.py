"""Seed the central engineering.db with synthetic, git-shaped, type-aware data.

Each module is a repo of a given TYPE (network/backend/frontend/ai) and follows a
storyline via a 0..1 "severity" trajectory. For each commit we emit shared process
signals (build, integration, review, delivery) plus that module type's own quality
metrics (from METRIC_CATALOG) into commit_metrics. Engineers belong to a module's
team; one is the team lead. A subset of customer issues point at real commit ids in
the worst modules so the customer->commit traceability demo lights up.

Run once:  python src/generate_data.py
"""

import random
from datetime import datetime, timedelta

from faker import Faker

import database

fake = Faker()
random.seed(42)
Faker.seed(42)

WEEKS = 12
COMMITS_PER_WEEK = 8
BASE_DATE = datetime(2025, 1, 6)  # a Monday; W01 starts here

# --- Organisation: 2 units -> 4 projects -> 8 modules --------------------
ORG = [
    {
        "unit": "Infrastructure", "head": "Alice Nguyen",
        "projects": [
            {"name": "Core Services", "manager": "Bob Mensah",
             "modules": ["Networking", "Auth", "Security"]},
            {"name": "Platform Eng", "manager": "Carol Diaz",
             "modules": ["Platform", "Cloud"]},
        ],
    },
    {
        "unit": "Product", "head": "Dave Okafor",
        "projects": [
            {"name": "Data & ML", "manager": "Eve Park",
             "modules": ["ML Pipeline", "Backend"]},
            {"name": "Experience", "manager": "Frank Russo",
             "modules": ["UI/UX"]},
        ],
    },
]

# Per-module storyline. build_* interpolate build-success start->end over 12 wks.
# qual_* are a 0..1 quality SEVERITY trajectory (1 = worst) that drives every
# type-specific metric. late_days -> punctuality, latency -> review hours,
# major_rate -> share of major comments, issue_rate -> customer-issue probability.
MODULE_CONFIGS = {
    "Networking":  {"type": "network",  "team_size": 7,
                    "build_start": 0.93, "build_end": 0.68,
                    "qual_start": 0.20, "qual_end": 0.85,
                    "late_days": 15, "latency": 34, "major_rate": 0.50, "issue_rate": 0.28},
    "Auth":        {"type": "backend",  "team_size": 5,
                    "build_start": 0.82, "build_end": 0.55,
                    "qual_start": 0.45, "qual_end": 0.92,
                    "late_days": 11, "latency": 34, "major_rate": 0.55, "issue_rate": 0.35},
    "Security":    {"type": "backend",  "team_size": 6,
                    "build_start": 0.88, "build_end": 0.97,
                    "qual_start": 0.60, "qual_end": 0.12,
                    "late_days": 1, "latency": 14, "major_rate": 0.30, "issue_rate": 0.03},
    "Platform":    {"type": "backend",  "team_size": 8,
                    "build_start": 0.97, "build_end": 0.98,
                    "qual_start": 0.06, "qual_end": 0.05,
                    "late_days": 0, "latency": 10, "major_rate": 0.20, "issue_rate": 0.01},
    "Cloud":       {"type": "backend",  "team_size": 6,
                    "build_start": 0.95, "build_end": 0.93,
                    "qual_start": 0.22, "qual_end": 0.45,
                    "late_days": 4, "latency": 22, "major_rate": 0.35, "issue_rate": 0.08},
    "ML Pipeline": {"type": "ai",       "team_size": 4,
                    "build_start": 0.80, "build_end": 0.84,
                    "qual_start": 0.35, "qual_end": 0.55,
                    "late_days": 16, "latency": 36, "major_rate": 0.40, "issue_rate": 0.12},
    "Backend":     {"type": "backend",  "team_size": 6,
                    "build_start": 0.90, "build_end": 0.90,
                    "qual_start": 0.30, "qual_end": 0.33,
                    "late_days": 3, "latency": 20, "major_rate": 0.30, "issue_rate": 0.06},
    "UI/UX":       {"type": "frontend", "team_size": 5,
                    "build_start": 0.93, "build_end": 0.86,
                    "qual_start": 0.20, "qual_end": 0.50,
                    "late_days": 6, "latency": 26, "major_rate": 0.25, "issue_rate": 0.05},
}

# Type-aware quality metrics: (metric, label, unit, higher_is_better, weight, good, bad).
# good -> ~0 risk, bad -> ~100 risk. Weights per type sum to ~1.0.
METRIC_CATALOG = {
    "network": [
        ("clang_warnings", "Clang warnings / commit", "count", 0, 0.35, 10, 120),
        ("asan_failures", "ASAN failures / commit", "count", 0, 0.30, 0, 3),
        ("codechecker_critical", "CodeChecker criticals", "count", 0, 0.20, 0, 6),
        ("compile_warnings", "Compile warnings / commit", "count", 0, 0.15, 5, 90),
    ],
    "backend": [
        ("lint_errors", "Lint errors / commit", "count", 0, 0.25, 2, 40),
        ("test_coverage_pct", "Test coverage", "%", 1, 0.30, 85, 50),
        ("api_error_rate_pct", "API error rate", "%", 0, 0.25, 0.5, 5),
        ("sast_findings", "SAST findings", "count", 0, 0.20, 0, 10),
    ],
    "frontend": [
        ("eslint_errors", "ESLint errors / commit", "count", 0, 0.25, 2, 50),
        ("accessibility_score", "Accessibility score", "score", 1, 0.25, 95, 70),
        ("lighthouse_perf", "Lighthouse performance", "score", 1, 0.25, 90, 50),
        ("bundle_size_kb", "Bundle size", "KB", 0, 0.25, 200, 1200),
    ],
    "ai": [
        ("eval_accuracy_pct", "Eval accuracy", "%", 1, 0.35, 92, 70),
        ("data_validation_failures", "Data validation failures", "count", 0, 0.25, 0, 10),
        ("model_drift", "Model drift", "ratio", 0, 0.25, 0.02, 0.3),
        ("train_minutes", "Training time", "min", 0, 0.15, 20, 240),
    ],
}

CUSTOMERS = ["Acme Corp", "Globex", "Initech"]

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


def main():
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

    total_commits = total_comments = total_metrics = 0
    total_engineers = 0
    all_engineer_ids = []                 # global pool (for cross-team reviewers)
    module_engineers = {}                 # module_name -> [engineer_id, ...]
    module_commit_ids = {}                # module_name -> [(sha, week_idx, build_ok)]

    for unit in ORG:
        cur.execute("INSERT INTO units (name, head) VALUES (?, ?)",
                    (unit["unit"], unit["head"]))
        unit_id = cur.lastrowid

        for proj in unit["projects"]:
            cur.execute(
                "INSERT INTO projects (unit_id, name, manager) VALUES (?, ?, ?)",
                (unit_id, proj["name"], proj["manager"]))
            project_id = cur.lastrowid

            for mod_name in proj["modules"]:
                cfg = MODULE_CONFIGS[mod_name]
                repo = mod_name.lower().replace(" ", "-").replace("/", "-")
                # Insert module first (team_lead_id filled after engineers exist).
                cur.execute(
                    "INSERT INTO modules (project_id, name, type, repo_url, "
                    "team_lead_id, team_size) VALUES (?, ?, ?, ?, NULL, ?)",
                    (project_id, mod_name, cfg["type"],
                     f"https://git.example/{repo}.git", cfg["team_size"]))
                module_id = cur.lastrowid

                # Team: team_size engineers belonging to this module.
                team = []
                for _ in range(cfg["team_size"]):
                    cur.execute(
                        "INSERT INTO engineers (name, module_id) VALUES (?, ?)",
                        (fake.name(), module_id))
                    team.append(cur.lastrowid)
                total_engineers += len(team)
                module_engineers[mod_name] = team
                all_engineer_ids.extend(team)
                # First team member is the lead.
                cur.execute("UPDATE modules SET team_lead_id = ? WHERE id = ?",
                            (team[0], module_id))

                module_commit_ids[mod_name] = []
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
                            days=w * 7 + random.randint(0, 6),
                            hours=random.randint(0, 23))
                        targeted = committed_at + timedelta(days=7)
                        days_late = max(0, random.gauss(cfg["late_days"],
                                                        cfg["late_days"] * 0.4 + 1))
                        actual = targeted + timedelta(days=days_late)

                        build_success = 1 if random.random() < build_prob else 0
                        author_id = random.choice(team)
                        # Reviewer: usually a teammate, occasionally cross-team.
                        if random.random() < 0.15 and len(all_engineer_ids) > 1:
                            reviewer_id = random.choice(
                                [e for e in all_engineer_ids if e != author_id])
                        else:
                            reviewer_id = random.choice(
                                [e for e in team if e != author_id] or [author_id])
                        integ_total = random.randint(40, 80)
                        integ_failed = (random.randint(0, 5) if build_prob > 0.85
                                        else random.randint(3, 12))

                        cur.execute(
                            "INSERT INTO commits (commit_id, pr_id, module_id, "
                            "project_id, unit_id, week, committed_at, author_id, "
                            "reviewer_id, targeted_delivery, actual_delivery, "
                            "build_success, integration_total, integration_failed, "
                            "review_latency_hours, lines_changed) VALUES "
                            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (sha, f"{mod_name[:3].upper()}-PR-{pr_seq:04d}", module_id,
                             project_id, unit_id, f"W{w+1:02d}",
                             committed_at.isoformat(timespec="seconds"),
                             author_id, reviewer_id,
                             targeted.date().isoformat(), actual.date().isoformat(),
                             build_success, integ_total, integ_failed,
                             max(1.0, random.gauss(cfg["latency"], 8)),
                             random.randint(50, 800)))
                        total_commits += 1
                        module_commit_ids[mod_name].append((sha, w, build_success))

                        # Type-specific quality metrics for this commit.
                        for (metric, _l, unit_, _h, _w, good, bad) in catalog:
                            cur.execute(
                                "INSERT INTO commit_metrics (commit_id, metric, value) "
                                "VALUES (?,?,?)",
                                (sha, metric, metric_value(good, bad, sev, unit_)))
                            total_metrics += 1

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
                            total_comments += 1

    # --- Customers + issues ----------------------------------------------
    customer_ids = []
    for name in CUSTOMERS:
        cur.execute("INSERT INTO customers (name) VALUES (?)", (name,))
        customer_ids.append(cur.lastrowid)

    mod_lookup = {r["name"]: (r["id"], r["project_id"])
                  for r in conn.execute(
                      "SELECT id, name, project_id FROM modules").fetchall()}

    total_issues = 0
    severities = ["low", "medium", "high", "critical"]
    for mod_name, cfg in MODULE_CONFIGS.items():
        module_id, project_id = mod_lookup[mod_name]
        for (sha, w, build_success) in module_commit_ids[mod_name]:
            prob = cfg["issue_rate"] * (0.4 + w / WEEKS)
            if build_success == 0:
                prob *= 1.8
            if random.random() < prob:
                report = BASE_DATE + timedelta(days=w * 7 + random.randint(7, 21))
                resolved = (report + timedelta(days=random.randint(1, 20))
                            if random.random() < 0.7 else None)
                cur.execute(
                    "INSERT INTO customer_issues (customer_id, project_id, module_id, "
                    "commit_id, error_info, severity, report_time, resolve_time) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (random.choice(customer_ids), project_id, module_id, sha,
                     random.choice(ERROR_TEMPLATES),
                     random.choices(severities, weights=[3, 4, 2, 1])[0],
                     report.date().isoformat(),
                     resolved.date().isoformat() if resolved else None))
                total_issues += 1

    conn.commit()
    conn.close()

    print("Seeded central engineering.db:")
    print(f"  engineers       : {total_engineers} (across teams)")
    print(f"  commits         : {total_commits}")
    print(f"  commit_metrics  : {total_metrics}")
    print(f"  review_comments : {total_comments}")
    print(f"  customers       : {len(customer_ids)}")
    print(f"  customer_issues : {total_issues}")


if __name__ == "__main__":
    main()
