# Metric catalog (type-aware quality metrics)

Quality is scored on **type-specific** metrics. Each metric has a "good" threshold (maps to
~0 risk) and a "bad" threshold (maps to ~100 risk); values in between scale linearly. The
per-metric risks are weight-averaged within the type to give the module's **quality_risk**.
"Dir" = better direction: **up** means higher is better, **down** means lower is better.

To judge a value: compare it to that metric's good/bad thresholds. E.g. backend test coverage
of 55% sits near the "bad" end (good=85, bad=50) → high quality risk; 88% is past "good".

## network  (RAN/baseband/MEC modules)

| Metric | Label | Unit | Dir | Weight | Good | Bad |
|---|---|---|---|---|---|---|
| asan_failures | ASAN failures / commit | count | down | 0.30 | 0 | 3 |
| clang_warnings | Clang warnings / commit | count | down | 0.20 | 10 | 120 |
| packet_drop_rate_pct | Packet drop rate | % | down | 0.30 | 0.05 | 2.0 |
| p99_latency_ms | p99 latency | ms | down | 0.20 | 20 | 150 |

## backend  (payments/ledger/billing/trade modules)

| Metric | Label | Unit | Dir | Weight | Good | Bad |
|---|---|---|---|---|---|---|
| test_coverage_pct | Test coverage | % | up | 0.25 | 85 | 50 |
| transaction_error_rate_pct | Transaction error rate | % | down | 0.30 | 0.1 | 3.0 |
| sast_findings | SAST findings | count | down | 0.25 | 0 | 10 |
| lint_errors | Lint errors / commit | count | down | 0.20 | 2 | 40 |

## ai  (fraud / KYC ML modules)

| Metric | Label | Unit | Dir | Weight | Good | Bad |
|---|---|---|---|---|---|---|
| eval_accuracy_pct | Eval accuracy | % | up | 0.30 | 92 | 70 |
| false_positive_rate_pct | False positive rate | % | down | 0.25 | 1 | 15 |
| model_drift | Model drift | ratio | down | 0.25 | 0.02 | 0.3 |
| data_validation_failures | Data validation failures | count | down | 0.20 | 0 | 10 |

## frontend  (reserved — no frontend modules in the current data)

| Metric | Label | Unit | Dir | Weight | Good | Bad |
|---|---|---|---|---|---|---|
| eslint_errors | ESLint errors / commit | count | down | 0.25 | 2 | 50 |
| accessibility_score | Accessibility score | score | up | 0.25 | 95 | 70 |
| lighthouse_perf | Lighthouse performance | score | up | 0.25 | 90 | 50 |
| bundle_size_kb | Bundle size | KB | down | 0.25 | 200 | 1200 |
