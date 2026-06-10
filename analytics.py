"""Analytics engine: turn raw commits into role-ready metrics.

Reads through database.query / database.query_df (each opens its own connection,
so no connection is threaded through these functions). Feeds the risk engine,
the dashboards, and the LLM context builder.
"""

import database
import risk_engine


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def _all_weeks() -> list[str]:
    """Distinct week labels present in the data, ascending (e.g. W01..W12)."""
    return [r["week"] for r in
            database.query("SELECT DISTINCT week FROM commits ORDER BY week")]


def _last_weeks(n: int) -> list[str]:
    weeks = _all_weeks()
    return weeks[-n:] if n < len(weeks) else weeks


def _placeholders(items) -> str:
    return ",".join("?" for _ in items)


# -------------------------------------------------------------------------
# Module-level
# -------------------------------------------------------------------------
def get_module_health(module_id: int, weeks: int = 4) -> dict:
    """Aggregate metrics for a module over the last N weeks (risk-engine input)."""
    wks = _last_weeks(weeks)
    ph = _placeholders(wks)

    meta = database.query(
        "SELECT m.id, m.name, m.type, m.team_lead, m.team_size, "
        "p.id AS project_id, p.name AS project, u.id AS unit_id, u.name AS unit "
        "FROM modules m JOIN projects p ON p.id = m.project_id "
        "JOIN units u ON u.id = p.unit_id WHERE m.id = ?",
        (module_id,),
    )[0]

    agg = database.query(
        f"SELECT COUNT(*) AS commits, "
        f"ROUND(100.0 * SUM(build_success) / COUNT(*), 1) AS build_success_rate, "
        f"ROUND(AVG(clang_warnings), 1) AS avg_clang_warnings_per_commit, "
        f"ROUND(AVG(asan_failures), 3) AS avg_asan_per_commit, "
        f"SUM(asan_failures) AS total_asan_failures, "
        f"ROUND(100.0 * SUM(integration_failed) / "
        f"      NULLIF(SUM(integration_total), 0), 1) AS integration_fail_pct, "
        f"ROUND(AVG(review_latency_hours), 1) AS avg_review_latency_hours "
        f"FROM commits WHERE module_id = ? AND week IN ({ph})",
        (module_id, *wks),
    )[0]

    # Share of commits in the window that merged with zero review comments.
    unrev = database.query(
        f"SELECT ROUND(100.0 * SUM(CASE WHEN rc.n IS NULL THEN 1 ELSE 0 END) "
        f"            / COUNT(*), 1) AS unreviewed_pct "
        f"FROM commits c "
        f"LEFT JOIN (SELECT commit_id, COUNT(*) AS n FROM review_comments "
        f"           GROUP BY commit_id) rc ON rc.commit_id = c.commit_id "
        f"WHERE c.module_id = ? AND c.week IN ({ph})",
        (module_id, *wks),
    )[0]["unreviewed_pct"]

    # Major / minor comment counts in the window.
    sev = {r["severity"]: r["n"] for r in database.query(
        f"SELECT rc.severity, COUNT(*) AS n FROM review_comments rc "
        f"JOIN commits c ON c.commit_id = rc.commit_id "
        f"WHERE c.module_id = ? AND c.week IN ({ph}) GROUP BY rc.severity",
        (module_id, *wks),
    )}

    # Clang trend across the window: first window-week vs last window-week.
    trend = database.query(
        f"SELECT week, ROUND(AVG(clang_warnings), 1) AS avg_clang "
        f"FROM commits WHERE module_id = ? AND week IN ({ph}) "
        f"GROUP BY week ORDER BY week",
        (module_id, *wks),
    )
    if len(trend) >= 2 and trend[0]["avg_clang"]:
        delta = (trend[-1]["avg_clang"] - trend[0]["avg_clang"]) / trend[0]["avg_clang"]
        warning_trend = f"{delta * 100:+.0f}% over {len(trend)} weeks"
    else:
        warning_trend = "n/a"

    punctuality = database.query(
        "SELECT avg_days_late FROM punctuality WHERE module_id = ?", (module_id,))
    days_late = punctuality[0]["avg_days_late"] if punctuality else 0.0

    customer_issues = database.query(
        "SELECT COUNT(*) AS n FROM customer_issues WHERE module_id = ?",
        (module_id,))[0]["n"]

    return {
        "module_id": meta["id"],
        "name": meta["name"],
        "type": meta["type"],
        "team_lead": meta["team_lead"],
        "team_size": meta["team_size"],
        "project_id": meta["project_id"],
        "project": meta["project"],
        "unit_id": meta["unit_id"],
        "unit": meta["unit"],
        "window_weeks": len(wks),
        "commits": agg["commits"],
        "build_success_rate": agg["build_success_rate"] or 0.0,
        "avg_clang_warnings_per_commit": agg["avg_clang_warnings_per_commit"] or 0.0,
        "avg_asan_per_commit": agg["avg_asan_per_commit"] or 0.0,
        "total_asan_failures": agg["total_asan_failures"] or 0,
        "integration_fail_pct": agg["integration_fail_pct"] or 0.0,
        "avg_review_latency_hours": agg["avg_review_latency_hours"] or 0.0,
        "unreviewed_pct": unrev or 0.0,
        "major_comments": sev.get("major", 0),
        "minor_comments": sev.get("minor", 0),
        "warning_trend": warning_trend,
        "punctuality_days_late": days_late,
        "customer_issues": customer_issues,
    }


def get_module_trends(module_id: int) -> list[dict]:
    """Week-by-week history for trend charts (from weekly_summary)."""
    return database.query(
        "SELECT week, commits_merged, build_success_rate, total_clang_warnings, "
        "avg_clang_warnings_per_commit, total_asan_failures, integration_failures, "
        "integration_fail_pct, avg_review_latency "
        "FROM weekly_summary WHERE module_id = ? ORDER BY week",
        (module_id,),
    )


def get_commit_comments(module_id: int) -> list[dict]:
    """Per-commit comment counts by severity (major/minor), for a module."""
    return database.query(
        "SELECT c.commit_id, c.pr_id, c.week, e.name AS author, "
        "SUM(CASE WHEN rc.severity = 'major' THEN 1 ELSE 0 END) AS major, "
        "SUM(CASE WHEN rc.severity = 'minor' THEN 1 ELSE 0 END) AS minor, "
        "COUNT(rc.id) AS total "
        "FROM commits c "
        "LEFT JOIN review_comments rc ON rc.commit_id = c.commit_id "
        "LEFT JOIN engineers e ON e.id = c.author_id "
        "WHERE c.module_id = ? "
        "GROUP BY c.commit_id ORDER BY major DESC, total DESC",
        (module_id,),
    )


# -------------------------------------------------------------------------
# Rankings + org summary
# -------------------------------------------------------------------------
def get_all_module_rankings(weeks: int = 4) -> list[dict]:
    """All modules ranked by risk score (desc), each with health + risk."""
    mods = database.query("SELECT id FROM modules")
    rows = []
    for m in mods:
        health = get_module_health(m["id"], weeks)
        risk = risk_engine.compute_module_risk(health)
        rows.append({
            "module_id": health["module_id"],
            "module": health["name"],
            "project": health["project"],
            "unit": health["unit"],
            "team_size": health["team_size"],
            "risk_score": risk["score"],
            "risk_level": risk["level"],
            "build_success_rate": health["build_success_rate"],
            "avg_clang_warnings_per_commit": health["avg_clang_warnings_per_commit"],
            "punctuality_days_late": health["punctuality_days_late"],
            "customer_issues": health["customer_issues"],
            "warning_trend": health["warning_trend"],
            "breakdown": risk["breakdown"],
        })
    return sorted(rows, key=lambda r: r["risk_score"], reverse=True)


def get_org_summary(weeks: int = 4) -> dict:
    """High-level org health for KPI cards and the copilot context."""
    rankings = get_all_module_rankings(weeks)
    levels = {"GREEN": 0, "AMBER": 0, "RED": 0}
    for r in rankings:
        levels[r["risk_level"]] += 1

    avg_build = round(
        sum(r["build_success_rate"] for r in rankings) / len(rankings), 1
    ) if rankings else 0.0

    # Fastest-improving = most negative clang trend (e.g. "-40% over 4 weeks").
    def trend_pct(r):
        s = r["warning_trend"].split("%")[0]
        try:
            return float(s)
        except ValueError:
            return 0.0

    improving = sorted(rankings, key=trend_pct)
    total_issues = database.query(
        "SELECT COUNT(*) AS n FROM customer_issues")[0]["n"]

    return {
        "modules": len(rankings),
        "healthy": levels["GREEN"],
        "warning": levels["AMBER"],
        "critical": levels["RED"],
        "avg_build_success": avg_build,
        "highest_risk": rankings[0] if rankings else None,
        "fastest_improving": improving[0] if improving else None,
        "total_customer_issues": total_issues,
    }


# -------------------------------------------------------------------------
# Punctuality + customer impact + traceability
# -------------------------------------------------------------------------
def get_punctuality_by_module() -> list[dict]:
    """Avg days-late vs plan, per module (for the Unit Head view)."""
    return database.query(
        "SELECT m.name AS module, p.name AS project, m.team_size, "
        "pu.avg_days_late, pu.delivered "
        "FROM punctuality pu JOIN modules m ON m.id = pu.module_id "
        "JOIN projects p ON p.id = m.project_id "
        "ORDER BY pu.avg_days_late DESC"
    )


def get_customer_impact(project_id: int | None = None) -> list[dict]:
    """Errors reported per customer, optionally scoped to a project."""
    if project_id is None:
        return database.query(
            "SELECT cu.name AS customer, COUNT(*) AS issues, "
            "SUM(CASE WHEN ci.severity IN ('high','critical') THEN 1 ELSE 0 END) "
            "    AS high_critical "
            "FROM customer_issues ci JOIN customers cu ON cu.id = ci.customer_id "
            "GROUP BY cu.id ORDER BY issues DESC"
        )
    return database.query(
        "SELECT cu.name AS customer, COUNT(*) AS issues, "
        "SUM(CASE WHEN ci.severity IN ('high','critical') THEN 1 ELSE 0 END) "
        "    AS high_critical "
        "FROM customer_issues ci JOIN customers cu ON cu.id = ci.customer_id "
        "WHERE ci.project_id = ? GROUP BY cu.id ORDER BY issues DESC",
        (project_id,),
    )


def get_customer_trace(project_id: int | None = None) -> list[dict]:
    """Customer issue -> commit -> author/module lineage, optionally per project."""
    if project_id is None:
        return database.query(
            "SELECT * FROM customer_trace ORDER BY issue_severity DESC")
    return database.query(
        "SELECT ct.* FROM customer_trace ct "
        "JOIN customer_issues ci ON ci.id = ct.issue_id "
        "WHERE ci.project_id = ? ORDER BY ct.issue_severity DESC",
        (project_id,),
    )


def list_projects() -> list[dict]:
    return database.query(
        "SELECT p.id, p.name, p.manager, u.name AS unit "
        "FROM projects p JOIN units u ON u.id = p.unit_id ORDER BY u.name, p.name"
    )


def list_modules() -> list[dict]:
    return database.query(
        "SELECT m.id, m.name, m.team_lead, p.name AS project, u.name AS unit "
        "FROM modules m JOIN projects p ON p.id = m.project_id "
        "JOIN units u ON u.id = p.unit_id ORDER BY u.name, p.name, m.name"
    )
