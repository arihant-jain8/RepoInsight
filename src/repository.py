"""Write seam: ingest a held-back project bundle into the central DB.

Used by the showcase API gateway (API_GATEWAY_DECISION). Restores a whole project
subgraph — project, modules, engineers, commits (+ commit_metrics, review_comments),
jira_logs, performance_data — using the bundle's original ids, resolving the parent
account by name. Idempotent: re-ingesting the same project replaces it.

This is the single insert path the gateway depends on, so a future Mongo backend
(Phase 7) only has to reimplement this module.
"""

import database


def _remove_project(conn, proj_key: str) -> None:
    """FK-safe delete of an existing project subgraph (for idempotent re-ingest)."""
    proj = conn.execute(
        "SELECT id FROM projects WHERE proj_key = ?", (proj_key,)).fetchone()
    if proj is None:
        return
    pid = proj["id"]
    mids = [r["id"] for r in
            conn.execute("SELECT id FROM modules WHERE project_id = ?", (pid,))]
    cids = [r["commit_id"] for r in
            conn.execute("SELECT commit_id FROM commits WHERE project_id = ?", (pid,))]
    mph, cph = ",".join("?" * len(mids)), ",".join("?" * len(cids))
    cur = conn.cursor()
    cur.execute("UPDATE modules SET team_lead_id = NULL WHERE project_id = ?", (pid,))
    if cids:
        cur.execute(f"DELETE FROM review_comments WHERE commit_id IN ({cph})", cids)
        cur.execute(f"DELETE FROM commit_metrics WHERE commit_id IN ({cph})", cids)
    if mids:
        cur.execute(f"DELETE FROM jira_logs WHERE module_id IN ({mph})", mids)
        cur.execute(f"DELETE FROM performance_data WHERE module_id IN ({mph})", mids)
    cur.execute("DELETE FROM commits WHERE project_id = ?", (pid,))
    if mids:
        cur.execute(f"DELETE FROM engineers WHERE module_id IN ({mph})", mids)
    cur.execute("DELETE FROM modules WHERE project_id = ?", (pid,))
    cur.execute("DELETE FROM projects WHERE id = ?", (pid,))


def remove_project(proj_key: str) -> None:
    """Demo reset: remove a project subgraph from central, putting it back to the
    held-back state. The source bundle on disk is untouched, so the edge agent can
    re-ingest it. (Local admin action — does not go through the gateway.)"""
    conn = database.connect()
    try:
        _remove_project(conn, proj_key)
        conn.commit()
    finally:
        conn.close()


def _insert(cur, table: str, rows: list) -> None:
    """Insert dict rows into table with explicit columns (and ids)."""
    for row in rows:
        cols = list(row.keys())
        ph = ",".join("?" * len(cols))
        cur.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph})",
                    [row[c] for c in cols])


def ingest_project_bundle(bundle: dict) -> dict:
    """Restore a project bundle (from generate_data.export_and_remove_project) into
    the central DB. Returns a summary. Idempotent."""
    project = dict(bundle["project"])
    proj_key = project["proj_key"]
    conn = database.connect()
    try:
        acct = conn.execute(
            "SELECT id FROM accounts WHERE name = ?", (bundle["account_name"],)).fetchone()
        if acct is None:
            raise ValueError(f"Unknown account '{bundle['account_name']}'")
        project["account_id"] = acct["id"]   # re-resolve, robust to id drift

        _remove_project(conn, proj_key)       # idempotent re-ingest

        cur = conn.cursor()
        _insert(cur, "projects", [project])

        # Modules first with NULL team_lead (engineers not inserted yet), then fix up.
        mods = [dict(m) for m in bundle["modules"]]
        leads = {m["id"]: m["team_lead_id"] for m in mods}
        for m in mods:
            m["team_lead_id"] = None
        _insert(cur, "modules", mods)
        _insert(cur, "engineers", bundle["engineers"])
        for mid, lead in leads.items():
            if lead is not None:
                cur.execute("UPDATE modules SET team_lead_id = ? WHERE id = ?", (lead, mid))

        _insert(cur, "commits", bundle["commits"])
        _insert(cur, "commit_metrics", bundle["commit_metrics"])
        _insert(cur, "review_comments", bundle["review_comments"])
        _insert(cur, "jira_logs", bundle["jira_logs"])
        _insert(cur, "performance_data", bundle["performance_data"])
        conn.commit()
        return {
            "project": project["name"], "proj_key": proj_key,
            "modules": len(bundle["modules"]), "commits": len(bundle["commits"]),
            "jira_logs": len(bundle["jira_logs"]),
            "performance_data": len(bundle["performance_data"]),
        }
    finally:
        conn.close()
