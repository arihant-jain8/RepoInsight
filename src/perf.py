"""Inference performance metrics: GPU usage, token usage, end-to-end latency.

Vendor-aware GPU reads — `nvidia-smi` (local NVIDIA) or `rocm-smi` / `amd-smi`
(the AMD/ROCm machine the repo deploys to). One module, auto-detected, so the same
committed code runs in both places. The NVIDIA path is verified locally; the AMD
paths are written defensively and should be confirmed on the AMD box.
"""

import json
import shutil
import subprocess
import threading
import time

import httpx

import config

_CHAT_URL = f"{config.LLM_BASE_URL}/chat/completions"
_HEADERS = {"Authorization": f"Bearer {config.LLM_API_KEY}"}

# Detection order: nvidia first (local dev box), then AMD tools (deploy target).
_GPU_TOOLS = ("nvidia-smi", "rocm-smi", "amd-smi")


def gpu_backend():
    """Name of the first available GPU CLI on PATH, or None."""
    for tool in _GPU_TOOLS:
        if shutil.which(tool):
            return tool
    return None


def _run(cmd, timeout=5):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout


def gpu_snapshot():
    """One reading: {vendor, name, util_pct, mem_used_mb, mem_total_mb} or None."""
    tool = gpu_backend()
    try:
        if tool == "nvidia-smi":
            out = _run(["nvidia-smi",
                        "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                        "--format=csv,noheader,nounits"])
            name, util, used, total = [x.strip() for x in out.splitlines()[0].split(",")]
            return {"vendor": "nvidia", "name": name, "util_pct": float(util),
                    "mem_used_mb": float(used), "mem_total_mb": float(total)}
        if tool == "rocm-smi":
            # ROCm key names vary across versions — best-effort, verify on the AMD box.
            d = json.loads(_run(["rocm-smi", "--showuse", "--showmeminfo", "vram", "--json"]))
            card = next(iter(d.values()))
            return {"vendor": "amd", "name": card.get("Card series", "AMD GPU"),
                    "util_pct": float(card.get("GPU use (%)", 0) or 0),
                    "mem_used_mb": float(card.get("VRAM Total Used Memory (B)", 0) or 0) / 1e6,
                    "mem_total_mb": float(card.get("VRAM Total Memory (B)", 0) or 0) / 1e6}
        if tool == "amd-smi":
            d = json.loads(_run(["amd-smi", "metric", "--usage", "--mem-usage", "--json"]))
            g = d[0] if isinstance(d, list) else d
            used = g.get("mem_usage", {}).get("used_vram", {}).get("value", 0)
            total = g.get("mem_usage", {}).get("total_vram", {}).get("value", 0)
            return {"vendor": "amd", "name": g.get("market_name", "AMD GPU"),
                    "util_pct": float(g.get("usage", {}).get("gfx_activity", {}).get("value", 0) or 0),
                    "mem_used_mb": float(used or 0), "mem_total_mb": float(total or 0)}
    except Exception:
        return None
    return None


class GpuPeakSampler:
    """Context manager that background-samples the GPU and records the peak."""

    def __init__(self, interval: float = 0.25):
        self.interval = interval
        self.peak = {"util_pct": 0.0, "mem_used_mb": 0.0}
        self.available = gpu_backend() is not None
        self._stop = threading.Event()
        self._thread = None

    def _loop(self):
        while not self._stop.is_set():
            s = gpu_snapshot()
            if s:
                self.peak["util_pct"] = max(self.peak["util_pct"], s["util_pct"])
                self.peak["mem_used_mb"] = max(self.peak["mem_used_mb"], s["mem_used_mb"])
            self._stop.wait(self.interval)

    def __enter__(self):
        if self.available:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        return False


def metered_call(messages: list, max_tokens: int | None = None) -> dict:
    """Timed chat-completions call; returns text + token usage + latency.
    ok=False on any failure (so the page can show a graceful error)."""
    payload = {"model": config.LLM_MODEL, "messages": messages,
               "max_tokens": max_tokens or config.LLM_MAX_TOKENS, "temperature": 0.3}
    t0 = time.perf_counter()
    try:
        r = httpx.post(_CHAT_URL, json=payload, headers=_HEADERS, timeout=config.LLM_TIMEOUT)
        r.raise_for_status()
        latency = time.perf_counter() - t0
        data = r.json()
        usage = data.get("usage") or {}
        return {"ok": True, "text": data["choices"][0]["message"]["content"],
                "latency_s": round(latency, 2),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)}
    except Exception as e:
        return {"ok": False, "error": str(e), "text": "",
                "latency_s": round(time.perf_counter() - t0, 2),
                "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
