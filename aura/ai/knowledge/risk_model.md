# Risk model

The composite **risk_score** (0–100) is how at-risk a module/team is overall. It is a
fixed-weight blend of three components:

```
risk_score = 0.50 * quality_risk + 0.30 * delivery_risk + 0.20 * collaboration_risk
```

The weights **0.50 / 0.30 / 0.20 are FIXED** — they do NOT vary by module type or by
anything else. Bands:

- **low**  — risk_score < 30
- **medium** — 30 to 59
- **high** — 60 or more

## The three components are distinct

- **quality_risk** — code quality only. Computed from the module TYPE's own metrics in the
  metric catalog (see metric_catalog), each normalized to a 0–100 risk against its good/bad
  thresholds, then weight-averaged. It does NOT include build, integration, or review signals.
- **delivery_risk** — `0.6 * (100 - build_success_rate) + 0.4 * min(integration_fail_pct * 5, 100)`.
  Build failures and integration failures.
- **collaboration_risk** — `0.6 * min(review_latency_hours / 48 * 100, 100) + 0.4 * unreviewed_pct`.
  Review latency (48h ceiling) and the share of commits merged with zero review comments.

## Not part of risk_score

Days-late / punctuality, customer issues, and MTTR are reported **separately** and are NOT
folded into risk_score. A module can have high quality_risk but only a moderate risk_score if
its delivery and collaboration are strong — and vice versa.
