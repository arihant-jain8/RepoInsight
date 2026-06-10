"""Agentic copilot: a tool-using loop over the live database.

Unlike llm_service.chat (which paraphrases a fixed context blob), this gives the
model a toolbox — the analytics functions plus a guarded read-only run_sql — and
lets it decide what to fetch, query the live DB, and iterate before answering.
Returns {"text", "source", "trace"} where trace lists the tool calls it made.

Falls back to llm_service.chat when the model endpoint is unreachable.
"""

import json
import os
import re
import sqlite3

import httpx

import analytics
import config
import llm_service

MAX_STEPS = 6
_MAX_ROWS = 30  # cap rows fed back to the model per tool result


# -------------------------------------------------------------------------
# Name resolution
# -------------------------------------------------------------------------
def _resolve_module(name: str) -> dict | None:
    name = (name or "").strip().lower()
    for m in analytics.list_modules():
        if m["name"].lower() == name:
            return m
    return None


def _resolve_project(name: str) -> dict | None:
    name = (name or "").strip().lower()
    for p in analytics.list_projects():
        if p["name"].lower() == name:
            return p
    return None


# -------------------------------------------------------------------------
# Tool implementations (return JSON-serialisable data)
# -------------------------------------------------------------------------
def _t_list_modules(**_):
    return analytics.list_modules()


def _t_list_projects(**_):
    return analytics.list_projects()


def _t_org_summary(**_):
    return analytics.get_org_summary()


def _t_module_rankings(**_):
    return analytics.get_all_module_rankings()


def _t_module_health(module_name: str = "", **_):
    m = _resolve_module(module_name)
    if not m:
        return {"error": f"Unknown module '{module_name}'.",
                "available": [x["name"] for x in analytics.list_modules()]}
    return llm_service._module_context(m["id"])


def _t_module_trends(module_name: str = "", **_):
    m = _resolve_module(module_name)
    if not m:
        return {"error": f"Unknown module '{module_name}'.",
                "available": [x["name"] for x in analytics.list_modules()]}
    return analytics.get_module_trends(m["id"])


def _t_commit_comments(module_name: str = "", **_):
    m = _resolve_module(module_name)
    if not m:
        return {"error": f"Unknown module '{module_name}'.",
                "available": [x["name"] for x in analytics.list_modules()]}
    return analytics.get_commit_comments(m["id"])[:_MAX_ROWS]


def _t_customer_impact(project_name: str = "", **_):
    pid = None
    if project_name:
        p = _resolve_project(project_name)
        if not p:
            return {"error": f"Unknown project '{project_name}'.",
                    "available": [x["name"] for x in analytics.list_projects()]}
        pid = p["id"]
    return analytics.get_customer_impact(pid)


def _t_trace_customer_issues(project_name: str = "", module_name: str = "", **_):
    pid = None
    if project_name:
        p = _resolve_project(project_name)
        if not p:
            return {"error": f"Unknown project '{project_name}'.",
                    "available": [x["name"] for x in analytics.list_projects()]}
        pid = p["id"]
    rows = analytics.get_customer_trace(pid)
    if module_name:  # filter to a single module (customer_trace carries 'module')
        m = _resolve_module(module_name)
        if not m:
            return {"error": f"Unknown module '{module_name}'.",
                    "available": [x["name"] for x in analytics.list_modules()]}
        rows = [r for r in rows if (r.get("module") or "").lower() == module_name.lower()]
    out = rows[:_MAX_ROWS]
    sev = {}
    for r in rows:  # exact counts over ALL matching rows, computed here (not by the model)
        s = r.get("issue_severity")
        sev[s] = sev.get(s, 0) + 1
    return {"total_matching": len(rows),
            "severity_counts": sev,
            "high_or_critical": sev.get("high", 0) + sev.get("critical", 0),
            "rows_returned": len(out),
            "truncated": len(rows) > len(out),
            "rows": out}


_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|replace|"
    r"vacuum|reindex)\b", re.IGNORECASE)


def _t_run_sql(query: str = "", **_):
    """Run a single read-only SELECT against the DB (sandboxed)."""
    q = (query or "").strip().rstrip(";").strip()
    low = q.lower()
    if not (low.startswith("select") or low.startswith("with")):
        return {"error": "Only read-only SELECT / WITH queries are allowed."}
    if ";" in q:
        return {"error": "Only a single statement is allowed."}
    if _FORBIDDEN.search(q):
        return {"error": "Forbidden keyword; this tool is read-only SELECT only."}
    try:
        conn = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(q)
        rows = [dict(r) for r in cur.fetchmany(50)]
        cols = [d[0] for d in cur.description] if cur.description else []
        conn.close()
        return {"columns": cols, "row_count": len(rows), "rows": rows[:_MAX_ROWS]}
    except Exception as e:
        return {"error": str(e)}


def _t_team_members(module_name: str = "", **_):
    m = _resolve_module(module_name)
    if not m:
        return {"error": f"Unknown module '{module_name}'.",
                "available": [x["name"] for x in analytics.list_modules()]}
    return analytics.get_team_members(m["id"])


def _t_metric_catalog(module_type: str = "", **_):
    return analytics.get_metric_catalog(module_type or None)


_DISPATCH = {
    "list_modules": _t_list_modules,
    "list_projects": _t_list_projects,
    "get_org_summary": _t_org_summary,
    "get_module_rankings": _t_module_rankings,
    "get_module_health": _t_module_health,
    "get_module_trends": _t_module_trends,
    "get_commit_comments": _t_commit_comments,
    "get_customer_impact": _t_customer_impact,
    "trace_customer_issues": _t_trace_customer_issues,
    "get_team_members": _t_team_members,
    "get_metric_catalog": _t_metric_catalog,
    "run_sql": _t_run_sql,
}


def _tool(name, desc, props=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object",
                       "properties": props or {},
                       "required": required or []}}}


_MODULE_ARG = {"module_name": {"type": "string", "description": "Module name, e.g. 'Auth'"}}
_PROJECT_ARG = {"project_name": {"type": "string",
                                 "description": "Project name; omit for org-wide"}}

TOOLS = [
    _tool("list_modules", "List all modules with their project, unit and team lead."),
    _tool("list_projects", "List all projects with their unit and manager."),
    _tool("get_org_summary", "Org-wide health: healthy/warning/critical counts, avg build "
          "success, highest-risk and fastest-improving module, total customer issues."),
    _tool("get_module_rankings", "All modules ranked by risk score, with risk level, build "
          "rate, clang trend, days late and customer issue counts."),
    _tool("get_module_health", "Detailed health + risk breakdown for one module.",
          _MODULE_ARG, ["module_name"]),
    _tool("get_module_trends", "Week-by-week (12 weeks) metrics for one module.",
          _MODULE_ARG, ["module_name"]),
    _tool("get_commit_comments", "Per-commit review-comment counts (major/minor) for a module.",
          _MODULE_ARG, ["module_name"]),
    _tool("get_customer_impact", "Customer-reported issue counts per customer, optionally "
          "scoped to a project.", _PROJECT_ARG),
    _tool("trace_customer_issues", "Customer issue -> commit -> author/module lineage "
          "(which commit caused which customer issue, with each issue's severity). "
          "Optionally scope to a project and/or a single module.",
          {**_PROJECT_ARG, **_MODULE_ARG}),
    _tool("get_team_members", "List the engineers on a module's team (lead flagged), with "
          "how many commits each authored/reviewed.", _MODULE_ARG, ["module_name"]),
    _tool("get_metric_catalog", "The quality metrics that define a module type "
          "(label, unit, direction, good/bad thresholds). Pass module_type to scope.",
          {"module_type": {"type": "string",
                           "description": "network | backend | frontend | ai"}}),
    _tool("run_sql", "Run a single READ-ONLY SQL SELECT against the database for anything the "
          "other tools don't cover. Returns columns + rows.",
          {"query": {"type": "string", "description": "A single SELECT statement."}},
          ["query"]),
]


# -------------------------------------------------------------------------
# Transport + loop
# -------------------------------------------------------------------------
def _chat_raw(messages: list[dict], tools=None) -> dict | None:
    payload = {"model": config.LLM_MODEL, "messages": messages,
               "temperature": 0.2, "stream": False}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    try:
        r = httpx.post(f"{config.LLM_BASE_URL}/chat/completions", json=payload,
                       headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
                       timeout=config.LLM_TIMEOUT)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]
    except Exception:
        return None


def _dispatch(name: str, args: dict):
    fn = _DISPATCH.get(name)
    if not fn:
        return {"error": f"Unknown tool '{name}'."}
    try:
        return fn(**(args or {}))
    except Exception as e:
        return {"error": str(e)}


def _preview(result) -> str:
    if isinstance(result, dict):
        if "error" in result:
            return f"error: {result['error'][:120]}"
        if "rows" in result:
            return f"{result.get('row_count', len(result['rows']))} row(s)"
        keys = ", ".join(list(result.keys())[:6])
        return f"{{{keys}}}"
    if isinstance(result, list):
        return f"{len(result)} item(s)"
    return str(result)[:120]


def _prompt() -> str:
    with open(os.path.join(config.SRC_DIR, "prompts", "agent.txt"), encoding="utf-8") as f:
        return f.read()


# --- SQL guardrail: never surface raw SQL in the app ---------------------
_SQL_FENCE = re.compile(r"```[\s\S]*?```")
_SQL_LINE = re.compile(r"(?im)^\s*(?:SELECT|WITH)\b.*$")


def _scrub_sql(text: str) -> str:
    """Strip fenced code blocks and standalone SQL lines from a user-facing answer."""
    text = _SQL_FENCE.sub("", text)
    text = _SQL_LINE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _trace_entry(name: str, args: dict, result) -> dict:
    """Trace row for the UI. run_sql is redacted — never expose the query string."""
    if name == "run_sql":
        rc = result.get("row_count") if isinstance(result, dict) else None
        return {"tool": "run_sql", "args": {},
                "preview": f"queried the database ({rc if rc is not None else 0} rows)"}
    return {"tool": name, "args": args, "preview": _preview(result)}


def agent_chat(message: str, history: list[dict] | None = None) -> dict:
    """Tool-using chat. Returns {'text', 'source', 'trace'}."""
    if not llm_service.is_available():
        res = llm_service.chat(message, history)
        res["trace"] = []
        return res

    messages = [{"role": "system", "content": _prompt()}]
    for m in (history or [])[-6:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})

    trace = []
    for _ in range(MAX_STEPS):
        msg = _chat_raw(messages, tools=TOOLS)
        if msg is None:  # transport error mid-loop -> fallback
            res = llm_service.chat(message, history)
            res["trace"] = trace
            return res

        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            return {"text": _scrub_sql(msg.get("content") or "") or "(no answer)",
                    "source": "llm", "trace": trace}

        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": tool_calls})
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except Exception:
                args = {}
            result = _dispatch(name, args)
            trace.append(_trace_entry(name, args, result))
            messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                             "content": json.dumps(result, default=str)[:6000]})

    # Hit the step cap — force a final text answer with the data gathered so far.
    final = _chat_raw(messages + [{"role": "user",
                                   "content": "Answer now using the data above; do not call tools."}])
    text = _scrub_sql(final.get("content") if final else "") or \
        "I gathered data but couldn't finalise an answer — try narrowing the question."
    return {"text": text, "source": "llm", "trace": trace}
