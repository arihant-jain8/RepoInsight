"""Inference performance — live benchmark of the AI core.

Runs a few example scenarios through the local model and reports tokens used,
end-to-end latency, and GPU usage (util + memory, peak during the run vs idle).
GPU reads are vendor-aware (nvidia-smi locally, rocm-smi/amd-smi on the AMD box).
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".."))

import pandas as pd
import streamlit as st

from aura.ai import agent
from aura.analytics import analytics
from aura import config
from aura.ai import llm_service
from aura.ai import perf
from aura import ui

st.set_page_config(page_title="Performance", page_icon="⚡", layout="wide")
ui.require_db()

st.title("⚡ Inference Performance")
st.caption("Live benchmark of the AI core: tokens used, end-to-end latency, and GPU usage.")


def _run_metered(label, messages):
    """A single-call scenario: tokens + latency from the API, peak GPU sampled."""
    with perf.GpuPeakSampler() as gpu:
        r = perf.metered_call(messages)
    return {
        "scenario": label, "calls": 1,
        "prompt_tok": r["prompt_tokens"], "completion_tok": r["completion_tokens"],
        "total_tok": r["total_tokens"], "latency_s": r["latency_s"],
        "tok_per_s": round(r["completion_tokens"] / r["latency_s"], 1) if r["latency_s"] else 0,
        "peak_util_%": round(gpu.peak["util_pct"]), "peak_mem_GB": round(gpu.peak["mem_used_mb"] / 1024, 2),
        "ok": r["ok"], "error": r.get("error", ""),
    }


def _run_agentic(label, question):
    """The agentic copilot: tokens are summed across its tool-loop calls; latency is
    wall-clock for the whole loop. tok/s = total completion tokens ÷ latency."""
    with perf.GpuPeakSampler() as gpu:
        t0 = time.perf_counter()
        res = agent.agent_chat(question)
        latency = round(time.perf_counter() - t0, 2)
    completion = res.get("completion_tokens", 0)
    return {
        "scenario": label, "calls": res.get("calls", 0),
        "prompt_tok": res.get("prompt_tokens", 0), "completion_tok": completion,
        "total_tok": res.get("tokens", 0), "latency_s": latency,
        "tok_per_s": round(completion / latency, 1) if latency else 0,
        "peak_util_%": round(gpu.peak["util_pct"]), "peak_mem_GB": round(gpu.peak["mem_used_mb"] / 1024, 2),
        "ok": True, "error": "",
    }


# --- Status header --------------------------------------------------------
model_up = llm_service.is_available()
idle = perf.gpu_snapshot()
backend = perf.gpu_backend()

c1, c2, c3 = st.columns(3)
c1.metric("Model", config.LLM_MODEL)
c2.metric("Endpoint", "🟢 online" if model_up else "🔴 offline")
c3.metric("GPU", idle["name"] if idle else (backend or "none detected"))

if idle:
    st.caption(f"**Idle GPU baseline** ({idle['vendor']}): {idle['util_pct']:.0f}% util · "
               f"{idle['mem_used_mb'] / 1024:.2f} / {idle['mem_total_mb'] / 1024:.1f} GB")
else:
    st.caption("No GPU tool detected (nvidia-smi / rocm-smi / amd-smi) — "
               "tokens + latency will still be measured.")

if not model_up:
    st.error(f"Model endpoint offline (`{config.LLM_BASE_URL}`). Start Ollama and the model:\n\n"
             f"```\nollama run {config.LLM_MODEL}\n```")

# --- Run + results --------------------------------------------------------
if st.button("▶ Run benchmark", type="primary", disabled=not model_up):
    with st.spinner("Running scenarios through the model…"):
        rows = [
            _run_metered("Org summary report", llm_service.org_messages()),
            _run_metered("Module deep-dive report",
                         llm_service.module_messages(analytics.list_modules()[0]["id"])),
            _run_agentic("Copilot Q&A (agentic)", "Which module is highest risk and why?"),
        ]
    st.session_state["perf_rows"] = rows

rows = st.session_state.get("perf_rows")
if rows:
    st.subheader("Results")
    df = pd.DataFrame(rows)[["scenario", "calls", "prompt_tok", "completion_tok",
                             "total_tok", "latency_s", "tok_per_s",
                             "peak_util_%", "peak_mem_GB"]]
    st.dataframe(df, width="stretch", hide_index=True)

    peak_util = max(r["peak_util_%"] for r in rows)
    peak_mem = max(r["peak_mem_GB"] for r in rows)
    s1, s2, s3 = st.columns(3)
    s1.metric("Peak GPU util (during runs)", f"{peak_util:.0f}%",
              delta=f"{peak_util - (idle['util_pct'] if idle else 0):.0f}% vs idle")
    s2.metric("Peak GPU memory", f"{peak_mem:.2f} GB")
    s3.metric("Total tokens (all scenarios)", sum(r["total_tok"] for r in rows))

    for r in rows:
        if not r["ok"]:
            st.warning(f"{r['scenario']} failed: {r['error']}")
    st.caption("Latency = client-side wall-clock to the full response. `tok_per_s` = "
               "completion tokens ÷ latency. Agentic scenario sums tokens across its tool-loop calls.")
