-- Engineering Intelligence Copilot — central database schema
-- One SQLite file holds two logical groups: the internal DB (engineering
-- activity) and the customer DB (support signals), joined by commit_id so any
-- customer issue can be traced back to the commit that caused it.
--
-- The commits table is git-shaped: a real ingestion worker can later fill
-- commit_id / author / reviewer / module / review comments / actual_delivery
-- straight from git + the GitHub API with no schema change.

-- Drop in dependency order so re-seeding is idempotent.
DROP VIEW  IF EXISTS customer_trace;
DROP VIEW  IF EXISTS punctuality;
DROP VIEW  IF EXISTS weekly_summary;
DROP TABLE IF EXISTS customer_issues;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS review_comments;
DROP TABLE IF EXISTS commits;
DROP TABLE IF EXISTS engineers;
DROP TABLE IF EXISTS modules;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS units;

-- ========================================================================
-- Internal DB — organisational hierarchy: unit -> project -> module -> commit
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
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER REFERENCES projects(id),
    name        TEXT,       -- e.g. 'auth-service'
    type        TEXT,       -- generic: backend | frontend | ai | network | ...
    repo_url    TEXT,       -- multi-repo: each module = its own git repo
    team_lead   TEXT,       -- Team Lead (persona)
    team_size   INTEGER     -- people on the team (Unit Head's team-size view)
);

CREATE TABLE engineers (
    id    INTEGER PRIMARY KEY,
    name  TEXT
);

-- Core commit table: one row per commit, git-ready.
CREATE TABLE commits (
    id                  INTEGER PRIMARY KEY,
    commit_id           TEXT UNIQUE,    -- SHA-like; join key for customer issues
    pr_id               TEXT,           -- nullable; git-ready (e.g. 'NET-PR-047')
    module_id           INTEGER REFERENCES modules(id),
    project_id          INTEGER REFERENCES projects(id),
    unit_id             INTEGER REFERENCES units(id),
    week                TEXT,           -- 'W01'..'W12'
    committed_at        TEXT,           -- ISO timestamp

    author_id           INTEGER REFERENCES engineers(id),
    reviewer_id         INTEGER REFERENCES engineers(id),

    -- Delivery (for punctuality)
    targeted_delivery   TEXT,           -- planned date
    actual_delivery     TEXT,           -- merge date (from git later)

    -- Build / CI (synthetic until CI integration)
    build_success           INTEGER,    -- 1 or 0
    compile_warnings        INTEGER,
    clang_warnings          INTEGER,
    codechecker_findings    INTEGER,
    codechecker_critical    INTEGER,
    asan_failures           INTEGER,
    integration_total       INTEGER,
    integration_failed      INTEGER,

    -- Review / collaboration
    review_latency_hours    REAL,
    lines_changed           INTEGER
);

-- Review comments as a first-class entity (NOT pre-aggregated counts).
-- A commit has 0..N rows of mixed severity; major/minor counts are derived
-- with GROUP BY severity, never stored as columns.
CREATE TABLE review_comments (
    id          INTEGER PRIMARY KEY,
    commit_id   TEXT REFERENCES commits(commit_id),
    reviewer_id INTEGER REFERENCES engineers(id),
    comment     TEXT,       -- the comment itself
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
    commit_id     TEXT REFERENCES commits(commit_id),  -- which commit caused this issue
    error_info    TEXT,
    severity      TEXT,         -- 'low' | 'medium' | 'high' | 'critical'
    report_time   TEXT,
    resolve_time  TEXT          -- nullable while open
);

-- ========================================================================
-- Views
-- ========================================================================

-- Per module / week aggregates, computed on the commits table.
CREATE VIEW weekly_summary AS
SELECT
    week,
    module_id,
    project_id,
    COUNT(*)                                                AS commits_merged,
    ROUND(100.0 * SUM(build_success) / COUNT(*), 1)        AS build_success_rate,
    SUM(clang_warnings)                                     AS total_clang_warnings,
    ROUND(SUM(clang_warnings) * 1.0 / COUNT(*), 1)         AS avg_clang_warnings_per_commit,
    SUM(asan_failures)                                      AS total_asan_failures,
    SUM(integration_failed)                                 AS integration_failures,
    ROUND(100.0 * SUM(integration_failed) /
          NULLIF(SUM(integration_total), 0), 1)             AS integration_fail_pct,
    ROUND(AVG(review_latency_hours), 1)                    AS avg_review_latency
FROM commits
GROUP BY week, module_id;

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
