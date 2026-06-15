"""Showcase API gateway (API_GATEWAY_DECISION) — stdlib, zero extra deps.

Why stdlib http.server instead of FastAPI? FastAPI pins starlette<0.42, which
clashes with Streamlit 1.58 (needs starlette 1.2.x). A 3-endpoint demo gateway
doesn't need a framework, so we use the standard library — no dependency conflict.

Endpoints:
  GET  /healthz          -> {"status":"ok"}
  GET  /stats            -> central-DB row counts (for the Architecture page)
  POST /ingest/project   -> ingest a held-back project bundle into central staging

Run from the project root:  python -m aura.ingestion.gateway   (or set GATEWAY_PORT)
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Make sibling modules (database, repository, config) importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aura.data import database      # noqa: E402
from aura.data import repository    # noqa: E402

REQUIRED_KEYS = {"account_name", "project", "modules", "engineers", "commits",
                 "commit_metrics", "review_comments", "jira_logs", "performance_data"}


def _stats() -> dict:
    def n(table):
        return database.query(f"SELECT COUNT(*) AS c FROM {table}")[0]["c"]
    return {
        "verticals": n("vertical_units"), "accounts": n("accounts"),
        "projects": n("projects"), "modules": n("modules"),
        "commits": n("commits"), "jira_logs": n("jira_logs"),
        "performance_data": n("performance_data"),
        "project_names": [r["name"] for r in
                          database.query("SELECT name FROM projects ORDER BY id")],
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            self._send(200, {"status": "ok", "service": "aura-ingestion-gateway"})
        elif self.path == "/stats":
            self._send(200, _stats())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/ingest/project":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            bundle = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"})
            return
        missing = REQUIRED_KEYS - set(bundle)
        if missing:
            self._send(422, {"error": f"missing keys: {sorted(missing)}"})
            return
        try:
            summary = repository.ingest_project_bundle(bundle)
        except ValueError as e:
            self._send(422, {"error": str(e)})
            return
        self._send(200, {"status": "staged", **summary})

    def log_message(self, fmt, *args):   # quieter, prefixed console output
        sys.stderr.write("[gateway] " + (fmt % args) + "\n")


def main():
    port = int(os.getenv("GATEWAY_PORT", "8000"))
    print(f"Aura ingestion gateway on http://localhost:{port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
