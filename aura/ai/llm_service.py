"""Pluggable LLM layer (OpenAI-compatible) with a deterministic fallback.

Builds a compact JSON context from the analytics engine (never raw rows), sends it
to the configured chat-completions endpoint, and returns the generated text. If no
model is reachable, every generator falls back to a data-driven markdown narrative
assembled from the same context, so the app always produces useful output.

Each public generator returns {"text": str, "source": "llm" | "fallback"}.
"""

import json
import os

import httpx

from aura.analytics import analytics
from aura import config
from aura.analytics import risk_engine

_CHAT_URL = f"{config.LLM_BASE_URL}/chat/completions"
_MODELS_URL = f"{config.LLM_BASE_URL}/models"
_HEADERS = {"Authorization": f"Bearer {config.LLM_API_KEY}"}


# -------------------------------------------------------------------------
# Transport
# -------------------------------------------------------------------------
def is_available() -> bool:
    """True if the configured LLM endpoint answers quickly."""
    try:
        r = httpx.get(_MODELS_URL, headers=_HEADERS, timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _call(messages: list[dict], max_tokens: int | None = None) -> str | None:
    """POST to the chat endpoint; return content, or None on any failure."""
    try:
        r = httpx.post(
            _CHAT_URL,
            json={
                "model": config.LLM_MODEL,
                "messages": messages,
                "max_tokens": max_tokens or config.LLM_MAX_TOKENS,
                "temperature": 0.3,
            },
            headers=_HEADERS,
            timeout=config.LLM_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _prompt(name: str) -> str:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", name), encoding="utf-8") as f:
        return f.read()


# -------------------------------------------------------------------------
# Context builders (compact, summarised — never raw rows)
# -------------------------------------------------------------------------
def _module_context(module_id: int) -> dict:
    h = analytics.get_module_health(module_id)
    risk = risk_engine.compute_module_risk(h)
    cat = {c["metric"]: c for c in analytics.get_metric_catalog(h["type"])}
    quality = {}
    for metric, val in h["quality_metrics"].items():
        c = cat.get(metric, {})
        quality[c.get("label", metric)] = {
            "value": val, "unit": c.get("unit", ""),
            "risk_0_100": risk["quality_contrib"].get(metric)}
    return {
        "module": h["name"], "type": h["type"], "project": h["project"],
        "unit": h["unit"], "team_lead": h["team_lead"],
        "team_size_people": h["team_size"],
        "window_weeks": h["window_weeks"], "commits_in_window": h["commits"],
        "risk_score": risk["score"], "risk_level": risk["level"],
        "risk_breakdown": risk["breakdown"],
        "quality_metrics": quality, "quality_trend": h["quality_trend"],
        "same_type_benchmark": analytics.get_type_benchmark(module_id),
        "build_success_rate_pct": h["build_success_rate"],
        "integration_failure_rate_pct": h["integration_fail_pct"],
        "avg_review_latency_hours": h["avg_review_latency_hours"],
        "major_review_comments_total_in_window": h["major_comments"],
        "minor_review_comments_total_in_window": h["minor_comments"],
        "pct_commits_merged_unreviewed": h["unreviewed_pct"],
        "avg_days_late_vs_plan": h["punctuality_days_late"],
        "customer_issues_total": h["customer_issues"],
    }


def _project_context(project_id: int) -> dict:
    proj = next((p for p in analytics.list_projects() if p["id"] == project_id), None)
    modules = [{
        "module": r["module"], "type": r["type"], "risk_level": r["risk_level"],
        "risk_score": r["risk_score"], "build_success_rate": r["build_success_rate"],
        "quality_risk": r["quality_risk"],
        "punctuality_days_late": r["punctuality_days_late"],
        "customer_issues": r["customer_issues"], "quality_trend": r["quality_trend"],
    } for r in analytics.get_all_module_rankings()
        if proj and r["project"] == proj["name"]]
    trace = [{
        "customer": t["customer"], "severity": t["issue_severity"],
        "module": t["module"], "commit_id": t["commit_id"],
        "author": t["author"], "error": t["error_info"],
    } for t in analytics.get_customer_trace(project_id)[:8]]
    return {
        "project": proj["name"] if proj else "?",
        "manager": proj["manager"] if proj else "?",
        "unit": proj["unit"] if proj else "?",
        "modules": modules,
        "customer_impact": analytics.get_customer_impact(project_id),
        "sample_traced_issues": trace,
    }


def _org_context() -> dict:
    o = analytics.get_org_summary()
    top = [{
        "module": r["module"], "type": r["type"], "project": r["project"],
        "risk_level": r["risk_level"], "risk_score": r["risk_score"],
        "build_success_rate": r["build_success_rate"],
        "punctuality_days_late": r["punctuality_days_late"],
        "customer_issues": r["customer_issues"], "quality_trend": r["quality_trend"],
    } for r in analytics.get_all_module_rankings()]
    return {
        "modules": o["modules"], "healthy": o["healthy"],
        "warning": o["warning"], "critical": o["critical"],
        "avg_build_success": o["avg_build_success"],
        "highest_risk_module": o["highest_risk"]["module"] if o["highest_risk"] else None,
        "fastest_improving_module":
            o["fastest_improving"]["module"] if o["fastest_improving"] else None,
        "total_customer_issues": o["total_customer_issues"],
        "module_rankings": top,
        "customer_impact": analytics.get_customer_impact(),
    }


# -------------------------------------------------------------------------
# Public generators
# -------------------------------------------------------------------------
def _report_messages(role: str, scope: str, context: dict) -> list[dict]:
    """The chat messages for a report — single source for generators + benchmark."""
    prompt = _prompt("report.txt").format(
        role=role, scope=scope, context=json.dumps(context, indent=2))
    return [{"role": "user", "content": prompt}]


def org_messages(role: str = "Unit Head") -> list[dict]:
    """Messages for the org-summary report (used by the perf benchmark)."""
    return _report_messages(role, "entire organisation", _org_context())


def module_messages(module_id: int, role: str = "Team Lead") -> list[dict]:
    """Messages for a module deep-dive report (used by the perf benchmark)."""
    ctx = _module_context(module_id)
    return _report_messages(role, f"module {ctx['module']} (project {ctx['project']})", ctx)


def _report(role: str, scope: str, context: dict, fallback) -> dict:
    out = _call(_report_messages(role, scope, context))
    if out:
        return {"text": out, "source": "llm"}
    return {"text": fallback(role, context), "source": "fallback"}


def generate_module_report(module_id: int, role: str = "Team Lead") -> dict:
    ctx = _module_context(module_id)
    scope = f"module {ctx['module']} (project {ctx['project']})"
    return _report(role, scope, ctx, _fallback_module)


def generate_project_report(project_id: int, role: str = "Project Manager") -> dict:
    ctx = _project_context(project_id)
    scope = f"project {ctx['project']}"
    return _report(role, scope, ctx, _fallback_project)


def generate_org_report(role: str = "Unit Head") -> dict:
    ctx = _org_context()
    return _report(role, "entire organisation", ctx, _fallback_org)


def chat(user_message: str, history: list[dict] | None = None) -> dict:
    ctx = _org_context()
    system = _prompt("copilot.txt").format(context=json.dumps(ctx, indent=2))
    messages = [{"role": "system", "content": system}]
    for m in (history or [])[-6:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message})
    out = _call(messages, max_tokens=500)
    if out:
        return {"text": out, "source": "llm"}
    return {"text": _fallback_chat(user_message, ctx), "source": "fallback"}


# -------------------------------------------------------------------------
# Deterministic fallbacks (used when no model is reachable)
# -------------------------------------------------------------------------
_OFFLINE = ("_LLM offline — this is an automatic, data-driven summary "
            "(no AI generation)._\n\n")


def _fallback_module(role: str, c: dict) -> str:
    bd = c["risk_breakdown"]
    dominant = max(bd, key=bd.get).replace("_", " ")
    qm = c["quality_metrics"]
    # The worst type-specific metric (highest risk_0_100).
    worst_metric = max(qm.items(), key=lambda kv: kv[1].get("risk_0_100") or 0,
                       default=(None, {}))
    qm_lines = "\n".join(
        f"  - {name}: {d['value']}{d['unit']} (risk {d.get('risk_0_100')})"
        for name, d in qm.items())
    return _OFFLINE + f"""## Executive Summary
{c['module']} ({c['type']} module, project {c['project']}) is **{c['risk_level']}** with a
risk score of {c['risk_score']}. Build success is {c['build_success_rate_pct']}%; quality
trend {c['quality_trend']}. The dominant risk dimension is **{dominant}**.

## Key Risks
- **Quality** ({bd['quality_risk']}) — {c['type']} metrics:
{qm_lines}
- **Delivery** ({bd['delivery_risk']}): build {c['build_success_rate_pct']}%,
  integration failures {c['integration_failure_rate_pct']}%.
- **Collaboration** ({bd['collab_risk']}): review latency {c['avg_review_latency_hours']}h,
  {c['pct_commits_merged_unreviewed']}% of commits merged unreviewed.
- **Punctuality / customers**: avg {c['avg_days_late_vs_plan']} days late;
  {c['customer_issues_total']} linked customer issues.

## Root Causes
The {dominant} dimension dominates. {('The weakest metric is **' + worst_metric[0] + '**.') if worst_metric[0] else ''}
With {c['major_review_comments_total_in_window']} major and
{c['minor_review_comments_total_in_window']} minor review comments over the last
{c['window_weeks']} weeks, the quality trend ({c['quality_trend']}) suggests
{'worsening' if '+' in c['quality_trend'] else 'stabilising'} quality.

## Recommended Actions
- Prioritise reducing {dominant}{(' — start with ' + worst_metric[0]) if worst_metric[0] else ''}.
- Tighten review on the {c['pct_commits_merged_unreviewed']}% of unreviewed commits.
- Address integration failures ({c['integration_failure_rate_pct']}%).
- Review delivery estimates given the {c['avg_days_late_vs_plan']}-day average slip.
"""


def _fallback_project(role: str, c: dict) -> str:
    mods = c["modules"]
    worst = max(mods, key=lambda m: m["risk_score"]) if mods else None
    impact = ", ".join(f"{i['customer']} ({i['issues']})" for i in c["customer_impact"])
    mod_lines = "\n".join(
        f"- **{m['module']}** ({m['type']}) — {m['risk_level']} ({m['risk_score']}), "
        f"build {m['build_success_rate']}%, {m['punctuality_days_late']}d late, "
        f"{m['customer_issues']} issues, quality {m['quality_trend']}" for m in mods)
    return _OFFLINE + f"""## Executive Summary
Project **{c['project']}** (manager {c['manager']}, unit {c['unit']}) has {len(mods)}
modules. {'Highest-risk module: **' + worst['module'] + '** (' + str(worst['risk_score']) + ').' if worst else ''}

## Key Risks
{mod_lines}

## Root Causes
Risk concentrates in the highest-scoring modules above. Customer issues by customer: {impact or 'none'}.

## Recommended Actions
- Focus first on {worst['module'] if worst else 'the highest-risk module'}.
- Work the customer issues traced to specific commits (see traceability table).
- Address modules slipping on delivery (highest days-late above).
"""


def _fallback_org(role: str, c: dict) -> str:
    impact = ", ".join(f"{i['customer']} ({i['issues']})" for i in c["customer_impact"])
    rank_lines = "\n".join(
        f"- **{r['module']}** ({r['project']}) — {r['risk_level']} {r['risk_score']}, "
        f"build {r['build_success_rate']}%, {r['customer_issues']} issues"
        for r in c["module_rankings"][:5])
    return _OFFLINE + f"""## Executive Summary
{c['modules']} modules: {c['healthy']} healthy, {c['warning']} warning, {c['critical']}
critical. Average build success {c['avg_build_success']}%. Highest risk:
**{c['highest_risk_module']}**; fastest improving: **{c['fastest_improving_module']}**.

## Key Risks
{rank_lines}

## Root Causes
Risk is concentrated in the top modules above; {c['total_customer_issues']} customer issues
across the org. Issues by customer: {impact or 'none'}.

## Recommended Actions
- Intervene on **{c['highest_risk_module']}** first.
- Replicate what is working in **{c['fastest_improving_module']}**.
- Track the {c['warning']} warning-level modules before they turn critical.
"""


def _fallback_chat(message: str, c: dict) -> str:
    m = message.lower()
    if any(w in m for w in ("risk", "focus", "worst", "attention")):
        return (_OFFLINE.strip() + f" Highest-risk module is "
                f"**{c['highest_risk_module']}**. Warning-level modules: {c['warning']}, "
                f"critical: {c['critical']}.")
    if "customer" in m or "issue" in m:
        impact = ", ".join(f"{i['customer']} ({i['issues']})" for i in c["customer_impact"])
        return (_OFFLINE.strip() + f" {c['total_customer_issues']} customer issues total. "
                f"By customer: {impact}.")
    if "improv" in m or "better" in m:
        return (_OFFLINE.strip() + f" Fastest-improving module is "
                f"**{c['fastest_improving_module']}**.")
    return (_OFFLINE.strip() + f" {c['modules']} modules — {c['healthy']} healthy, "
            f"{c['warning']} warning, {c['critical']} critical; avg build "
            f"{c['avg_build_success']}%. Highest risk: **{c['highest_risk_module']}**.")
