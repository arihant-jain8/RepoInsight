"""Management Copilot — natural-language chat grounded in the org data."""

import os
import sys

# Make the modules in src/ importable (pages live one level below the root).
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import streamlit as st

import llm_service
import ui

st.set_page_config(page_title="Copilot", page_icon="💬", layout="wide")
ui.require_db()
ui.llm_badge()

st.title("💬 Management Copilot")
st.caption("Ask about your engineering org. Answers are grounded in the current data; "
           "if no model is running you get a concise data-driven reply.")

EXAMPLES = [
    "Which module should I focus on this week?",
    "Why is Networking deteriorating?",
    "Which customer reported the most issues?",
    "Is Auth getting better or worse?",
]
st.caption("Try: " + " · ".join(f"“{e}”" for e in EXAMPLES))

if "messages" not in st.session_state:
    st.session_state.messages = []

# Render history.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("source") == "fallback":
            st.caption("⚠️ Model offline — data-driven reply.")

if prompt := st.chat_input("Ask about your engineering org…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            result = llm_service.chat(prompt, st.session_state.messages[:-1])
        st.markdown(result["text"])
        if result["source"] == "fallback":
            st.caption("⚠️ Model offline — data-driven reply.")
    st.session_state.messages.append(
        {"role": "assistant", "content": result["text"], "source": result["source"]})

if st.session_state.messages and st.button("Clear conversation"):
    st.session_state.messages = []
    st.rerun()
