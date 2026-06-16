"""Knowledge base: static domain reference the copilot/reports draw on.

One source of truth (the Markdown files in knowledge/) for the risk model, metric
catalog, glossary, and org structure. The tool-using agent fetches a topic on demand
via the get_reference tool (agent.py); the no-tool prompts (copilot.txt, report.txt)
inject bundled topics at build time (llm_service.py).

The Markdown is brace-free on purpose: copilot.txt/report.txt are filled with
str.format(), so a literal brace in the injected text would break formatting.
"""

import os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge")

# topic -> one-line description (drives both the agent tool schema and the prompt text)
TOPICS = {
    "risk_model": "how risk_score is computed (the 0.50/0.30/0.20 components and bands)",
    "metric_catalog": "the type-aware quality metrics with good/bad thresholds and weights",
    "glossary": "operational metrics, enums, and interpretation rules (e.g. quality_trend sign)",
    "org_structure": "the vertical to account to project to module hierarchy and real entity names",
}


def list_topics() -> list[tuple[str, str]]:
    """[(topic, description)] for the agent tool + prompt guidance."""
    return list(TOPICS.items())


def read(topic: str) -> str:
    """Return one knowledge file's text, or an error string naming the valid topics."""
    topic = (topic or "").strip().lower()
    if topic not in TOPICS:
        return f"Unknown topic '{topic}'. Valid topics: {', '.join(TOPICS)}."
    with open(os.path.join(_DIR, f"{topic}.md"), encoding="utf-8") as f:
        return f.read().strip()


def bundle(*topics: str) -> str:
    """Concatenate the given topics (defaults to all) for injection into a prompt."""
    names = topics or tuple(TOPICS)
    return "\n\n---\n\n".join(read(t) for t in names)
