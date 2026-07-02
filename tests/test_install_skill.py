"""install-skill.ps1 copies skill/ to both harness install roots without touching local config."""
import subprocess
from pathlib import Path

import pytest

from conftest import requires_powershell, powershell_exe

REPO = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = REPO / "scripts" / "install-skill.ps1"


def _run_install(claude_root: Path, agents_root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            powershell_exe(), "-NoProfile", "-NonInteractive", "-File", str(INSTALL_SCRIPT),
            "-ClaudeSkillsRoot", str(claude_root),
            "-AgentsSkillsRoot", str(agents_root),
        ],
        capture_output=True, text=True, timeout=60,
    )


@requires_powershell
def test_install_copies_to_both_targets(tmp_path):
    claude_root = tmp_path / "claude_skills"
    agents_root = tmp_path / "agents_skills"

    result = _run_install(claude_root, agents_root)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (claude_root / "read-video" / "SKILL.md").exists()
    assert (agents_root / "read-video" / "SKILL.md").exists()
    assert (claude_root / "read-video" / "scripts" / "video.py").exists()
    assert (agents_root / "read-video" / "scripts" / "video.py").exists()


@requires_powershell
def test_install_reports_copy_ok_for_both_targets(tmp_path):
    claude_root = tmp_path / "claude_skills"
    agents_root = tmp_path / "agents_skills"

    result = _run_install(claude_root, agents_root)

    assert "RESULT claude copy OK" in result.stdout
    assert "RESULT agents copy OK" in result.stdout


@requires_powershell
def test_install_creates_missing_parent_dir(tmp_path):
    claude_root = tmp_path / "does_not_exist_yet" / "claude_skills"
    agents_root = tmp_path / "also_missing" / "agents_skills"

    result = _run_install(claude_root, agents_root)

    assert result.returncode == 0
    assert (claude_root / "read-video" / "SKILL.md").exists()
    assert (agents_root / "read-video" / "SKILL.md").exists()


@requires_powershell
def test_install_preserves_existing_local_config(tmp_path):
    claude_root = tmp_path / "claude_skills"
    dest = claude_root / "read-video"
    dest.mkdir(parents=True)
    (dest / ".env").write_text("SECRET_KEY=do-not-touch", encoding="utf-8")
    (dest / "workspace.json").write_text('{"inbox_dir": "keep-me"}', encoding="utf-8")

    agents_root = tmp_path / "agents_skills"

    result = _run_install(claude_root, agents_root)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (dest / ".env").read_text(encoding="utf-8") == "SECRET_KEY=do-not-touch"
    assert (dest / "workspace.json").read_text(encoding="utf-8") == '{"inbox_dir": "keep-me"}'


@requires_powershell
def test_install_reports_verification_ok_for_both_targets(tmp_path):
    claude_root = tmp_path / "claude_skills"
    agents_root = tmp_path / "agents_skills"

    result = _run_install(claude_root, agents_root)

    assert "RESULT claude verify:frontmatter OK" in result.stdout
    assert "RESULT agents verify:frontmatter OK" in result.stdout
    assert "RESULT claude verify:cli OK" in result.stdout
    assert "RESULT agents verify:cli OK" in result.stdout


@requires_powershell
def test_install_prints_summary_line(tmp_path):
    claude_root = tmp_path / "claude_skills"
    agents_root = tmp_path / "agents_skills"

    result = _run_install(claude_root, agents_root)

    assert "SUMMARY install complete" in result.stdout
    assert result.returncode == 0
