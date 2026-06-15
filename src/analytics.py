"""Analytics engine: turn raw commits into role-ready, type-aware metrics.

Reads through database.query / database.query_df (each opens its own connection).
Quality signals are per module TYPE (from commit_metrics + metric_catalog); shared
process signals (build, integration, review, delivery) come from commits.
"""

import database
import risk_engine


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def _all_weeks() -> list[str]:
    return [r["week"] for r in
            database.query("SELECT DISTINCT week FROM commits ORDER BY week")]


def _last_weeks(n: int) -> list[str]:
    weeks = _all_weeks()
    return weeks[-n:] if n < len(weeks) else weeks


def _placeholders(items) -> str:
    return ",".join("?" for _ in items)


def get_metric_catalog(module_type: str | None = None) -> list[dict]:
    """Metric definitions, optionally for one module type."""
    if module_type:
        return database.query(
            "SELECT * FROM metric_catalog WHERE module_type = ? ORDER BY weight DESC",
            (module_type,))
    return database.query("SELECT * FROM metric_catalog ORDER BY module_type, weight DESC")


# -------------------------------------------------------------------------
# Module-level
# -------------------------------------------------------------------------
def get_module_health(module_id: int, weeks: int = 4) -> dict:
    """Aggregate metrics for a module over the last N weeks (risk-engine input)."""
    wks = _last_weeks(weeks)
    ph = _placeholders(wks)

    meta = database.query(
        "SELECT m.id, m.name, m.type, m.team_size, m.issue_status, "
        "e.name AS team_lead, p.id AS project_id, p.name AS project, "
        "p.customer AS customer, a.id AS account_id, a.name AS account, "
        "vu.id AS unit_id, vu.name AS unit "
        "FROM modules m JOIN projects p ON p.id = m.project_id "
        "JOIN accounts a ON a.id = p.account_id "
        "JOIN vertical_units vu ON vu.id = a.vertical_id "
        "LEFT JOIN engineers e ON e.id = m.team_lead_id WHERE m.id = ?",
        (module_id,),
    )[0]

    agg = database.query(
        f"SELECT COUNT(*) AS commits, "
        f"ROUND(100.0 * SUM(build_success) / COUNT(*), 1) AS build_success_rate, "
        f"ROUND(100.0 * SUM(integration_failed) / "
        f"      NULLIF(SUM(integration_total), 0), 1) AS integration_fail_pct, "
        f"ROUND(AVG(review_latency_hours), 1) AS avg_review_latency_hours "
        f"FROM commits WHERE module_id = ? AND week IN ({ph})",
        (module_id, *wks),
    )[0]

    # Type-specific quality metrics: avg per metric over the window.
    quality_metrics = {r["metric"]: r["v"] for r in database.query(
        f"SELECT cm.metric, ROUND(AVG(cm.value), 3) AS v FROM commit_metrics cm "
        f"JOIN commits c ON c.commit_id = cm.commit_id "
        f"WHERE c.module_id = ? AND c.week IN ({ph}) GROUP BY cm.metric",
        (module_id, *wks),
    )}

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

    sev = {r["severity"]: r["n"] for r in database.query(
        f"SELECT rc.severity, COUNT(*) AS n FROM review_comments rc "
        f"JOIN commits c ON c.commit_id = rc.commit_id "
        f"WHERE c.module_id = ? AND c.week IN ({ph}) GROUP BY rc.severity",
        (module_id, *wks),
    )}

    # Quality trend: weighted quality risk in the first vs last window-week.
    byweek = {}
    for r in database.query(
        f"SELECT week, metric, avg_value FROM metric_weekly "
        f"WHERE module_id = ? AND week IN ({ph}) ORDER BY week", (module_id, *wks)):
        byweek.setdefault(r["week"], {})[r["metric"]] = r["avg_value"]
    weeks_sorted = sorted(byweek)
    quality_trend = "n/a"
    if len(weeks_sorted) >= 2:
        q0, _ = risk_engine.quality_risk(meta["type"], byweek[weeks_sorted[0]])
        q1, _ = risk_engine.quality_risk(meta["type"], byweek[weeks_sorted[-1]])
        if q0 > 0:
            quality_trend = f"{(q1 - q0) / q0 * 100:+.0f}% over {len(weeks_sorted)} weeks"
        else:
            quality_trend = "flat" if q1 == 0 else f"rising (from ~0)"

    punctuality = database.query(
        "SELECT avg_days_late FROM punctuality WHERE module_id = ?", (module_id,))
    days_late = punctuality[0]["avg_days_late"] if punctuality else 0.0

    customer_issues = database.query(
        "SELECT COUNT(*) AS n FROM customer_issues WHERE module_id = ?",
        (module_id,))[0]["n"]

    return {
        "module_id": meta["id"], "name": meta["name"], "type": meta["type"],
        "team_lead": meta["team_lead"], "team_size": meta["team_size"],
        "project_id": meta["project_id"], "project": meta["project"],
        "customer": meta["customer"],
        "account_id": meta["account_id"], "account": meta["account"],
        "unit_id": meta["unit_id"], "unit": meta["unit"],
        "issue_status": meta["issue_status"],
        "window_weeks": len(wks), "commits": agg["commits"],
        "build_success_rate": agg["build_success_rate"] or 0.0,
        "integration_fail_pct": agg["integration_fail_pct"] or 0.0,
        "avg_review_latency_hours": agg["avg_review_latency_hours"] or 0.0,
        "unreviewed_pct": unrev or 0.0,
        "quality_metrics": quality_metrics,
        "major_comments": sev.get("major", 0), "minor_comments": sev.get("minor", 0),
        "quality_trend": quality_trend,
        "punctuality_days_late": days_late, "customer_issues": customer_issues,
    }


def get_module_trends(module_id: int) -> dict:
    """Week-by-week series for type-aware charts.

    Returns {weeks, build: [{week, build_success_rate}],
             metrics: [{week, metric, label, avg_value}], catalog: [...]}.
    """
    mtype = database.query(
        "SELECT type FROM modules WHERE id = ?", (module_id,))[0]["type"]
    build = database.query(
        "SELECT week, build_success_rate, integration_fail_pct "
        "FROM weekly_summary WHERE module_id = ? ORDER BY week", (module_id,))
    catalog = get_metric_catalog(mtype)
    labels = {c["metric"]: c["label"] for c in catalog}
    metrics = database.query(
        "SELECT week, metric, avg_value FROM metric_weekly "
        "WHERE module_id = ? ORDER BY week", (module_id,))
    for m in metrics:
        m["label"] = labels.get(m["metric"], m["metric"])
    return {"weeks": [b["week"] for b in build], "type": mtype,
            "build": build, "metrics": metrics, "catalog": catalog}


def get_commit_comments(module_id: int) -> list[dict]:
    """Per-commit comment counts by severity (major/minor), for a module."""
    return database.query(
        "SELECT c.commit_id, c.pr_id, c.week, e.name AS author, "
        "c.ai_agent_used, ROUND(c.ai_generated_percentage, 1) AS ai_generated_pct, "
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


def get_team_members(module_id: int) -> list[dict]:
    """Engineers on a module's team (lead flagged), with their activity."""
    return database.query(
        "SELECT e.id, e.name, "
        "CASE WHEN e.id = m.team_lead_id THEN 1 ELSE 0 END AS is_lead, "
        "(SELECT COUNT(*) FROM commits c WHERE c.author_id = e.id) AS commits_authored, "
        "(SELECT COUNT(*) FROM commits c WHERE c.reviewer_id = e.id) AS commits_reviewed "
        "FROM engineers e JOIN modules m ON m.id = e.module_id "
        "WHERE e.module_id = ? ORDER BY is_lead DESC, e.name",
        (module_id,),
    )


# -------------------------------------------------------------------------
# Rankings + org summary + benchmarking
# -------------------------------------------------------------------------
def get_all_module_rankings(weeks: int = 4) -> list[dict]:
    """All modules ranked by risk score (desc), each with health + risk."""
    rows = []
    for m in database.query("SELECT id FROM modules"):
        health = get_module_health(m["id"], weeks)
        risk = risk_engine.compute_module_risk(health)
        rows.append({
            "module_id": health["module_id"], "module": health["name"],
            "type": health["type"], "project": health["project"],
            "account_id": health["account_id"], "account": health["account"],
            "unit": health["unit"], "team_size": health["team_size"],
            "risk_score": risk["score"], "risk_level": risk["level"],
            "build_success_rate": health["build_success_rate"],
            "quality_risk": risk["breakdown"]["quality_risk"],
            "punctuality_days_late": health["punctuality_days_late"],
            "customer_issues": health["customer_issues"],
            "quality_trend": health["quality_trend"], "breakdown": risk["breakdown"],
        })
    return sorted(rows, key=lambda r: r["risk_score"], reverse=True)


def get_type_benchmark(module_id: int, weeks: int = 4) -> dict:
    """Rank a module among same-type peers (lower risk = better)."""
    rankings = get_all_module_rankings(weeks)
    me = next((r for r in rankings if r["module_id"] == module_id), None)
    if not me:
        return {}
    peers = [r for r in rankings if r["type"] == me["type"]]
    # Position from best (lowest risk). 1 = best of its type.
    ordered = sorted(peers, key=lambda r: r["risk_score"])
    rank = next(i for i, r in enumerate(ordered, 1) if r["module_id"] == module_id)
    n = len(peers)
    better_than = round(100 * (n - rank) / (n - 1)) if n > 1 else 100
    return {"type": me["type"], "peers": n, "rank": rank,
            "better_than_pct": better_than, "risk_score": me["risk_score"]}


def get_org_summary(weeks: int = 4) -> dict:
    """High-level org health for KPI cards and the copilot context."""
    rankings = get_all_module_rankings(weeks)
    levels = {"low": 0, "medium": 0, "high": 0}
    for r in rankings:
        levels[r["risk_level"]] += 1

    avg_build = round(
        sum(r["build_success_rate"] for r in rankings) / len(rankings), 1
    ) if rankings else 0.0

    def trend_pct(r):
        try:
            return float(r["quality_trend"].split("%")[0])
        except ValueError:
            return 0.0

    improving = sorted(rankings, key=trend_pct)
    total_issues = database.query(
        "SELECT COUNT(*) AS n FROM customer_issues")[0]["n"]

    return {
        "modules": len(rankings), "healthy": levels["low"],
        "warning": levels["medium"], "critical": levels["high"],
        "avg_build_success": avg_build,
        "highest_risk": rankings[0] if rankings else None,
        "fastest_improving": improving[0] if improving else None,
        "total_customer_issues": total_issues,
    }


# -------------------------------------------------------------------------
# Punctuality + customer impact + traceability + listings
# -------------------------------------------------------------------------
def get_punctuality_by_module() -> list[dict]:
    return database.query(
        "SELECT m.name AS module, m.type, p.name AS project, m.team_size, "
        "pu.avg_days_late, pu.delivered "
        "FROM punctuality pu JOIN modules m ON m.id = pu.module_id "
        "JOIN projects p ON p.id = m.project_id "
        "ORDER BY pu.avg_days_late DESC"
    )


def get_customer_impact(project_id: int | None = None) -> list[dict]:
    where = "WHERE ci.project_id = ?" if project_id is not None else ""
    params = (project_id,) if project_id is not None else ()
    return database.query(
        "SELECT ci.customer AS customer, COUNT(*) AS issues, "
        "SUM(CASE WHEN ci.severity IN ('high','critical') THEN 1 ELSE 0 END) "
        "    AS high_critical "
        "FROM customer_issues ci "
        f"{where} GROUP BY ci.customer ORDER BY issues DESC", params)


def get_customer_trace(project_id: int | None = None) -> list[dict]:
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
        "SELECT p.id, p.name, p.manager, p.customer, a.name AS account, "
        "vu.name AS unit "
        "FROM projects p JOIN accounts a ON a.id = p.account_id "
        "JOIN vertical_units vu ON vu.id = a.vertical_id "
        "ORDER BY vu.name, p.name"
    )


def list_modules() -> list[dict]:
    return database.query(
        "SELECT m.id, m.name, m.type, e.name AS team_lead, "
        "p.name AS project, a.name AS account, vu.name AS unit "
        "FROM modules m JOIN projects p ON p.id = m.project_id "
        "JOIN accounts a ON a.id = p.account_id "
        "JOIN vertical_units vu ON vu.id = a.vertical_id "
        "LEFT JOIN engineers e ON e.id = m.team_lead_id "
        "ORDER BY vu.name, p.name, m.name"
    )


# -------------------------------------------------------------------------
# Phase 4 rollups: MTTR, AI efficiency, Jira pipeline, telemetry
# -------------------------------------------------------------------------
def get_mttr_by_module() -> list[dict]:
    """Mean time to resolution (days) per module, from resolved jira tickets."""
    return database.query(
        "SELECT m.id AS module_id, m.name AS module, COUNT(*) AS resolved_tickets, "
        "ROUND(AVG(julianday(j.resolve_time) - julianday(j.raised_time)), 1) AS mttr_days "
        "FROM jira_logs j JOIN modules m ON m.id = j.module_id "
        "WHERE j.resolve_time IS NOT NULL "
        "GROUP BY m.id ORDER BY mttr_days DESC"
    )


def get_mttr_by_account() -> list[dict]:
    """Mean time to resolution (days) per account, from resolved jira tickets."""
    return database.query(
        "SELECT a.id AS account_id, a.name AS account, COUNT(*) AS resolved_tickets, "
        "ROUND(AVG(julianday(j.resolve_time) - julianday(j.raised_time)), 1) AS mttr_days "
        "FROM jira_logs j "
        "JOIN modules m ON m.id = j.module_id "
        "JOIN projects p ON p.id = m.project_id "
        "JOIN accounts a ON a.id = p.account_id "
        "WHERE j.resolve_time IS NOT NULL "
        "GROUP BY a.id ORDER BY mttr_days DESC"
    )


def get_account_risk_tiers(weeks: int = 4) -> dict:
    """Derive each account's risk tier from its modules' computed risk:
    high if any module is high, else medium if any medium, else low. Returns
    {account_id: {tier, critical_modules, n_critical, n_amber}}."""
    by_acct = {}
    for r in get_all_module_rankings(weeks):
        a = by_acct.setdefault(r["account_id"],
                               {"critical_modules": [], "n_critical": 0, "n_amber": 0})
        if r["risk_level"] == "high":
            a["critical_modules"].append(r["module"])
            a["n_critical"] += 1
        elif r["risk_level"] == "medium":
            a["n_amber"] += 1
    for a in by_acct.values():
        a["tier"] = ("high" if a["n_critical"] else
                     "medium" if a["n_amber"] else "low")
    return by_acct


def get_account_ai_efficiency() -> list[dict]:
    """Per-account AI tooling efficiency (ai_tool_efficiency) + computed MTTR +
    a data-derived account risk tier (from its modules' risk)."""
    rows = database.query(
        "SELECT a.id AS account_id, a.name AS account, vu.name AS unit, "
        "e.manual_triage_hours_saved, e.mttr_reduction_percentage, "
        "e.ai_resolved_tickets_count "
        "FROM ai_tool_efficiency e JOIN accounts a ON a.id = e.account_id "
        "JOIN vertical_units vu ON vu.id = a.vertical_id ORDER BY a.name"
    )
    mttr = {m["account_id"]: m["mttr_days"] for m in get_mttr_by_account()}
    tiers = get_account_risk_tiers()
    for r in rows:
        r["mttr_days"] = mttr.get(r["account_id"], 0.0)
        t = tiers.get(r["account_id"], {})
        r["risk_tier"] = t.get("tier", "low")
        r["critical_modules"] = t.get("critical_modules", [])
        r["n_critical"] = t.get("n_critical", 0)
    return rows


# Severity ordering for jira tickets (string severity -> rank).
_SEV_RANK = ("CASE j.severity WHEN 'critical' THEN 4 WHEN 'high' THEN 3 "
             "WHEN 'medium' THEN 2 ELSE 1 END")


def get_jira_pipeline(project_id: int | None = None) -> list[dict]:
    """Jira ticket pipeline (PM/TL view): one row per ticket, severity-ordered."""
    where = "WHERE m.project_id = ?" if project_id is not None else ""
    params = (project_id,) if project_id is not None else ()
    return database.query(
        "SELECT j.ticket_id, m.name AS module, p.name AS project, p.customer, "
        "j.severity, j.status, j.raised_time, j.resolve_time, j.assigned_to, "
        "j.task_name, j.lifecycle_status, j.automation_percentage, j.commit_id "
        "FROM jira_logs j "
        "JOIN modules m ON m.id = j.module_id "
        "JOIN projects p ON p.id = m.project_id "
        f"{where} ORDER BY {_SEV_RANK} DESC, j.raised_time DESC", params
    )


def get_project_delivery_kpis(project_id: int) -> dict:
    """Delivery snapshot for a project: ticket volume/backlog, MTTR, AI assistance."""
    return database.query(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN j.resolve_time IS NULL THEN 1 ELSE 0 END) AS open_count, "
        "SUM(CASE WHEN j.resolve_time IS NULL AND j.severity IN ('high','critical') "
        "         THEN 1 ELSE 0 END) AS high_crit_open, "
        "ROUND(AVG(CASE WHEN j.resolve_time IS NOT NULL "
        "          THEN julianday(j.resolve_time) - julianday(j.raised_time) END), 1) "
        "    AS mttr_days, "
        "ROUND(AVG(j.automation_percentage), 1) AS ai_assisted_pct "
        "FROM jira_logs j JOIN modules m ON m.id = j.module_id "
        "WHERE m.project_id = ?", (project_id,)
    )[0]


def get_telemetry(module_id: int) -> list[dict]:
    """Telemetry samples for a module (most recent first)."""
    return database.query(
        "SELECT metric_source, timestamp, issue_status, packet_drop_rate, "
        "latency_ms, cpu_utilization_percentage, associated_incidents "
        "FROM performance_data WHERE module_id = ? ORDER BY timestamp DESC",
        (module_id,)
    )


def get_customer_issue_status() -> list[dict]:
    """Per customer × severity: tickets raised vs still open (unresolved). A ticket
    is 'open' if it has no resolve_time. Customer = project.customer."""
    return database.query(
        "SELECT vu.name AS unit, p.customer AS customer, j.severity AS severity, "
        "COUNT(*) AS raised, "
        "SUM(CASE WHEN j.resolve_time IS NULL THEN 1 ELSE 0 END) AS open_count "
        "FROM jira_logs j "
        "JOIN modules m ON m.id = j.module_id "
        "JOIN projects p ON p.id = m.project_id "
        "JOIN accounts a ON a.id = p.account_id "
        "JOIN vertical_units vu ON vu.id = a.vertical_id "
        "GROUP BY vu.name, p.customer, j.severity ORDER BY p.customer, j.severity"
    )
