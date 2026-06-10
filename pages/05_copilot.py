"""Management Copilot — a tool-using agent over the live database.

The agent decides which tools to call (analytics functions + read-only SQL),
queries the data, and synthesises an answer. The tool-trace is shown so you can
see how it got there. Falls back to a static-context reply if no model is running.
"""

import os
import sys

# Make the modules in src/ importable (pages live one level below the root).
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import streamlit as st

import agent
import ui

st.set_page_config(page_title="Copilot", page_icon="💬", layout="wide")
ui.require_db()
ui.llm_badge()

st.title("💬 Management Copilot")
st.caption("A tool-using agent: it queries the live database to answer, and shows its "
           "work. If no model is running you get a concise data-driven reply.")

EXAMPLES = [
    "Which module should I focus on this week and why?",
    "How many high/critical customer issues does each RED module have?",
    "Which commit caused Acme Corp's worst issue?",
    "Does reviewer overload line up with customer bugs in Auth?",
]
st.caption("Try: " + " · ".join(f"“{e}”" for e in EXAMPLES))


def _render_trace(trace):
    if not trace:
        return
    with st.expander(f"🔧 How I got this — {len(trace)} tool call(s)"):
        for i, t in enumerate(trace, 1):
            args = ", ".join(f"{k}={v!r}" for k, v in (t.get("args") or {}).items())
            st.markdown(f"{i}. `{t['tool']}({args})` → {t['preview']}")


if "messages" not in st.session_state:
    st.session_state.messages = []

# Render history.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            _render_trace(msg.get("trace"))
            if msg.get("source") == "fallback":
                st.caption("⚠️ Model offline — data-driven reply (no tools).")

if prompt := st.chat_input("Ask about your engineering org…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Investigating… (querying the data)"):
            result = agent.agent_chat(prompt, st.session_state.messages[:-1])
        st.markdown(result["text"])
        _render_trace(result.get("trace"))
        if result["source"] == "fallback":
            st.caption("⚠️ Model offline — data-driven reply (no tools).")
    st.session_state.messages.append({
        "role": "assistant", "content": result["text"],
        "source": result["source"], "trace": result.get("trace", []),
    })

if st.session_state.messages and st.button("Clear conversation"):
    st.session_state.messages = []
    st.rerun()
