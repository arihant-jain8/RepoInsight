"""Data-over-code charting: the copilot emits a validated chart SPEC (never code),
which we render with Plotly from real analytics data.

The model only picks {chart_type, dataset, x, y, color, title} over a fixed set of
known datasets/fields — it never supplies the data points — so it cannot hallucinate
numbers and we never execute model-generated code (AURA.md's "data-over-code" engine).
"""

from aura.analytics import analytics

CHART_TYPES = ("bar", "line", "pie")

# name -> (loader, category fields [x/color], value fields [y], one-line description)
DATASETS = {
    "module_rankings": (
        analytics.get_all_module_rankings,
        ["module", "type", "project", "account", "unit", "risk_level"],
        ["risk_score", "build_success_rate", "quality_risk", "team_size",
         "punctuality_days_late", "customer_issues"],
        "all modules ranked by risk",
    ),
    "customer_tickets": (
        analytics.get_customer_issue_status,
        ["unit", "customer", "severity"],
        ["raised", "open_count"],
        "tickets per customer x severity (raised vs open)",
    ),
    "mttr_by_account": (
        analytics.get_mttr_by_account,
        ["account"], ["mttr_days", "resolved_tickets"],
        "mean time to resolution per account",
    ),
    "mttr_by_module": (
        analytics.get_mttr_by_module,
        ["module"], ["mttr_days", "resolved_tickets"],
        "mean time to resolution per module",
    ),
    "ai_efficiency": (
        analytics.get_account_ai_efficiency,
        ["account", "unit", "risk_tier"],
        ["mttr_reduction_percentage", "manual_triage_hours_saved",
         "ai_resolved_tickets_count", "mttr_days", "n_critical"],
        "AI tooling efficiency per account",
    ),
    "punctuality": (
        analytics.get_punctuality_by_module,
        ["module", "type", "project"],
        ["avg_days_late", "delivered", "team_size"],
        "delivery punctuality per module",
    ),
    "team_improvement": (
        analytics.get_team_improvement,
        ["module", "type", "project", "account", "driver"],
        ["risk_delta", "risk_early", "risk_recent",
         "quality_delta", "delivery_delta", "collab_delta"],
        "teams ranked by risk-score improvement over time (risk_delta>0 = improved)",
    ),
}


def catalog_text() -> str:
    """LLM-readable description of datasets + fields, for the make_chart tool schema."""
    lines = []
    for name, (_, cats, nums, desc) in DATASETS.items():
        lines.append(f"- {name}: {desc}. x/color fields: {', '.join(cats)}; "
                     f"y (value) fields: {', '.join(nums)}")
    return "\n".join(lines)


def validate_spec(spec: dict):
    """Return (ok, error). Checks chart type, dataset, that x/y/color are valid fields
    of that dataset (y must be a value field), and an optional row filter."""
    if not isinstance(spec, dict):
        return False, "spec must be an object"
    if spec.get("chart_type") not in CHART_TYPES:
        return False, f"chart_type must be one of {list(CHART_TYPES)}"
    ds = spec.get("dataset")
    if ds not in DATASETS:
        return False, f"dataset must be one of {list(DATASETS)}"
    _, cats, nums, _ = DATASETS[ds]
    allf = cats + nums
    x, y, color = spec.get("x"), spec.get("y"), spec.get("color")
    if x not in allf:
        return False, f"x must be a field of {ds}: {allf}"
    if y not in nums:
        return False, f"y must be a value field of {ds}: {nums}"
    if color not in (None, "") and color not in allf:
        return False, f"color must be a field of {ds} or omitted: {allf}"
    # Optional filter: keep only rows whose `filter_field` is in `filter_values`
    # (e.g. chart just two named modules). The model supplies category NAMES, never
    # data values, so this stays within data-over-code.
    ff, fv = spec.get("filter_field"), spec.get("filter_values")
    if ff not in (None, ""):
        if ff not in cats:
            return False, f"filter_field must be a category field of {ds}: {cats}"
        if not isinstance(fv, (list, tuple)) or not fv:
            return False, "filter_values must be a non-empty list when filter_field is set"
    return True, None


def build_figure(spec: dict):
    """Validate the spec + build a Plotly figure from the dataset's real data."""
    ok, err = validate_spec(spec)
    if not ok:
        raise ValueError(err)
    import pandas as pd
    import plotly.express as px

    df = pd.DataFrame(DATASETS[spec["dataset"]][0]())
    ff = spec.get("filter_field")
    if ff:
        vals = [str(v) for v in (spec.get("filter_values") or [])]
        df = df[df[ff].astype(str).isin(vals)]
        if df.empty:
            raise ValueError(f"no rows match {ff} in {spec.get('filter_values')}")
    x, y = spec["x"], spec["y"]
    color = spec.get("color") or None
    title = spec.get("title") or f"{y} by {x}"
    if spec["chart_type"] == "pie":
        return px.pie(df, names=x, values=y, title=title, hole=0.3)
    fn = px.bar if spec["chart_type"] == "bar" else px.line
    return fn(df, x=x, y=y, color=color, title=title)
