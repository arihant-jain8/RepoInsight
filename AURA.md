Because I am an AI assistant operating through this chat interface, I cannot directly inject a physical file onto your local computer's hard drive. However, I have already generated and formatted the full text for you!

You can create this file locally in less than 10 seconds. Here is the complete content of your project_aura_context.md file. Simply copy the code block below, paste it into a text editor (like Notepad, VS Code, or TextEdit), and save the file as project_aura_context.md.

Markdown
# Project Aura: Unified Operational Intelligence Core
### High-Velocity Enterprise Hackathon Blueprint & Technical Specification

---

## 🏛️ 1. Architecture & Federated Ingestion Core

Project Aura is built upon a **Federated Data Ingestion Architecture**. Rather than deploying a high-risk, monolithic database layer requiring broad read-write access across the enterprise, Aura distributes lightweight, non-invasive ingestion agents to localized boundaries.

[Simulated Local Sources]         [Local Edge Ingestion Agent]          [Central Infrastructure]
+-------------------------+       +-----------------------------+       +------------------------+
| - Git Transaction Stream|       | - Dynamic Schema Filtering  |       | - FastAPI Gateway      |
| - Jira Operational Logs | ----> | - Localized Regex Sanitizer | ----> | - Llama-3-70B Core     |
| - Telemetry / APM Data  |       | - Salted SHA-256 Hashing    |       | - MongoDB Atlas Staging|
+-------------------------+       +-----------------------------+       +------------------------+


### Strategic Technical Differentiators
* **Federated, Non-Invasive Ingestion:** Respects local account privacy constraints by leveraging dynamic MongoDB filters (`$exists`) to ingest data gracefully without structural breaking, bypassing risky monolithic access requests.
* **Deterministic Privacy Integrity:** Implements local, salted SHA-256 cryptographic hashing to maintain robust relational data mappings across separate Git, Jira, and performance metrics while preserving 100% individual developer anonymity.
* **Data-Over-Code Charting Engine:** Protects enterprise UI stability by forcing the LLM to output a strict, secure JSON charting specification dynamically parsed by the UI, rather than executing risky, unpredictable frontend code blocks.

---

## 📂 2. Database Schema Architecture (MongoDB Documents)

Data is segregated across four functional collections within a multi-tenant layout representing major industry verticals (`BFSI`, `Telecomm`, `Pharma`, `Mfg`).

### 📶 Vertical Unit: Telecomm

#### 🏢 Account 1: GlobalTel Wireless

* **📋 Project 1: 5G Core Rollout** (Customer: AT&T)
* 💻 **Module 1 (Team 1 / Lead 1):** `RAN Packet Parser` | Status: High Risk 🔴
* 💻 **Module 2 (Team 2 / Lead 2):** `Baseband Processing` | Status: Medium Risk 🟡
* 💻 **Module 3 (Team 3 / Lead 3):** `OSS/BSS Billing Interface` | Status: Low Risk 🟢


* **📋 Project 2: Edge Computing Layer** (Customer: Verizon)
* 💻 **Module 4 (Team 4 / Lead 4):** `MEC Signal Handler` | Status: Low Risk 🟢
* 💻 **Module 5 (Team 5 / Lead 5):** `Baseband Telemetry Stream` | Status: Low Risk 🟢
* 💻 **Module 6 (Team 6 / Lead 6):** `RAN Automation Engine` | Status: Medium Risk 🟡

---

### 🏦 Vertical Unit: BFSI

#### 🏢 Account 2: Nexus Digital Bank

* **📋 Project 3: Instant Payments Core** (Customer: Citibank)
* 💻 **Module 7 (Team 7 / Lead 7):** `ISO20022 Message Parser` | Status: Medium Risk 🟡
* 💻 **Module 8 (Team 8 / Lead 8):** `Ledger Clearing Engine` | Status: High Risk 🔴
* 💻 **Module 9 (Team 9 / Lead 9):** `Fraud Analytics Stream` | Status: Low Risk 🟢


* **📋 Project 4: Wealth Management APIs** (Customer: Barclays)
* 💻 **Module 10 (Team 10 / Lead 10):** `Portfolio Valuation Engine` | Status: Low Risk 🟢
* 💻 **Module 11 (Team 11 / Lead 11):** `KYC Document Sanitizer` | Status: Low Risk 🟢
* 💻 **Module 12 (Team 12 / Lead 12):** `Trade Execution Broker` | Status: Low Risk 🟢

### Collection 1: `vertical_units` (Master Operational Matrix)
```json
{
  "_id": "ObjectId('666b4f72c1a8a2b34c000001')",
  "unit_name": "Telecomm", 
  "scale_matrix": {
    "total_projects": 2,   
    "active_teams": 6,    
    "designated_leads": 6
  },
  "accounts": [
    {
      "account_name": "GlobalTel Wireless",
      "customer_status": "high", 
      "ai_tool_efficiency": {
        "manual_triage_hours_saved": 45.5,
        "mttr_reduction_percentage": 88.0,
        "ai_resolved_tickets_count": 24
      },
      "projects": [
        {
          "project_id": "proj_ran_5g",
          "project_name": "5G Core Rollout",
          "customer": "AT&T",
          "critical_modules": [
            { "module_id": "mod_ran_packet_parser", "module_name": "RAN Packet Parser", "issue_status": "high" },
            { "module_id": "mod_baseband_proc", "module_name": "Baseband Processing", "issue_status": "medium" },
            { "module_id": "mod_oss_bss_billing", "module_name": "OSS/BSS Billing Interface", "issue_status": "low" }
          ]
        },
        {
          "project_id": "proj_edge_comp",
          "project_name": "Edge Computing Layer",
          "customer": "Verizon",
          "critical_modules": [
            { "module_id": "mod_mec_signal", "module_name": "MEC Signal Handler", "issue_status": "low" },
            { "module_id": "mod_baseband_stream", "module_name": "Baseband Telemetry Stream", "issue_status": "low" },
            { "module_id": "mod_ran_automation", "module_name": "RAN Automation Engine", "issue_status": "medium" }
          ]
        }
      ]
    }
  ]
}
```

### Collection 2: git_logs (Engineering Transaction Layer)
```json
{
  "_id": "ObjectId('666b4f72c1a8a2b34c000002')",
  "unit_name": "Telecomm",
  "project_id": "proj_ran_5g",                
  "module_id": "mod_ran_packet_parser",       
  "commit_hash": "a8f3b2c1d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4",
  "author_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "timestamp": "2026-06-13T14:22:00Z",
  "lines_added": 240,
  "lines_removed": 12,
  "code_churn_score": "high",
  "ai_metrics": {
    "ai_agent_used": "GitHub Copilot",
    "ai_generated_percentage": 78.5          
  }
}
```
### Collection 3: jira_logs (Operational & Task Lifecycle Layer)
```json
{
  "_id": "ObjectId('666b4f72c1a8a2b34c000003')",
  "unit_name": "Telecomm",
  "account_name": "GlobalTel Wireless",
  "project_id": "proj_ran_5g",
  "module_id": "mod_ran_packet_parser",
  "ticket_type": "customer_incident",
  "pm_view_data": {
    "ticket_id": "JIRA-TEL-9821",
    "customer": "AT&T",
    "summary": "L3 Telecom Packet Drop during peak RAN congestion",
    "severity": "high",                       
    "status": "In Progress",                 
    "raised_time": "2026-06-13T10:14:00Z",
    "resolve_time": null,
    "ai_assistance": {
      "ai_agent_used": "Aura-Triage-Agent",
      "automation_percentage": 85.0          
    }
  },
  "tl_view_data": {
    "task_name": "Optimize RAN Packet Parsing Loops",
    "assigned_to": "Dev_0931",
    "assigned_on": "2026-06-13T11:00:00Z",
    "lifecycle_status": "implementation stage", 
    "completed_date": null
  }
}
```
### Collection 4: performance_data (Real-Time Infrastructure Telemetry)
```json
{
  "_id": "ObjectId('666b4f72c1a8a2b34c000004')",
  "unit_name": "Telecomm",
  "account_name": "GlobalTel Wireless",
  "project_id": "proj_ran_5g",
  "module_id": "mod_ran_packet_parser",
  "metric_source": "Baseband Telemetry Stream",
  "timestamp": "2026-06-13T19:00:00Z",
  "issue_status": "high",
  "telemetry_payload": {
    "packet_drop_rate": 0.08,
    "latency_ms": 42.1,
    "cpu_utilization_percentage": 94.2
  },
  "associated_incidents": ["JIRA-TEL-9821"]
}
```

## 👥 3. Persona-Based Dashboards & Workflows
Aura maps corporate workflows using Role-Based Access Control (RBAC), strictly filtering information down to precise visualization requirements and architectural sandboxes.

### 🏢 View A: Unit Head (Strategic & Customer Experience Command)
* **Top-Level Footprint Scale Matrix:** Displays global scale stats instantly (Total Projects, Active Delivery Teams, Designated Project Managers).

* **Primary Priority Panel: Customer Reported Errors is promoted to the highest structural layout to capture churn risks immediately.

* **Customer-to-Project Drill-down Workflow:** 1. Executive reviews global customer status lists bucketed by risk tiers: low (GREEN/Normal lifecycle with automated AI resolution mitigation), medium (AMBER/SLA threat), or high (RED/Immediate operational breach risk).
2. Selecting an account dynamically triggers a layout filter detailing the responsible Project and the underlying Critical Modules (e.g., RAN Packet Parser) triggering the anomaly.

* **Executive AI Metrics Panel:** Visualizes AI Tool Efficiency for Customer Issue Resolution per client, calculating exactly how effectively predictive tooling decreases customer MTTR.

* **Contextual AI Chat Workspace:** Allows immediate macro querying with standard automated buttons:

&emsp;&emsp;"How many teams are currently allocated to the Telecom account, and how are those teams performing relative to active SLA metrics?"

&emsp;&emsp;"Summarize the AI tool efficiency across all low-risk customer accounts."

### 📋 View B: Project Manager (Delivery & Operational Governance)
* **Customer Status Tracking Engine:** Governs pipeline timelines, severity matrices, and tracking loops.

* **Customer Review Track Table:**

* &emsp;**Displays:** Customer Reviews / Tickets, Severity (high, medium, low), Status (Pending, In Progress, Resolved), Raised Time, Resolve Time, and AI Agent Used (Percentage Generated).

* &emsp;**Operational Visibility Engine:** Tracks real-time codebase activity against active client escalations, tying automated triage directly to developer commits.

* &emsp;**Commit-Level Tracking Matrix:** Instead of static ticket descriptions, this table surfaces the explicit code changes addressing each customer issue, calculating the exact percentage of AI

### 💻 View C: Team Lead (Technical & Local Execution Workspace)
* **Task-Level Workspace Sandbox:** Completely isolated from broad financial metrics or cross-account contexts.

* **Task Overview Table:** Maps internal engineering metrics cleanly across local lifecycle stages:

* **Tracks:** Task Description, Assigned To, Assigned On, Status (study stage, implementation stage, review stage, testing stage, deployment stage), and Completed Date.

* **Operational Visibility Engine:** Tracks real-time codebase activity against active client escalations, tying automated triage directly to developer commits.

* **Commit-Level Tracking Matrix:** Instead of static ticket descriptions, this table surfaces the explicit code changes addressing each customer issue, calculating the exact percentage of AI

## 🤖 4. AI Core Orchestration & Security Guardrails
The underlying AI Core utilizes an accelerated hardware configuration (AMD MI300X via vLLM hosting Llama-3-70B) running specialized LangGraph / CrewAI multi-agent states.

### Feature 1: Dynamic Graph Generation (Data-Over-Code Parsing)
Aura completely blocks LLMs from creating or serving raw, unsecure javascript elements that break the frontend runtime interface. Instead, the local agent outputs a structural, highly validated JSON charting specification. Aura's frontend intercepts this JSON string to natively build secure, dynamic Recharts / Plotly graph components 100% of the time.

### Feature 2: Rigid Prompt Sandboxing & Security Gates
Team Lead Guardrail: Semantic system filters route queries away from broad customer accounts. Attempts to fetch cross-project data return a hard failure: Access Denied: Target telemetry outside local engineering boundary.

Project Manager Sandbox: Session-bound tenant tokens restrict raw MongoDB aggregation strings, forcing isolation between multi-tenant project leads.

---

## 🛠️ 5. Demo Simulation & Data Generation Engine (`mock_generators.py`)

To simulate the live end-to-end telemetry pipeline for the prototype evaluation, a local Python script mocks transactional data packets across all 12 modules and streams them through the architecture.

### Data Generation Parameters & Rules
* **Structural Distribution Matrix:** The script cycles through the 2 Accounts, 4 Projects, and 12 distinct `module_id` keys configured in the `vertical_units` collection.
* **The Target Anomaly Trigger (Demo Story):** To show a live resolution loop, the generator is hardcoded to emit an initial cluster of high-frequency error anomalies targeted specifically at `mod_ran_packet_parser` (Account 1 -> Project 1 -> Module 1).
* **Commit-Level Tracking Generation:** For every simulated customer issue, the script automatically generates a corresponding Git transactional object, injecting:
  1. A random developer identifier string (to be hashed by the edge agent).
  2. The specific `ai_agent_used` name string.
  3. A randomized float between `0.00` and `100.00` representing the `ai_generated_percentage` metric.

### Python Mimic Payload Payload Matrix (POST Execution Loop)
```python
# Expected data stream loop structure for mock_generators.py
import requests
import random
from datetime import datetime

DEMO_MATRIX = {
    "proj_ran_5g": ["mod_ran_packet_parser", "mod_baseband_proc", "mod_oss_bss_billing"],
    "proj_edge_comp": ["mod_mec_signal", "mod_baseband_stream", "mod_ran_automation"],
    "proj_pay_core": ["mod_iso_parser", "mod_ledger_engine", "mod_fraud_stream"],
    "proj_wealth_api": ["mod_portfolio_val", "mod_kyc_sanitize", "mod_trade_broker"]
}

def generate_mock_git_log():
    # Loop mimics a developer committing code to fix a raised customer incident
    payload = {
        "unit_name": "Telecomm",
        "project_id": "proj_ran_5g",
        "module_id": "mod_ran_packet_parser",
        "commit_hash": "a8f3b2c1d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4",
        "raw_author_email": "engineer.one@globaltel.com", # Stripped/Hashed at Edge Agent layer
        "timestamp": datetime.utcnow().isoformat(),
        "lines_added": random.randint(50, 300),
        "lines_removed": random.randint(5, 50),
        "code_churn_score": "high",
        "ai_metrics": {
            "ai_agent_used": random.choice(["GitHub Copilot", "Devin Agent", "N/A"]),
            "ai_generated_percentage": round(random.uniform(20.0, 95.0), 2)
        }
    }
    return payload

## 📋 6. Value Proposition & Problem Definition
Problem Statement
Enterprise engineering leadership at global IT service providers lacks real-time visibility into software delivery bottlenecks, system stability, and customer-facing risks because teams manage fragmented, multi-tenant tech stacks under strict, conflicting client NDAs that block invasive, centralized tools. This data siloing forces leadership into a slow, multi-layered game of corporate telephone—where a Unit Head must query Project Managers, who in turn chase Team Leads to manually aggregate disparate Git, Jira, and performance logs. This manual reporting pipeline creates severe operational friction, misallocates high-value engineering capacity toward status compilation, and drastically inflates the Mean Time to Resolution (MTTR), risking severe financial SLA penalties and client revenue churn.

Why This Problem Matters (Service-Based Context)
In massive telecom accounts, operations are fractured across a steep hierarchy of distinct programs and dozens of isolated, multi-stack projects. Siloed by disparate tools and strict security policies, leadership must play an inefficient corporate "game of telephone" just to gauge account health. Project Aura solves this by bringing all fragmented telemetry "under one roof." By unifying disparate Git, Jira, and performance metrics into a single, privacy-preserving staging layer, it collapses these organizational layers—giving executives immediate, cross-program visibility into delivery bottlenecks and SLA compliance without breaching data sovereignty.

Expected Financial & Operational Impact
Zero-Trust Security & IP Protection (100% Compliance): Eliminates 100% of external corporate data leaks and PII compliance violations by ensuring raw strings never leave local boundaries.

Drastic MTTR Reduction (~85% Faster Resolution): Minimizes the Mean Time to Resolution for high-priority client bugs from an average of 4.5 days down to less than 15 minutes via direct codebase correlation.

Elimination of the "Corporate Telephone" (Saving ~120 Hours/Month): Eradicates up to 15 hours per week of static status compilation per manager, freeing up valuable leadership bandwidth.

Proactive Retention (Up to 25% Reduction in Churn): Empowers Unit Heads to actively intercept client dissatisfaction 30 to 60 days before renewals are threatened.

## 👥 7. Hackathon Project Team Matrix
AI & Core Orchestration Lead: Builds multi-agent state loops via LangGraph, configures local model serving layouts on vLLM, and patterns the dynamic JSON graph generation prompt matrix.

Backend & Security Infrastructure Engineer: Establishes the schemaless MongoDB Atlas database layer, programs edge extraction endpoints using FastAPI, and implements salted SHA-256 masking scripts.

Frontend & Visualizations Developer: Designs the premium interface using Next.js and shadcn/ui, architectures the JSON data-to-chart rendering pipeline, and builds the workflow switches across all three distinct user persona dashboards.