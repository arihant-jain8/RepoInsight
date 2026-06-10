"""Risk scoring: combine quality / delivery / collaboration into one 0-100 score.

All sub-scores are normalised to 0-100 before weighting so the dimensions are
comparable. Input is the dict returned by analytics.get_module_health().
"""


def compute_module_risk(m: dict) -> dict:
    """Return {'score', 'level', 'breakdown'} for a module's health metrics."""

    # --- Quality risk (0-100) --------------------------------------------
    warning_score = min(m["avg_clang_warnings_per_commit"] * 3, 100)
    asan_score = min(m["avg_asan_per_commit"] * 200, 100)  # asan is 0/1 -> rate
    integ_score = min(m["integration_fail_pct"] * 1.5, 100)
    quality_risk = 0.40 * warning_score + 0.35 * asan_score + 0.25 * integ_score

    # --- Delivery risk (0-100): the build failure rate -------------------
    delivery_risk = 100 - m["build_success_rate"]

    # --- Collaboration risk (0-100) --------------------------------------
    # Review latency normalised to a 48h ceiling, plus a penalty for commits
    # that merged with no review comments at all (thin review scrutiny).
    latency_norm = min(m["avg_review_latency_hours"] / 48 * 100, 100)
    review_pen = m["unreviewed_pct"]  # already 0-100
    collab_risk = min(latency_norm * 0.6 + review_pen * 0.4, 100)

    # --- Weighted final score --------------------------------------------
    risk_score = 0.50 * quality_risk + 0.30 * delivery_risk + 0.20 * collab_risk

    level = "GREEN" if risk_score < 30 else "AMBER" if risk_score < 60 else "RED"

    return {
        "score": round(risk_score, 1),
        "level": level,
        "breakdown": {
            "quality_risk": round(quality_risk, 1),
            "delivery_risk": round(delivery_risk, 1),
            "collab_risk": round(collab_risk, 1),
        },
    }
