"""Seed the central engineering.db with synthetic, git-shaped data.

This simulates the per-module ingestion agents: for each module (a repo) it
fabricates ~8 commits/week over 12 weeks, each with an author, a reviewer, a few
review comments (with severity), CI/quality signals trending along the module's
storyline, and planned-vs-actual delivery. It then creates 3 customers and a set
of customer issues, a subset of which point at REAL generated commit ids in the
worst-quality modules so the customer->commit traceability demo lights up.

Run once:  python generate_data.py
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
# Each module is its own repo (multi-repo) and follows a storyline so trends
# are meaningful, not noise.
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

# Per-module storyline + metadata. build/clang interpolate start->end over 12 wks.
# asan_rate / issue_rate are per-commit probabilities. late_days drives punctuality.
# major_rate is the share of review comments marked 'major'.
MODULE_CONFIGS = {
    "Networking":  {"type": "network",  "team_size": 7, "lead": "Grace Liu",
                    "build_start": 0.94, "build_end": 0.78, "clang_start": 18, "clang_end": 118,
                    "asan_rate": 0.10, "issue_rate": 0.22, "late_days": 12, "major_rate": 0.45,
                    "latency": 30},
    "Auth":        {"type": "backend",  "team_size": 5, "lead": "Hassan Ali",
                    "build_start": 0.85, "build_end": 0.72, "clang_start": 30, "clang_end": 80,
                    "asan_rate": 0.40, "issue_rate": 0.30, "late_days": 9,  "major_rate": 0.50,
                    "latency": 28},
    "Security":    {"type": "backend",  "team_size": 6, "lead": "Ivy Chen",
                    "build_start": 0.88, "build_end": 0.97, "clang_start": 60, "clang_end": 12,
                    "asan_rate": 0.02, "issue_rate": 0.03, "late_days": 1,  "major_rate": 0.30,
                    "latency": 14},
    "Platform":    {"type": "backend",  "team_size": 8, "lead": "Jack Owens",
                    "build_start": 0.97, "build_end": 0.98, "clang_start": 10, "clang_end": 9,
                    "asan_rate": 0.01, "issue_rate": 0.01, "late_days": 0,  "major_rate": 0.20,
                    "latency": 10},
    "Cloud":       {"type": "backend",  "team_size": 6, "lead": "Kara Singh",
                    "build_start": 0.95, "build_end": 0.93, "clang_start": 22, "clang_end": 40,
                    "asan_rate": 0.05, "issue_rate": 0.08, "late_days": 4,  "major_rate": 0.35,
                    "latency": 22},
    "ML Pipeline": {"type": "ai",       "team_size": 4, "lead": "Leo Martins",
                    "build_start": 0.80, "build_end": 0.84, "clang_start": 25, "clang_end": 45,
                    "asan_rate": 0.12, "issue_rate": 0.12, "late_days": 16, "major_rate": 0.40,
                    "latency": 36},
    "Backend":     {"type": "backend",  "team_size": 6, "lead": "Mia Rossi",
                    "build_start": 0.90, "build_end": 0.90, "clang_start": 28, "clang_end": 30,
                    "asan_rate": 0.06, "issue_rate": 0.06, "late_days": 3,  "major_rate": 0.30,
                    "latency": 20},
    "UI/UX":       {"type": "frontend", "team_size": 5, "lead": "Noah Berg",
                    "build_start": 0.93, "build_end": 0.86, "clang_start": 15, "clang_end": 28,
                    "asan_rate": 0.03, "issue_rate": 0.05, "late_days": 6,  "major_rate": 0.25,
                    "latency": 26},
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


def fake_sha():
    return "".join(random.choice("0123456789abcdef") for _ in range(12))


def main():
    conn = database.connect()
    database.init_schema(conn)
    cur = conn.cursor()

    # --- Engineers pool ---------------------------------------------------
    engineer_ids = []
    for _ in range(24):
        cur.execute("INSERT INTO engineers (name) VALUES (?)", (fake.name(),))
        engineer_ids.append(cur.lastrowid)

    # --- Hierarchy + commits ---------------------------------------------
    total_commits = 0
    total_comments = 0
    module_commit_ids = {}  # module_name -> list of (commit_id, week_idx, build_success)

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
                cur.execute(
                    "INSERT INTO modules (project_id, name, type, repo_url, "
                    "team_lead, team_size) VALUES (?, ?, ?, ?, ?, ?)",
                    (project_id, mod_name, cfg["type"],
                     f"https://git.example/{repo}.git", cfg["lead"], cfg["team_size"]))
                module_id = cur.lastrowid
                module_commit_ids[mod_name] = []

                pr_seq = 0
                for w in range(WEEKS):
                    t = w / (WEEKS - 1)
                    build_prob = lerp(cfg["build_start"], cfg["build_end"], t)
                    clang_base = lerp(cfg["clang_start"], cfg["clang_end"], t)

                    for _ in range(COMMITS_PER_WEEK):
                        pr_seq += 1
                        sha = fake_sha()
                        committed_at = BASE_DATE + timedelta(
                            days=w * 7 + random.randint(0, 6),
                            hours=random.randint(0, 23))
                        targeted = committed_at + timedelta(days=7)
                        days_late = max(0, random.gauss(cfg["late_days"],
                                                        cfg["late_days"] * 0.4 + 1))
                        actual = targeted + timedelta(days=days_late)

                        build_success = 1 if random.random() < build_prob else 0
                        clang = max(0, int(random.gauss(clang_base, clang_base * 0.15)))
                        author_id = random.choice(engineer_ids)
                        reviewer_id = random.choice(
                            [e for e in engineer_ids if e != author_id])
                        integ_total = random.randint(40, 80)
                        integ_failed = (random.randint(0, 5) if build_prob > 0.85
                                        else random.randint(3, 12))

                        cur.execute(
                            "INSERT INTO commits (commit_id, pr_id, module_id, "
                            "project_id, unit_id, week, committed_at, author_id, "
                            "reviewer_id, targeted_delivery, actual_delivery, "
                            "build_success, compile_warnings, clang_warnings, "
                            "codechecker_findings, codechecker_critical, asan_failures, "
                            "integration_total, integration_failed, review_latency_hours, "
                            "lines_changed) VALUES "
                            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (sha, f"{mod_name[:3].upper()}-PR-{pr_seq:04d}", module_id,
                             project_id, unit_id, f"W{w+1:02d}",
                             committed_at.isoformat(timespec="seconds"),
                             author_id, reviewer_id,
                             targeted.date().isoformat(), actual.date().isoformat(),
                             build_success,
                             max(0, int(random.gauss(clang * 0.3, 2))),
                             clang,
                             max(0, int(random.gauss(clang * 0.4, 3))),
                             max(0, int(random.gauss(clang * 0.05, 1))),
                             1 if random.random() < cfg["asan_rate"] else 0,
                             integ_total, integ_failed,
                             max(1.0, random.gauss(cfg["latency"], 8)),
                             random.randint(50, 800)))
                        total_commits += 1
                        module_commit_ids[mod_name].append((sha, w, build_success))

                        # Review comments (first-class rows, with severity)
                        n_comments = max(0, int(random.gauss(3, 2)))
                        for _ in range(n_comments):
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

    # Look up module/project ids for issue rows.
    mod_lookup = {r["name"]: (r["id"], r["project_id"])
                  for r in conn.execute(
                      "SELECT id, name, project_id FROM modules").fetchall()}

    total_issues = 0
    severities = ["low", "medium", "high", "critical"]
    for mod_name, cfg in MODULE_CONFIGS.items():
        module_id, project_id = mod_lookup[mod_name]
        commits = module_commit_ids[mod_name]
        for (sha, w, build_success) in commits:
            # Issues cluster on later weeks and worse builds; tie to a real commit.
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
    print(f"  engineers       : {len(engineer_ids)}")
    print(f"  commits         : {total_commits}")
    print(f"  review_comments : {total_comments}")
    print(f"  customers       : {len(customer_ids)}")
    print(f"  customer_issues : {total_issues}")


if __name__ == "__main__":
    main()
