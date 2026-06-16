# Organisation structure

Hierarchy: **vertical_unit → account → project → module → commit**. The customer (end client)
lives on the project. There is no separate units or customers table.

Two verticals → two accounts → four projects → twelve modules:

## Telecomm  (head: Michael Scott)
**Account: GlobalTel Wireless** (customer_status: high)

- **Project: 5G Core Rollout** — customer **AT&T**, manager **Jim Halpert**
  - RAN Packet Parser (network)
  - Baseband Processing (network)
  - OSS/BSS Billing Interface (backend)
- **Project: Edge Computing Layer** — customer **Verizon**, manager **Pam Beesly**
  - MEC Signal Handler (network)
  - Baseband Telemetry Stream (network)
  - RAN Automation Engine (backend)

## BFSI  (head: David Wallace)
**Account: Nexus Digital Bank** (customer_status: high)

- **Project: Instant Payments Core** — customer **Citibank**, manager **Dwight Schrute**
  - ISO20022 Message Parser (backend)
  - Ledger Clearing Engine (backend)
  - Fraud Analytics Stream (ai)
- **Project: Wealth Management APIs** — customer **Barclays**, manager **Oscar Martinez**
  - Portfolio Valuation Engine (backend)
  - KYC Document Sanitizer (ai)
  - Trade Execution Broker (backend)

> Note: **5G Core Rollout** may be held back for the live-ingestion demo, so the live DB
> sometimes contains only 3 of the 4 projects (it is re-ingested on the Architecture page).
