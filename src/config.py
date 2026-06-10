"""Central configuration: database path + pluggable LLM settings.

The LLM layer speaks the OpenAI-compatible /v1/chat/completions API, so the same
code works against a small local model now (Ollama on this Windows PC) and a larger
model later (vLLM + Qwen on the AMD/ROCm machine). Switching backends = changing the
env vars below; no code changes.
"""

import os

# --- Database -------------------------------------------------------------
# One central SQLite file that every (simulated) per-module agent writes into.
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, "data", "engineering.db")
SCHEMA_PATH = os.path.join(SRC_DIR, "schema.sql")

# --- LLM (pluggable) ------------------------------------------------------
# Default: small local model via Ollama (OpenAI-compatible endpoint).
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")  # or "llama3.2:3b"
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed-for-local")

# To run on the AMD/ROCm machine with vLLM, set:
#   LLM_BASE_URL=http://localhost:8000/v1
#   LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
