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

from aura.analytics import analytics
from aura import config
from aura.ai import charts
from aura.ai import llm_service

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


def _t_describe_schema(**_):
    """Real tables, columns, views and FK relationships (read-only introspection)."""
    conn = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    objs = conn.execute(
        "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') "
        "AND name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall()
    tables = [o["name"] for o in objs if o["type"] == "table"]
    views = [o["name"] for o in objs if o["type"] == "view"]
    columns, rels = {}, []
    for t in tables:
        columns[t] = [r["name"] for r in
                      conn.execute(f"PRAGMA table_info({t})").fetchall()]
        for fk in conn.execute(f"PRAGMA foreign_key_list({t})").fetchall():
            rels.append(f"{t}.{fk['from']} -> {fk['table']}.{fk['to']}")
    conn.close()
    return {"tables": tables, "views": views, "columns": columns,
            "relationships": rels}


def _t_mttr(**_):
    return {"by_module": analytics.get_mttr_by_module(),
            "by_account": analytics.get_mttr_by_account()}


def _t_ai_efficiency(**_):
    return analytics.get_account_ai_efficiency()


def _t_team_improvement(**_):
    return analytics.get_team_improvement()


def _t_jira_pipeline(project_name: str = "", **_):
    pid = None
    if project_name:
        p = _resolve_project(project_name)
        if not p:
            return {"error": f"Unknown project '{project_name}'.",
                    "available": [x["name"] for x in analytics.list_projects()]}
        pid = p["id"]
    return analytics.get_jira_pipeline(pid)[:_MAX_ROWS]


def _t_telemetry(module_name: str = "", **_):
    m = _resolve_module(module_name)
    if not m:
        return {"error": f"Unknown module '{module_name}'.",
                "available": [x["name"] for x in analytics.list_modules()]}
    return analytics.get_telemetry(m["id"])


def _t_make_chart(chart_type: str = "", dataset: str = "", x: str = "",
                  y: str = "", color: str = "", title: str = "",
                  filter_field: str = "", filter_values=None, **_):
    """Validate a chart spec (data-over-code). On success returns the spec for the UI
    to render; on a bad field/dataset returns an error so the model self-corrects."""
    spec = {"chart_type": chart_type, "dataset": dataset, "x": x, "y": y, "title": title}
    if color:
        spec["color"] = color
    if filter_field:
        spec["filter_field"] = filter_field
        spec["filter_values"] = list(filter_values) if filter_values else []
    ok, err = charts.validate_spec(spec)
    if not ok:
        return {"error": err}
    return {"status": "chart spec accepted — it will be rendered to the user", "spec": spec}


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
    "get_mttr": _t_mttr,
    "get_ai_efficiency": _t_ai_efficiency,
    "get_team_improvement": _t_team_improvement,
    "get_jira_pipeline": _t_jira_pipeline,
    "get_telemetry": _t_telemetry,
    "make_chart": _t_make_chart,
    "describe_schema": _t_describe_schema,
    "run_sql": _t_run_sql,
}


def _tool(name, desc, props=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object",
                       "properties": props or {},
                       "required": required or []}}}


_MODULE_ARG = {"module_name": {"type": "string",
                               "description": "Module name, e.g. 'RAN Packet Parser'"}}
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
    _tool("get_mttr", "Mean time to resolution (days) per module and per account, "
          "from resolved jira tickets."),
    _tool("get_ai_efficiency", "Per-account AI tooling efficiency: manual hours saved, "
          "MTTR-reduction %, AI-resolved ticket count, plus computed MTTR (days)."),
    _tool("get_team_improvement", "Which teams improved (or regressed) the most over time: "
          "each team's (module's) composite risk score in an early window vs a recent window, "
          "the risk_delta (positive = improved/risk fell), and the driver component (code "
          "quality / build & integration / review collaboration) behind it. Ranked "
          "most-improved first. Use for 'who improved the most / by how much / based on what'."),
    _tool("get_jira_pipeline", "Jira ticket pipeline (ticket id, severity, status, lifecycle "
          "stage, assignee, AI automation %, causing commit). Optionally scope to a project.",
          _PROJECT_ARG),
    _tool("get_telemetry", "Real-time telemetry samples for a module (packet drop rate, "
          "latency, CPU utilisation, associated incidents).", _MODULE_ARG, ["module_name"]),
    _tool("make_chart",
          "Render a chart for the user when they ask for a graph/chart/plot/visualisation. "
          "Pick chart_type (bar/line/pie), a dataset, and x + y fields (optionally color). "
          "You do NOT provide data values — the app fills them from the dataset. To chart only "
          "SPECIFIC items (e.g. compare two named modules), set filter_field to a category field "
          "and filter_values to the exact names to keep — otherwise the chart shows ALL rows. "
          "Datasets:\n" + charts.catalog_text(),
          {"chart_type": {"type": "string", "description": "bar | line | pie"},
           "dataset": {"type": "string", "description": "one of the dataset names listed above"},
           "x": {"type": "string", "description": "category field for the x-axis (or pie names)"},
           "y": {"type": "string", "description": "value field for the y-axis (or pie values)"},
           "color": {"type": "string", "description": "optional field to group/colour by"},
           "title": {"type": "string", "description": "a short chart title"},
           "filter_field": {"type": "string", "description":
                            "optional category field to limit the chart to specific rows, e.g. 'module'"},
           "filter_values": {"type": "array", "items": {"type": "string"}, "description":
                             "optional: the exact values of filter_field to KEEP, e.g. the two module names"}},
          ["chart_type", "dataset", "x", "y"]),
    _tool("describe_schema", "The real database structure: tables, columns, views and "
          "foreign-key relationships. Use for any question about what tables/columns "
          "exist or how the database is structured."),
    _tool("run_sql", "Run a single READ-ONLY SQL SELECT against the database for anything the "
          "other tools don't cover. Returns columns + rows.",
          {"query": {"type": "string", "description": "A single SELECT statement."}},
          ["query"]),
]


# -------------------------------------------------------------------------
# Transport + loop
# -------------------------------------------------------------------------
def _chat_raw(messages: list[dict], tools=None):
    """Returns (message, usage). On any failure returns (None, {})."""
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
        data = r.json()
        return data["choices"][0]["message"], (data.get("usage") or {})
    except Exception:
        return None, {}


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
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "agent.txt"), encoding="utf-8") as f:
        return f.read()


# --- SQL guardrail: never surface raw SQL in the app ---------------------
_SQL_FENCE = re.compile(r"```[\s\S]*?```")
_SQL_LINE = re.compile(r"(?im)^\s*(?:SELECT|WITH)\b.*$")


def _scrub_sql(text: str) -> str:
    """Strip fenced code blocks and standalone SQL lines from a user-facing answer.

    Also drops any markdown image the model invents (e.g. ![chart](chart_image_url)) —
    real charts are rendered separately from the chart spec, so an inline image is
    always a broken placeholder.
    """
    text = _SQL_FENCE.sub("", text)
    text = _SQL_LINE.sub("", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _trace_entry(name: str, args: dict, result) -> dict:
    """Trace row for the UI. run_sql is redacted — never expose the query string."""
    if name == "run_sql":
        rc = result.get("row_count") if isinstance(result, dict) else None
        return {"tool": "run_sql", "args": {},
                "preview": f"queried the database ({rc if rc is not None else 0} rows)"}
    return {"tool": name, "args": args, "preview": _preview(result)}


def agent_chat(message: str, history: list[dict] | None = None) -> dict:
    """Tool-using chat. Returns {'text', 'source', 'trace', 'tokens', 'prompt_tokens',
    'completion_tokens', 'calls', 'chart'} — token counts summed across the tool loop."""
    if not llm_service.is_available():
        res = llm_service.chat(message, history)
        res.update({"trace": [], "tokens": 0, "prompt_tokens": 0,
                    "completion_tokens": 0, "calls": 0, "chart": None})
        return res

    messages = [{"role": "system", "content": _prompt()}]
    for m in (history or [])[-6:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": message})

    trace = []
    nudged = False
    total_tokens = prompt_tokens = completion_tokens = calls = 0
    chart = None
    for _ in range(MAX_STEPS):
        msg, usage = _chat_raw(messages, tools=TOOLS)
        calls += 1
        total_tokens += usage.get("total_tokens", 0)
        prompt_tokens += usage.get("prompt_tokens", 0)
        completion_tokens += usage.get("completion_tokens", 0)
        if msg is None:  # transport error mid-loop -> fallback
            res = llm_service.chat(message, history)
            res.update({"trace": trace, "tokens": total_tokens,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "calls": calls, "chart": chart})
            return res

        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            # Guard against answering DATA questions from memory (the model would
            # invent modules/numbers). Nudge once: if the answer cites specific data
            # values it must verify them via a tool; pure schema answers may stand.
            if not trace and not nudged:
                nudged = True
                messages.append({"role": "assistant", "content": msg.get("content") or ""})
                messages.append({"role": "user", "content":
                                 "You answered without using a tool. If your answer names "
                                 "specific modules, projects, people, metrics, counts or "
                                 "trends, those are DATA — call the right tool to verify "
                                 "them, then answer. If your answer is only about the "
                                 "database structure/schema, you may keep it as-is."})
                continue
            return {"text": _scrub_sql(msg.get("content") or "") or "(no answer)",
                    "source": "llm", "trace": trace, "tokens": total_tokens,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "calls": calls, "chart": chart}

        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": tool_calls})
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except Exception:
                args = {}
            result = _dispatch(name, args)
            if name == "make_chart" and isinstance(result, dict) and result.get("spec"):
                chart = result["spec"]
            trace.append(_trace_entry(name, args, result))
            messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                             "content": json.dumps(result, default=str)[:6000]})

    # Hit the step cap — force a final text answer with the data gathered so far.
    final, usage = _chat_raw(messages + [{"role": "user",
                                          "content": "Answer now using the data above; do not call tools."}])
    calls += 1
    total_tokens += usage.get("total_tokens", 0)
    prompt_tokens += usage.get("prompt_tokens", 0)
    completion_tokens += usage.get("completion_tokens", 0)
    text = _scrub_sql(final.get("content") if final else "") or \
        "I gathered data but couldn't finalise an answer — try narrowing the question."
    return {"text": text, "source": "llm", "trace": trace, "tokens": total_tokens,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "calls": calls, "chart": chart}
