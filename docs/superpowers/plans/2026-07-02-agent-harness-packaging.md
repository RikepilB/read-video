# Agent-Harness Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `read-video` installable and discoverable by Claude Code, Codex, Gemini CLI, and Copilot CLI from one source directory, with zero runtime code changes.

**Architecture:** `skill/` stays the single source of truth. A new PowerShell install script (Bash counterpart for parity) copies it to `~/.claude/skills/read-video/` (Claude Code) and `~/.agents/skills/read-video/` (the directory Codex, Gemini CLI, and Copilot CLI all read — confirmed via superpowers' own cross-runtime tool-mapping docs). `skill/SKILL.md` gets a wording pass to drop Claude-Code-specific phrasing; `skill/scripts/video.py` is untouched.

**Tech Stack:** PowerShell (primary install script), Bash (parity script), Python/pytest (existing test suite, extended with install-script tests), Markdown (docs).

## Global Constraints

- Zero changes to `skill/scripts/video.py` or the `probe`/`estimate`/`run` CLI contract — this is packaging/docs only.
- Install must never overwrite pre-existing `workspace.json`, `.env`, or `load-env.ps1` at either destination.
- PowerShell is the reference implementation and gets the automated test suite; the Bash script is parity-only, verified manually.
- No symlinks (Windows Developer Mode/admin requirement), no Agent SDK/automation integration, no `video.py` restructuring, no PyPI packaging — all explicitly out of scope per the spec's Non-goals.
- Spec: `docs/superpowers/specs/2026-07-02-agent-harness-packaging-design.md`.

---

### Task 1: Harness-neutral `SKILL.md` wording

**Files:**
- Modify: `skill/SKILL.md`
- Test: `tests/test_skill_md_wording.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing later tasks depend on programmatically — this is a standalone content fix.

- [ ] **Step 1: Write the failing test**

Create `tests/test_skill_md_wording.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_skill_md_wording.py -v`
Expected: `test_skill_md_has_no_claude_specific_phrasing` FAILS — the current file contains
`"Claude's"`, `"Claude can"`, `"Claude *can*"`, `"wants Claude to"`, and `` `Read` the frames``.
`test_skill_md_frontmatter_still_present` PASSES (frontmatter already there, unaffected by
wording).

- [ ] **Step 3: Edit `skill/SKILL.md`**

Make these four edits (exact old text → new text):

1. Frontmatter description, `"whenever the user wants Claude to"` → `"whenever the user wants the agent to"`:

```yaml
  whenever the user wants the agent to "watch", "read", "summarize", "describe", "transcribe", or
```

2. Frontmatter description, `"It extracts frames so Claude can SEE and a transcript so Claude can HEAR"` →:

```yaml
  It extracts frames so the agent can see the visual track and a transcript so it can hear the
  audio track, and ALWAYS prices the job up front so the user approves any spend or heavy step
  before it runs.
```

(This replaces the original two-line sentence; drop the now-duplicate trailing
`"job up front so the user approves any spend or heavy step before it runs."` line that followed
it in the original, since it's folded into the sentence above.)

3. Body opening, `"Claude's \`Read\` tool renders images and PDFs — **not** video."` and
   `"two things Claude *can* consume"` →:

```markdown
An agent's file-reading tool renders images and PDFs — **not** video. So "reading" a video means
converting it into two things an agent *can* consume: **frames** (JPEGs, the visual track) and a
**transcript** (text, the audio track). The catch is that this costs real tokens — frames
dominate — so this skill **estimates the whole job first** and only spends after the user (or a
$0 threshold) approves.
```

4. Step 5 heading body, `` "`Read` the frames from the workdir" `` →:

```markdown
Load the frames from the workdir `frames/` folder (in filename order) and `transcript.txt`. Then:
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_skill_md_wording.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Run full suite, then commit**

Run: `python -m pytest -q`
Expected: all pass (this task doesn't touch `video.py`, so the count should match the pre-task
baseline plus the 2 new tests).

```bash
git add skill/SKILL.md tests/test_skill_md_wording.py
git commit -m "docs: drop Claude-Code-specific phrasing from SKILL.md"
```

---

### Task 2: Install script core — copy logic

**Files:**
- Create: `scripts/install-skill.ps1`
- Modify: `tests/conftest.py` (add `requires_powershell` marker, matching the existing
  `requires_ffmpeg` pattern)
- Test: `tests/test_install_skill.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `Install-SkillTo` PowerShell function — takes `-Label <string> -TargetRoot <string>`,
  creates `<TargetRoot>/read-video`, copies `skill/*` into it via `Copy-Item -Recurse -Force`
  (never deletes/overwrites files at the destination that aren't part of the source — this is
  what keeps a pre-existing `.env`/`workspace.json`/`load-env.ps1` untouched, since the repo's
  `skill/` directory never contains those filenames), prints `RESULT <label> copy OK` or
  `RESULT <label> copy FAILED <message>` to stdout, and returns the destination path string (or
  `$null` on failure). Script accepts `-ClaudeSkillsRoot` / `-AgentsSkillsRoot` params (defaulting
  to the real install locations) so tests can point them at `tmp_path` instead. Task 3 adds
  verification on top of this; this task's script is runnable standalone and already installs to
  both targets even before Task 3 lands (verification is additive, not blocking).

- [ ] **Step 1: Add the `requires_powershell` marker to `tests/conftest.py`**

Add near the existing `HAVE_FFMPEG`/`requires_ffmpeg` lines (after line 13):

```python
HAVE_POWERSHELL = shutil.which("powershell") is not None or shutil.which("pwsh") is not None
requires_powershell = pytest.mark.skipif(not HAVE_POWERSHELL, reason="powershell/pwsh not on PATH")


def powershell_exe() -> str:
    return shutil.which("pwsh") or shutil.which("powershell")
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_install_skill.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_install_skill.py -v`
Expected: FAIL — `scripts/install-skill.ps1` does not exist yet (file-not-found from the
subprocess call, surfaced as a non-zero/error result on every test).

- [ ] **Step 4: Write `scripts/install-skill.ps1`**

```powershell
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ClaudeSkillsRoot = (Join-Path $env:USERPROFILE ".claude\skills"),
    [string]$AgentsSkillsRoot = (Join-Path $env:USERPROFILE ".agents\skills")
)

$SkillSource = Join-Path $RepoRoot "skill"

function Install-SkillTo {
    param(
        [string]$Label,
        [string]$TargetRoot
    )

    $Dest = Join-Path $TargetRoot "read-video"

    try {
        if (-not (Test-Path $TargetRoot)) {
            New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
        }
        if (-not (Test-Path $Dest)) {
            New-Item -ItemType Directory -Path $Dest -Force | Out-Null
        }

        Copy-Item -Path (Join-Path $SkillSource "*") -Destination $Dest -Recurse -Force

        Write-Output "RESULT $Label copy OK"
        return $Dest
    } catch {
        Write-Output "RESULT $Label copy FAILED $($_.Exception.Message)"
        return $null
    }
}

$targets = @(
    @{ Label = "claude"; Root = $ClaudeSkillsRoot },
    @{ Label = "agents"; Root = $AgentsSkillsRoot }
)

$anySucceeded = $false

foreach ($t in $targets) {
    $dest = Install-SkillTo -Label $t.Label -TargetRoot $t.Root
    if ($dest) {
        $anySucceeded = $true
    }
}

if (-not $anySucceeded) {
    Write-Output "SUMMARY all targets FAILED"
    exit 1
} else {
    Write-Output "SUMMARY install complete"
    exit 0
}
```

Note: `Copy-Item -Recurse -Force` overlays `skill/*` onto the destination — it creates/overwrites
files that exist in the source, but never deletes or touches destination files that aren't present
in the source. Since the repo's `skill/` directory never contains `workspace.json`, `.env`, or
`load-env.ps1` (they're gitignored, destination-only files), this copy mechanism inherently leaves
them untouched — no explicit exclude list needed.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_install_skill.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 6: Run full suite, then commit**

Run: `python -m pytest -q`
Expected: all pass (baseline + 2 from Task 1 + 4 new).

```bash
git add scripts/install-skill.ps1 tests/conftest.py tests/test_install_skill.py
git commit -m "feat: install-skill.ps1 copies skill/ to both harness install roots"
```

---

### Task 3: Install script verification + exit-code contract

**Files:**
- Modify: `scripts/install-skill.ps1`
- Modify: `tests/test_install_skill.py` (add verification-focused tests)

**Interfaces:**
- Consumes: `Install-SkillTo` from Task 2 (returns destination path or `$null`), the
  `RESULT <label> copy OK/FAILED` output convention, the `-ClaudeSkillsRoot`/`-AgentsSkillsRoot`
  params.
- Produces: `Test-Frontmatter -Label <string> -Dest <string>` and
  `Test-CliRuns -Label <string> -Dest <string>` functions, each printing
  `RESULT <label> verify:frontmatter OK/FAILED <message>` or
  `RESULT <label> verify:cli OK/FAILED <message>`. Final script behavior: runs both verifications
  against every target whose copy succeeded, always prints a final `SUMMARY ...` line, exits 0
  unless every target's copy step failed.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_install_skill.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_install_skill.py -k verification_ok -v`
Expected: FAIL — no `verify:frontmatter`/`verify:cli` output exists yet (Task 2's script only
prints copy results).

- [ ] **Step 3: Add verification functions to `scripts/install-skill.ps1`**

Insert after the `Install-SkillTo` function definition (before the `$targets = @(...)` line):

```powershell
function Test-Frontmatter {
    param(
        [string]$Label,
        [string]$Dest
    )

    $SkillMdPath = Join-Path $Dest "SKILL.md"
    try {
        if (-not (Test-Path $SkillMdPath)) {
            throw "SKILL.md not found"
        }
        $content = Get-Content $SkillMdPath -Raw
        if ($content -notmatch '(?s)^---\s*(.*?)\s*---') {
            throw "no frontmatter block found"
        }
        $fm = $Matches[1]
        if ($fm -notmatch 'name:\s*\S+') { throw "missing name key" }
        if ($fm -notmatch 'description:') { throw "missing description key" }
        Write-Output "RESULT $Label verify:frontmatter OK"
    } catch {
        Write-Output "RESULT $Label verify:frontmatter FAILED $($_.Exception.Message)"
    }
}

function Test-CliRuns {
    param(
        [string]$Label,
        [string]$Dest
    )

    $ScriptPath = Join-Path $Dest "scripts\video.py"
    try {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { throw "python not found on PATH" }
        & python $ScriptPath probe --help *> $null
        if ($LASTEXITCODE -ne 0) { throw "exit code $LASTEXITCODE" }
        Write-Output "RESULT $Label verify:cli OK"
    } catch {
        Write-Output "RESULT $Label verify:cli FAILED $($_.Exception.Message)"
    }
}
```

Then replace the `foreach ($t in $targets) { ... }` loop body to also call the two new functions:

```powershell
foreach ($t in $targets) {
    $dest = Install-SkillTo -Label $t.Label -TargetRoot $t.Root
    if ($dest) {
        $anySucceeded = $true
        Test-Frontmatter -Label $t.Label -Dest $dest
        Test-CliRuns -Label $t.Label -Dest $dest
    }
}
```

(The `if (-not $anySucceeded) { ... } else { ... }` block after the loop is unchanged from Task 2.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_install_skill.py -v`
Expected: all 6 tests in the file PASS.

- [ ] **Step 5: Run full suite, then commit**

Run: `python -m pytest -q`
Expected: all pass.

```bash
git add scripts/install-skill.ps1 tests/test_install_skill.py
git commit -m "feat: install-skill.ps1 verifies frontmatter and CLI at each install target"
```

---

### Task 4: Bash parity script

**Files:**
- Create: `scripts/install-skill.sh`

**Interfaces:**
- Consumes: nothing programmatically (independent file); mirrors `install-skill.ps1`'s behavior
  and `RESULT`/`SUMMARY` output convention from Tasks 2-3 for consistency.
- Produces: nothing later tasks consume programmatically. No automated pytest coverage for this
  file per the spec ("PowerShell is the reference implementation and gets tested first") — this
  task's verification step is a manual run, recorded in the task report.

- [ ] **Step 1: Write `scripts/install-skill.sh`**

```bash
#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(dirname "$SCRIPT_DIR")}"
SKILL_SOURCE="$REPO_ROOT/skill"

CLAUDE_SKILLS_ROOT="${CLAUDE_SKILLS_ROOT:-$HOME/.claude/skills}"
AGENTS_SKILLS_ROOT="${AGENTS_SKILLS_ROOT:-$HOME/.agents/skills}"

install_to() {
  local label="$1" dest="$2"

  if ! mkdir -p "$dest"; then
    echo "RESULT $label copy FAILED mkdir $dest"
    return 1
  fi
  if cp -r "$SKILL_SOURCE"/. "$dest"/; then
    echo "RESULT $label copy OK"
    return 0
  fi
  echo "RESULT $label copy FAILED cp"
  return 1
}

verify_frontmatter() {
  local label="$1" dest="$2" skill_md="$2/SKILL.md"

  if [ ! -f "$skill_md" ]; then
    echo "RESULT $label verify:frontmatter FAILED missing SKILL.md"
    return 1
  fi
  if grep -q '^name:' "$skill_md" && grep -q '^description:' "$skill_md"; then
    echo "RESULT $label verify:frontmatter OK"
    return 0
  fi
  echo "RESULT $label verify:frontmatter FAILED missing name/description"
  return 1
}

verify_cli() {
  local label="$1" dest="$2"

  if ! command -v python >/dev/null 2>&1; then
    echo "RESULT $label verify:cli FAILED python not on PATH"
    return 1
  fi
  if python "$dest/scripts/video.py" probe --help >/dev/null 2>&1; then
    echo "RESULT $label verify:cli OK"
    return 0
  fi
  echo "RESULT $label verify:cli FAILED non-zero exit"
  return 1
}

any_ok=0

for pair in "claude $CLAUDE_SKILLS_ROOT" "agents $AGENTS_SKILLS_ROOT"; do
  label="${pair%% *}"
  root="${pair#* }"
  dest="$root/read-video"
  if install_to "$label" "$dest"; then
    any_ok=1
    verify_frontmatter "$label" "$dest" || true
    verify_cli "$label" "$dest" || true
  fi
done

if [ "$any_ok" -eq 0 ]; then
  echo "SUMMARY all targets FAILED"
  exit 1
fi
echo "SUMMARY install complete"
exit 0
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/install-skill.sh
```

- [ ] **Step 3: Manual verification run**

Run against temp directories (do not point at real install locations yet — that's Task 7):

```bash
CLAUDE_SKILLS_ROOT=/tmp/harness-test/claude_skills AGENTS_SKILLS_ROOT=/tmp/harness-test/agents_skills bash scripts/install-skill.sh
```

Expected output: `RESULT claude copy OK`, `RESULT claude verify:frontmatter OK`,
`RESULT claude verify:cli OK` (and the same three lines with `agents`), then
`SUMMARY install complete`. Exit code 0 (`echo $?`).

Verify files landed: `ls /tmp/harness-test/claude_skills/read-video/SKILL.md
/tmp/harness-test/agents_skills/read-video/scripts/video.py` — both should exist.

Clean up: `rm -rf /tmp/harness-test`

- [ ] **Step 4: Commit**

```bash
git add scripts/install-skill.sh
git commit -m "feat: install-skill.sh (Bash parity for install-skill.ps1)"
```

---

### Task 5: `docs/harness-support.md`

**Files:**
- Create: `docs/harness-support.md`

**Interfaces:**
- Consumes: the finished behavior of `install-skill.ps1`/`install-skill.sh` from Tasks 2-4 (this
  doc describes what they do — write it last so it can't drift from the actual implementation).
- Produces: a doc Task 6's README section links to.

- [ ] **Step 1: Write `docs/harness-support.md`**

```markdown
# Multi-Harness Support

`read-video`'s engine (`skill/scripts/video.py`) is a plain stdlib Python CLI with no Claude Code
dependency — anything that can run a shell command and read a file can drive it via
`probe → estimate → [gate] → run`. This doc covers how the *skill* (the `SKILL.md` prompt that
tells an agent how to drive that CLI) gets discovered by different agent harnesses.

## The two install locations

| Harness | Install root | Notes |
|---|---|---|
| Claude Code | `~/.claude/skills/read-video/` | Claude Code does **not** read `~/.agents/skills/`. |
| Codex | `~/.agents/skills/read-video/` | Shared cross-runtime directory. |
| Gemini CLI | `~/.agents/skills/read-video/` | Same shared directory as Codex/Copilot CLI. |
| Copilot CLI | `~/.agents/skills/read-video/` | Same shared directory as Codex/Gemini CLI. |

Codex, Gemini CLI, and Copilot CLI all read **the same** `~/.agents/skills/` directory — installing
there once covers all three. Claude Code needs its own separate copy at `~/.claude/skills/`.

## Why no per-harness adapter exists

All four harnesses use the identical skill format: a subdirectory containing a `SKILL.md` file with
`name` and `description` YAML frontmatter, plus supporting files. There's no prompt-syntax or
schema difference to translate between them — `read-video`'s `skill/` directory is valid, as-is,
at both install roots. The only harness-specific work was removing Claude-Code-specific wording
from `SKILL.md`'s prose (e.g. naming Claude Code's `Read` tool specifically) so the same file reads
naturally regardless of which agent is following it.

## Installing

From the repo root:

```powershell
# Windows / PowerShell (primary)
.\scripts\install-skill.ps1
```

```bash
# macOS / Linux / Git Bash (parity)
bash scripts/install-skill.sh
```

Both scripts copy `skill/` to both install roots and print a per-target `RESULT` line for the copy
step and two verification checks (frontmatter parses, `video.py --help` runs), ending with a
`SUMMARY` line. Exit code is non-zero only if **every** target's copy failed — a machine with only
Claude Code installed still succeeds overall (the `~/.agents/skills/` copy just sits there ready
for whichever of Codex/Gemini CLI/Copilot CLI gets installed later).

Override the install roots (used by the test suite, or if you keep skills somewhere non-default):

```powershell
.\scripts\install-skill.ps1 -ClaudeSkillsRoot "D:\custom\claude\skills" -AgentsSkillsRoot "D:\custom\agents\skills"
```

```bash
CLAUDE_SKILLS_ROOT=/custom/claude/skills AGENTS_SKILLS_ROOT=/custom/agents/skills bash scripts/install-skill.sh
```

## Re-syncing after edits

There is no live-sync watcher. After editing anything under `skill/`, re-run the install script to
push the change to both installed copies. Local config files (`workspace.json`, `.env`,
`load-env.ps1`) at either destination are never touched by the install — the repo's `skill/`
directory never contains those filenames (they're gitignored, generated at the destination only),
so a plain overlay copy leaves them alone automatically.

## Out of scope

Agent SDK / custom-bot integration and non-interactive automation (cron, n8n, etc.) are different
integration modes than "another CLI agent reads a SKILL.md" and aren't covered by this doc or the
install scripts — see `docs/superpowers/specs/2026-07-02-agent-harness-packaging-design.md` for the
full scope decision.
```

- [ ] **Step 2: Commit**

```bash
git add docs/harness-support.md
git commit -m "docs: add harness-support.md explaining multi-harness install"
```

---

### Task 6: README update

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `docs/harness-support.md` from Task 5 (links to it).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Insert a new install subsection**

In `README.md`, find this existing text (the end of the `## Install` section's item 4):

```markdown
### 4. (Optional) workspace
Copy `skill/workspace.example.json` to `skill/workspace.json` (gitignored) and set `inbox_dir` / `out_dir`
to your folders. With it, you can pass **bare filenames** and the skill auto-saves notes.

## Quickstart (driving the engine directly)
```

Replace it with (adds a new item 5 between the workspace section and Quickstart):

```markdown
### 4. (Optional) workspace
Copy `skill/workspace.example.json` to `skill/workspace.json` (gitignored) and set `inbox_dir` / `out_dir`
to your folders. With it, you can pass **bare filenames** and the skill auto-saves notes.

### 5. (Optional) other agent harnesses
`read-video` also works with Codex, Gemini CLI, and Copilot CLI — they share one install
directory (`~/.agents/skills/`) with the identical `SKILL.md` format Claude Code uses, so no
per-harness adapter is needed. Run the install script instead of the manual copy above to set up
all of them at once:

```powershell
# Windows / PowerShell
.\scripts\install-skill.ps1
```
```bash
# macOS / Linux / Git Bash
bash scripts/install-skill.sh
```

See [docs/harness-support.md](docs/harness-support.md) for details.

## Quickstart (driving the engine directly)
```

- [ ] **Step 2: Verify the doc renders sensibly**

Read the edited `README.md` section back and confirm the heading numbering and Markdown code
fences are well-formed (no unclosed fences, no duplicate `## Quickstart` heading).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document multi-harness install in README"
```

---

### Task 7: Real install, manual verification, final full-suite run

**Files:**
- No new repo files. Live install targets: `C:\Users\a2021\.claude\skills\read-video\` and
  `C:\Users\a2021\.agents\skills\read-video\` (outside the repo, not tracked by git).

**Interfaces:**
- Consumes: the finished `scripts/install-skill.ps1` from Tasks 2-3.
- Produces: the actual working multi-harness install on this machine — the deliverable the whole
  plan exists for.

- [ ] **Step 1: Run the full test suite one more time**

Run: `python -m pytest -v`
Expected: all PASS, 0 unexpected skips (PowerShell is present on this machine, so the
`requires_powershell`-marked tests should run, not skip).

- [ ] **Step 2: Run the real install**

From the repo root:

```powershell
.\scripts\install-skill.ps1
```

Expected output: `RESULT claude copy OK`, `RESULT claude verify:frontmatter OK`,
`RESULT claude verify:cli OK`, `RESULT agents copy OK`, `RESULT agents verify:frontmatter OK`,
`RESULT agents verify:cli OK`, `SUMMARY install complete`. Exit code 0.

- [ ] **Step 3: Verify the live installs by hand**

```powershell
Get-Content "$env:USERPROFILE\.claude\skills\read-video\SKILL.md" -TotalCount 5
Get-Content "$env:USERPROFILE\.agents\skills\read-video\SKILL.md" -TotalCount 5
python "$env:USERPROFILE\.claude\skills\read-video\scripts\video.py" probe --help
python "$env:USERPROFILE\.agents\skills\read-video\scripts\video.py" probe --help
```

Expected: both `SKILL.md` files show the same frontmatter (`name: read-video`), both `probe --help`
invocations exit 0 with usage text.

- [ ] **Step 4: Verify pre-existing Claude Code local config survived**

```powershell
Get-Item "$env:USERPROFILE\.claude\skills\read-video\.env" | Select-Object LastWriteTime
Get-Item "$env:USERPROFILE\.claude\skills\read-video\workspace.json" | Select-Object LastWriteTime
Get-Item "$env:USERPROFILE\.claude\skills\read-video\load-env.ps1" | Select-Object LastWriteTime
```

Expected: `LastWriteTime` on all three predates this task's install run (they were not touched).

- [ ] **Step 5: Commit any final documentation touch-ups found during manual verification**

If Steps 2-4 surface no issues, there's nothing new to commit — the repo-side work already landed
in Tasks 1-6. If something needs a fix, make the smallest correction, re-run the affected test(s),
and commit:

```bash
git add -A
git commit -m "fix: <describe the specific issue found during manual install verification>"
```

(Only run this commit if Step 5 actually found something to fix — otherwise this task ends at
Step 4.)
