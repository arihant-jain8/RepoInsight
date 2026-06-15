"""Edge ingestion agent (API_GATEWAY_DECISION showcase).

Reads a held-back project's source bundle and forwards it to central staging
through the API gateway. In the federated AURA.md design there is one agent per
local source; for this demo we build a single real agent (5G Core Rollout), the
rest are pre-loaded.

Dynamic schema filtering ($exists semantics): forward only fields that are present
— never break on a missing key.

CLI:  python -m aura.ingestion.edge_agent [proj_key]
"""

import json
import os

import httpx

from aura import config

SOURCES_DIR = os.path.join(config.PROJECT_ROOT, "data", "sources")


def filter_fields(record):
    """Recursively drop None fields ($exists semantics) — keep present fields/lists."""
    if isinstance(record, dict):
        return {k: filter_fields(v) for k, v in record.items() if v is not None}
    if isinstance(record, list):
        return [filter_fields(v) for v in record]
    return record


def load_bundle(proj_key: str) -> dict:
    with open(os.path.join(SOURCES_DIR, f"{proj_key}.json"), encoding="utf-8") as f:
        return json.load(f)


def has_source(proj_key: str) -> bool:
    return os.path.exists(os.path.join(SOURCES_DIR, f"{proj_key}.json"))


def forward(proj_key: str, gateway_url: str | None = None) -> dict:
    """Read the project's source bundle, filter, and POST it to the gateway."""
    gateway_url = gateway_url or config.GATEWAY_URL
    bundle = filter_fields(load_bundle(proj_key))
    r = httpx.post(f"{gateway_url}/ingest/project", json=bundle, timeout=60)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else "proj_ran_5g"
    print(forward(key))
