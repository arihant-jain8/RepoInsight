-- Engineering Intelligence Copilot — central database schema
-- One SQLite file holds the internal DB (engineering activity) and the customer
-- DB (support signals), joined by commit_id so any customer issue traces back to
-- the commit that caused it.
--
-- Quality signals are TYPE-AWARE: each module type (network/backend/frontend/ai)
-- has its own metrics, defined in metric_catalog and stored per commit in
-- commit_metrics. Shared process signals (build, integration, review, delivery)
-- stay on the commits table.

-- Drop in any order (SQLite ignores FKs on DROP); children-first for clarity.
DROP VIEW  IF EXISTS metric_weekly;
DROP VIEW  IF EXISTS customer_trace;
DROP VIEW  IF EXISTS punctuality;
DROP VIEW  IF EXISTS weekly_summary;
DROP TABLE IF EXISTS customer_issues;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS commit_metrics;
DROP TABLE IF EXISTS review_comments;
DROP TABLE IF EXISTS commits;
DROP TABLE IF EXISTS engineers;
DROP TABLE IF EXISTS modules;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS units;
DROP TABLE IF EXISTS metric_catalog;

-- ========================================================================
-- Internal DB — hierarchy: unit -> project -> module -> commit
-- ========================================================================

CREATE TABLE units (
    id      INTEGER PRIMARY KEY,
    name    TEXT,
    head    TEXT            -- Unit Head (persona)
);

CREATE TABLE projects (
    id      INTEGER PRIMARY KEY,
    unit_id INTEGER REFERENCES units(id),
    name    TEXT,
    manager TEXT            -- Project Manager (persona)
);

CREATE TABLE modules (
    id           INTEGER PRIMARY KEY,
    project_id   INTEGER REFERENCES projects(id),
    name         TEXT,       -- e.g. 'auth-service'
    type         TEXT,       -- network | backend | frontend | ai
    repo_url     TEXT,       -- multi-repo: each module = its own git repo
    team_lead_id INTEGER REFERENCES engineers(id),  -- FK (was free text)
    team_size    INTEGER     -- people on the team
);

-- Engineers belong to one module/team.
CREATE TABLE engineers (
    id        INTEGER PRIMARY KEY,
    name      TEXT,
    module_id INTEGER REFERENCES modules(id)
);

-- Type-aware quality metric definitions: how each metric maps to risk.
-- good -> ~0 risk, bad -> ~100 risk; direction set by higher_is_better.
CREATE TABLE metric_catalog (
    metric           TEXT,
    module_type      TEXT,
    label            TEXT,
    unit             TEXT,       -- count | % | score | KB | min | ratio
    higher_is_better INTEGER,    -- 1 if a higher value is better
    weight           REAL,       -- weight within this type's quality risk
    good             REAL,
    bad              REAL,
    PRIMARY KEY (metric, module_type)
);

-- Core commit table: one row per commit, git-ready. Shared/process signals only.
CREATE TABLE commits (
    id                  INTEGER PRIMARY KEY,
    commit_id           TEXT UNIQUE,    -- SHA-like; join key for customer issues
    pr_id               TEXT,           -- nullable; git-ready
    module_id           INTEGER REFERENCES modules(id),
    project_id          INTEGER REFERENCES projects(id),
    unit_id             INTEGER REFERENCES units(id),
    week                TEXT,           -- 'W01'..'W12'
    committed_at        TEXT,           -- ISO timestamp

    author_id           INTEGER REFERENCES engineers(id),
    reviewer_id         INTEGER REFERENCES engineers(id),

    -- Delivery (for punctuality)
    targeted_delivery   TEXT,
    actual_delivery     TEXT,

    -- Build / integration (shared across all types)
    build_success           INTEGER,    -- 1 or 0
    integration_total       INTEGER,
    integration_failed      INTEGER,

    -- Review / collaboration
    review_latency_hours    REAL,
    lines_changed           INTEGER
);

-- Type-specific quality values, one row per (commit, metric).
CREATE TABLE commit_metrics (
    commit_id  TEXT REFERENCES commits(commit_id),
    metric     TEXT,
    value      REAL,
    PRIMARY KEY (commit_id, metric)
);

-- Review comments as a first-class entity (NOT pre-aggregated counts).
CREATE TABLE review_comments (
    id          INTEGER PRIMARY KEY,
    commit_id   TEXT REFERENCES commits(commit_id),
    reviewer_id INTEGER REFERENCES engineers(id),
    comment     TEXT,
    severity    TEXT,       -- 'major' or 'minor'
    created_at  TEXT
);

-- ========================================================================
-- Customer DB — support signals, linked back to commits by commit_id
-- ========================================================================

CREATE TABLE customers (
    id    INTEGER PRIMARY KEY,
    name  TEXT
);

CREATE TABLE customer_issues (
    id            INTEGER PRIMARY KEY,
    customer_id   INTEGER REFERENCES customers(id),
    project_id    INTEGER REFERENCES projects(id),
    module_id     INTEGER REFERENCES modules(id),
    commit_id     TEXT REFERENCES commits(commit_id),  -- which commit caused it
    error_info    TEXT,
    severity      TEXT,         -- 'low' | 'medium' | 'high' | 'critical'
    report_time   TEXT,
    resolve_time  TEXT
);

-- ========================================================================
-- Views
-- ========================================================================

-- Per module / week process aggregates (metric-agnostic).
CREATE VIEW weekly_summary AS
SELECT
    week,
    module_id,
    project_id,
    COUNT(*)                                                AS commits_merged,
    ROUND(100.0 * SUM(build_success) / COUNT(*), 1)        AS build_success_rate,
    SUM(integration_failed)                                 AS integration_failures,
    ROUND(100.0 * SUM(integration_failed) /
          NULLIF(SUM(integration_total), 0), 1)             AS integration_fail_pct,
    ROUND(AVG(review_latency_hours), 1)                    AS avg_review_latency
FROM commits
GROUP BY week, module_id;

-- Per module / week / metric averages (type-aware trends).
CREATE VIEW metric_weekly AS
SELECT
    c.week,
    c.module_id,
    cm.metric,
    ROUND(AVG(cm.value), 2) AS avg_value
FROM commits c
JOIN commit_metrics cm ON cm.commit_id = c.commit_id
GROUP BY c.week, c.module_id, cm.metric;

-- Punctuality: how late delivery was vs plan, per module.
CREATE VIEW punctuality AS
SELECT
    module_id,
    project_id,
    COUNT(*)                                                          AS delivered,
    ROUND(AVG(julianday(actual_delivery) - julianday(targeted_delivery)), 1)
                                                                      AS avg_days_late
FROM commits
WHERE targeted_delivery IS NOT NULL AND actual_delivery IS NOT NULL
GROUP BY module_id;

-- Customer issue -> commit -> author/module lineage.
CREATE VIEW customer_trace AS
SELECT
    ci.id            AS issue_id,
    cu.name          AS customer,
    ci.severity      AS issue_severity,
    ci.error_info,
    ci.commit_id,
    m.name           AS module,
    e.name           AS author
FROM customer_issues ci
JOIN customers  cu ON cu.id = ci.customer_id
LEFT JOIN commits   c  ON c.commit_id = ci.commit_id
LEFT JOIN modules   m  ON m.id = c.module_id
LEFT JOIN engineers e  ON e.id = c.author_id;
