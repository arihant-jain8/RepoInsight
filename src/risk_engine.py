"""Risk scoring — type-aware quality + shared delivery/collaboration.

Quality risk is computed from the module TYPE's metrics in metric_catalog: each
metric's aggregated value is normalised to 0-100 using the catalog's good/bad
anchors and direction, then weight-averaged. Delivery (build + integration) and
collaboration (review latency + unreviewed commits) are shared across all types.
"""

import database

_CATALOG = None  # process-level cache; the catalog is static


def _catalog() -> dict:
    global _CATALOG
    if _CATALOG is None:
        cat = {}
        for r in database.query("SELECT * FROM metric_catalog"):
            cat.setdefault(r["module_type"], []).append(r)
        _CATALOG = cat
    return _CATALOG


def _metric_risk(value, good, bad, higher_is_better) -> float:
    """Map a metric value to 0-100 risk (good -> 0, bad -> 100)."""
    if higher_is_better:
        span = good - bad           # good is the high (safe) end
        risk = (good - value) / span * 100 if span else 0.0
    else:
        span = bad - good           # bad is the high (risky) end
        risk = (value - good) / span * 100 if span else 0.0
    return max(0.0, min(100.0, risk))


def quality_risk(module_type: str, metrics: dict) -> tuple[float, dict]:
    """Weighted quality risk for a type, plus per-metric risk contributions."""
    num = den = 0.0
    contrib = {}
    for r in _catalog().get(module_type, []):
        v = metrics.get(r["metric"])
        if v is None:
            continue
        ri = _metric_risk(v, r["good"], r["bad"], r["higher_is_better"])
        contrib[r["metric"]] = round(ri, 1)
        num += r["weight"] * ri
        den += r["weight"]
    return (round(num / den, 1) if den else 0.0), contrib


def compute_module_risk(m: dict) -> dict:
    """Return {'score', 'level', 'breakdown', 'quality_contrib'} for a module."""
    qrisk, qcontrib = quality_risk(m["type"], m.get("quality_metrics", {}))

    # Delivery risk: build failures + integration failures (both shared).
    build_fail = 100 - m["build_success_rate"]
    integ = min(m.get("integration_fail_pct", 0.0) * 5, 100)
    delivery_risk = 0.6 * build_fail + 0.4 * integ

    # Collaboration risk: review latency (48h ceiling) + unreviewed commits.
    latency_norm = min(m["avg_review_latency_hours"] / 48 * 100, 100)
    collab_risk = min(latency_norm * 0.6 + m["unreviewed_pct"] * 0.4, 100)

    risk_score = 0.50 * qrisk + 0.30 * delivery_risk + 0.20 * collab_risk
    level = "low" if risk_score < 30 else "medium" if risk_score < 60 else "high"

    return {
        "score": round(risk_score, 1),
        "level": level,
        "breakdown": {
            "quality_risk": round(qrisk, 1),
            "delivery_risk": round(delivery_risk, 1),
            "collab_risk": round(collab_risk, 1),
        },
        "quality_contrib": qcontrib,  # per-metric risk, for drill-down
    }
