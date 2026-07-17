"""Agent/command docs that shell out to video.py must stay in sync with its cost/consent gate
fields -- a doc that only checks needs_install would trip an unhandled PermissionError on the
first video that needs a model download."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DOCS = [
    REPO / ".claude" / "agents" / "ig-analyze-subagent.md",
    REPO / ".codex" / "agents" / "ig-analyze-subagent.toml",
    REPO / ".claude" / "commands" / "read-audio.md",
]


def test_agent_docs_mention_needs_model_download():
    missing = [d for d in DOCS if "needs_model_download" not in d.read_text(encoding="utf-8")]
    assert not missing, f"docs missing needs_model_download handling: {missing}"
