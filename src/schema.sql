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
DROP VIEW  IF EXISTS customer_issues;    -- now a VIEW over jira_logs (Phase 1.3)
DROP VIEW  IF EXISTS punctuality;
DROP VIEW  IF EXISTS weekly_summary;
DROP TABLE IF EXISTS performance_data;   -- new (Phase 1.4)
DROP TABLE IF EXISTS jira_logs;          -- new (Phase 1.3)
DROP TABLE IF EXISTS ai_tool_efficiency; -- new (Phase 1.2)
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS commit_metrics;
DROP TABLE IF EXISTS review_comments;
DROP TABLE IF EXISTS commits;
DROP TABLE IF EXISTS engineers;
DROP TABLE IF EXISTS modules;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS accounts;           -- new (Phase 1.1)
DROP TABLE IF EXISTS units;              -- legacy; replaced by vertical_units
DROP TABLE IF EXISTS vertical_units;     -- new (Phase 1.1)
DROP TABLE IF EXISTS metric_catalog;

-- ========================================================================
-- Internal DB — hierarchy: vertical_unit -> account -> project -> module -> commit
-- ========================================================================

-- Vertical unit (industry vertical, e.g. Telecomm / BFSI). Replaces the old
-- single-org `units` table; `head` carries the Unit Head persona's name.
CREATE TABLE vertical_units (
    id      INTEGER PRIMARY KEY,
    name    TEXT,
    head    TEXT            -- Unit Head (persona)
);

-- Account = client org within a vertical (e.g. GlobalTel Wireless, Nexus Digital
-- Bank). customer_status mirrors the RED/AMBER/GREEN bucket at account level.
CREATE TABLE accounts (
    id              INTEGER PRIMARY KEY,
    vertical_id     INTEGER REFERENCES vertical_units(id),
    name            TEXT,
    customer_status TEXT            -- low | medium | high
);

-- Per-account AI tooling efficiency (AURA.md accounts[].ai_tool_efficiency).
CREATE TABLE ai_tool_efficiency (
    account_id                INTEGER REFERENCES accounts(id),
    manual_triage_hours_saved REAL,
    mttr_reduction_percentage REAL,
    ai_resolved_tickets_count INTEGER
);

CREATE TABLE projects (
    id         INTEGER PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id),   -- was unit_id -> units(id)
    proj_key   TEXT,        -- AURA.md ingestion id, e.g. 'proj_ran_5g'
    name       TEXT,
    customer   TEXT,        -- end client, e.g. 'AT&T' / 'Verizon'
    manager    TEXT         -- Project Manager (persona)
);

CREATE TABLE modules (
    id           INTEGER PRIMARY KEY,
    project_id   INTEGER REFERENCES projects(id),
    mod_key      TEXT,       -- AURA.md ingestion id, e.g. 'mod_ran_packet_parser'
    name         TEXT,       -- e.g. 'auth-service'
    type         TEXT,       -- network | backend | frontend | ai
    repo_url     TEXT,       -- multi-repo: each module = its own git repo
    team_lead_id INTEGER REFERENCES engineers(id),  -- FK (was free text)
    team_size    INTEGER,    -- people on the team
    issue_status TEXT        -- low | medium | high (mirrors RED/AMBER/GREEN)
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
    lines_changed           INTEGER,

    -- AI tooling (AURA.md git_logs: churn + ai_metrics)
    lines_added             INTEGER,
    lines_removed           INTEGER,
    code_churn_score        TEXT,       -- low | medium | high
    ai_agent_used           TEXT,       -- e.g. 'GitHub Copilot' | 'Devin Agent' | 'N/A'
    ai_generated_percentage REAL        -- 0..100, AI-authored share of the commit
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

-- Jira tickets / customer incidents (AURA.md jira_logs, flattened from
-- pm_view_data / tl_view_data). commit_id preserves issue->commit traceability;
-- customer is derived via module -> project.customer (no separate customers tbl).
CREATE TABLE jira_logs (
    id                    INTEGER PRIMARY KEY,
    ticket_id             TEXT,       -- e.g. 'JIRA-TEL-9821'
    module_id             INTEGER REFERENCES modules(id),
    commit_id             TEXT REFERENCES commits(commit_id),  -- causing/fixing commit
    ticket_type           TEXT,       -- e.g. 'customer_incident'
    summary               TEXT,
    severity              TEXT,       -- low | medium | high | critical
    status                TEXT,       -- Pending | In Progress | Resolved
    raised_time           TEXT,
    resolve_time          TEXT,
    automation_percentage REAL,       -- pm_view_data.ai_assistance.automation_percentage
    assigned_to           TEXT,       -- tl_view_data.assigned_to (e.g. 'Dev_0931')
    task_name             TEXT,       -- tl_view_data.task_name
    lifecycle_status      TEXT,       -- study|implementation|review|testing|deployment
    completed_date        TEXT
);

-- Real-time infrastructure telemetry per module (AURA.md performance_data).
-- associated_incidents flattened to comma-separated jira ticket_ids (no arrays).
CREATE TABLE performance_data (
    id                         INTEGER PRIMARY KEY,
    module_id                  INTEGER REFERENCES modules(id),
    metric_source              TEXT,
    timestamp                  TEXT,
    issue_status               TEXT,       -- low | medium | high
    packet_drop_rate           REAL,
    latency_ms                 REAL,
    cpu_utilization_percentage REAL,
    associated_incidents       TEXT        -- comma-separated jira ticket_ids
);

-- (No standalone `customers` table — the customers are AT&T/Verizon/etc., now
-- carried on projects.customer. `customer_issues` is a back-compat VIEW over
-- jira_logs, defined in the Views section below.)

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

-- Back-compat view: customer issues over jira_logs. customer is derived via
-- module -> project.customer (no customers table). Old column names
-- (error_info, report_time) are preserved so existing analytics keep resolving.
CREATE VIEW customer_issues AS
SELECT
    j.id           AS id,
    j.module_id    AS module_id,
    m.project_id   AS project_id,
    j.commit_id    AS commit_id,
    j.summary      AS error_info,
    j.severity     AS severity,
    j.raised_time  AS report_time,
    j.resolve_time AS resolve_time,
    p.customer     AS customer
FROM jira_logs j
LEFT JOIN modules  m ON m.id = j.module_id
LEFT JOIN projects p ON p.id = m.project_id;

-- Customer issue -> commit -> author/module lineage.
CREATE VIEW customer_trace AS
SELECT
    ci.id            AS issue_id,
    ci.customer      AS customer,
    ci.severity      AS issue_severity,
    ci.error_info,
    ci.commit_id,
    m.name           AS module,
    e.name           AS author
FROM customer_issues ci
LEFT JOIN commits   c  ON c.commit_id = ci.commit_id
LEFT JOIN modules   m  ON m.id = c.module_id
LEFT JOIN engineers e  ON e.id = c.author_id;
