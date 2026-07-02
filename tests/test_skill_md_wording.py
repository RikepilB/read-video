"""SKILL.md must not name Claude Code's tools specifically -- other harnesses read this file too."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_MD = REPO / "skill" / "SKILL.md"

BANNED_PHRASES = [
    "Claude's",
    "Claude can",
    "Claude *can*",
    "wants Claude to",
    "`Read` the frames",
]


def test_skill_md_has_no_claude_specific_phrasing():
    content = SKILL_MD.read_text(encoding="utf-8")
    found = [p for p in BANNED_PHRASES if p in content]
    assert not found, f"Claude-Code-specific phrasing still present: {found}"


def test_skill_md_frontmatter_still_present():
    content = SKILL_MD.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    frontmatter_end = content.index("\n---\n", 4)
    frontmatter = content[4:frontmatter_end]
    assert "name:" in frontmatter
    assert "description:" in frontmatter
