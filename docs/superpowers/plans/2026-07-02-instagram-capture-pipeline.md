# Instagram Capture Pipeline (Sub-project #1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture reel URLs from the user's Instagram "courses" saved-collection into `read-video`'s existing `inbox_dir/urls.md` queue, via a scoped browser-automation subagent, with unsave-as-dedup and a mandatory dry-run mode.

**Architecture:** An orchestrator slash command (`.claude/commands/instagram-capture.md`) parses `N`/`--dry-run`, resolves `inbox_dir` from `read-video`'s `workspace.json`, and dispatches a tool-scoped custom subagent (`.claude/agents/instagram-capture-subagent.md`, restricted to Chrome-automation tools + `Bash` + `Read`) that drives the actual browsing/unsaving loop. A small deterministic Python helper (`scripts/instagram_capture_helper.py`) owns the fragile parts — shortcode extraction, canonical URL building, dedup checking, and confirmed file append — so the subagent never free-hand-edits `urls.md` itself; it only shells out to the helper's `process` command and interprets the JSON result.

**Tech Stack:** Python 3.12 stdlib (helper script, matches `read-video`'s own no-dependency convention), pytest (helper script tests only), Claude Code custom commands/agents (markdown + YAML frontmatter), `claude-in-chrome` MCP tools (browser automation).

## Global Constraints

- **Public accounts/content only** — the "courses" collection is user-confirmed public-only; no private-content handling anywhere in this feature.
- **Append-before-unsave, always** — a reel must never be unsaved unless its URL is confirmed written to `urls.md` first (or was already confirmed present in a prior run — the dedup-recovery path).
- **Claude-Code-only** — this feature depends on `claude-in-chrome` MCP tools. It does not extend to Codex/Gemini CLI/Copilot CLI (unlike `read-video`'s core, which is multi-harness per the prior thread).
- **Human-paced interaction** — deliberate delays between navigate/scroll/click actions in the subagent's loop; no rapid-fire automation.
- **Reuses `read-video`'s existing queue file** (`inbox_dir/urls.md`, resolved from `workspace.json`) — no new state/database file.
- **No automatic hand-off to `read-video` processing** — this feature only ever appends to `urls.md`. It never invokes `video.py` or triggers transcription.
- **Dry-run before any live run; first live run watched manually by the user** — non-negotiable per spec's Testing section and the user's own standing directive to pause before anything irreversible/detrimental (unsaving a real reel qualifies).

---

### Task 1: Deterministic capture helper (shortcode extraction, dedup, confirmed append)

**Files:**
- Create: `scripts/instagram_capture_helper.py`
- Test: `tests/test_instagram_capture_helper.py`
- Modify: `tests/conftest.py` (add `scripts/` to `sys.path` alongside the existing `skill/scripts/` entry)

**Interfaces:**
- Produces: `extract_shortcode(url_or_code: str) -> str` (raises `ValueError` on unrecognized input), `canonical_url(shortcode: str) -> str`, `is_duplicate(url: str, urls_md_path: Path) -> bool`, `append_and_confirm(url: str, urls_md_path: Path) -> bool`, `process(url_or_code: str, urls_md_path: Path) -> dict` (returns `{"url": str, "duplicate": bool, "appended": bool, "safe_to_unsave": bool}`), and a CLI entry point `python scripts/instagram_capture_helper.py process <url_or_code> <urls_md_path>` printing that dict as JSON to stdout (exit 0) or `{"error": str}` (exit 1) on invalid input. Task 2's subagent definition consumes this CLI directly via `Bash`.

- [ ] **Step 1: Add the new sys.path entry to conftest.py**

Read `tests/conftest.py` first (it currently has `sys.path.insert(0, str(REPO / "skill" / "scripts"))` near the top). Add one more line directly below it:

```python
sys.path.insert(0, str(REPO / "scripts"))
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_instagram_capture_helper.py`:

```python
"""Tests for the Instagram capture helper — pure logic only, no browser/network."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from instagram_capture_helper import (
    append_and_confirm,
    canonical_url,
    extract_shortcode,
    is_duplicate,
    process,
)

REPO = Path(__file__).resolve().parent.parent
HELPER_SCRIPT = REPO / "scripts" / "instagram_capture_helper.py"


def test_extract_shortcode_from_reel_url():
    assert extract_shortcode("https://www.instagram.com/reel/Cx1AbC2DeFg/") == "Cx1AbC2DeFg"


def test_extract_shortcode_from_reel_url_with_query_params():
    url = "https://www.instagram.com/reel/Cx1AbC2DeFg/?igsh=abc123"
    assert extract_shortcode(url) == "Cx1AbC2DeFg"


def test_extract_shortcode_from_post_url():
    assert extract_shortcode("https://www.instagram.com/p/Cx1AbC2DeFg/") == "Cx1AbC2DeFg"


def test_extract_shortcode_from_bare_shortcode():
    assert extract_shortcode("Cx1AbC2DeFg") == "Cx1AbC2DeFg"


def test_extract_shortcode_invalid_raises():
    with pytest.raises(ValueError):
        extract_shortcode("https://example.com/not-instagram")


def test_canonical_url_format():
    assert canonical_url("Cx1AbC2DeFg") == "https://www.instagram.com/reel/Cx1AbC2DeFg/"


def test_is_duplicate_true_when_present(tmp_path):
    urls_md = tmp_path / "urls.md"
    urls_md.write_text("https://www.instagram.com/reel/Cx1AbC2DeFg/\n", encoding="utf-8")
    assert is_duplicate("https://www.instagram.com/reel/Cx1AbC2DeFg/", urls_md) is True


def test_is_duplicate_false_when_absent(tmp_path):
    urls_md = tmp_path / "urls.md"
    urls_md.write_text("https://www.instagram.com/reel/Other0000Ab/\n", encoding="utf-8")
    assert is_duplicate("https://www.instagram.com/reel/Cx1AbC2DeFg/", urls_md) is False


def test_is_duplicate_false_when_file_missing(tmp_path):
    urls_md = tmp_path / "does_not_exist.md"
    assert is_duplicate("https://www.instagram.com/reel/Cx1AbC2DeFg/", urls_md) is False


def test_append_and_confirm_creates_file_and_parent_dirs(tmp_path):
    urls_md = tmp_path / "nested" / "urls.md"
    ok = append_and_confirm("https://www.instagram.com/reel/Cx1AbC2DeFg/", urls_md)
    assert ok is True
    assert "https://www.instagram.com/reel/Cx1AbC2DeFg/" in urls_md.read_text(encoding="utf-8")


def test_append_and_confirm_appends_without_truncating_existing(tmp_path):
    urls_md = tmp_path / "urls.md"
    urls_md.write_text("https://www.instagram.com/reel/Existing0001/\n", encoding="utf-8")
    append_and_confirm("https://www.instagram.com/reel/Cx1AbC2DeFg/", urls_md)
    content = urls_md.read_text(encoding="utf-8")
    assert "Existing0001" in content
    assert "Cx1AbC2DeFg" in content


def test_process_new_url_appends(tmp_path):
    urls_md = tmp_path / "urls.md"
    result = process("Cx1AbC2DeFg", urls_md)
    assert result == {
        "url": "https://www.instagram.com/reel/Cx1AbC2DeFg/",
        "duplicate": False,
        "appended": True,
        "safe_to_unsave": True,
    }


def test_process_duplicate_url_skips_append_but_safe_to_unsave(tmp_path):
    urls_md = tmp_path / "urls.md"
    urls_md.write_text("https://www.instagram.com/reel/Cx1AbC2DeFg/\n", encoding="utf-8")
    result = process("Cx1AbC2DeFg", urls_md)
    assert result == {
        "url": "https://www.instagram.com/reel/Cx1AbC2DeFg/",
        "duplicate": True,
        "appended": False,
        "safe_to_unsave": True,
    }


def test_process_invalid_input_raises(tmp_path):
    urls_md = tmp_path / "urls.md"
    with pytest.raises(ValueError):
        process("https://example.com/not-instagram", urls_md)


def test_cli_process_prints_json_for_new_url(tmp_path):
    urls_md = tmp_path / "urls.md"
    result = subprocess.run(
        [sys.executable, str(HELPER_SCRIPT), "process", "Cx1AbC2DeFg", str(urls_md)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["appended"] is True
    assert payload["url"] == "https://www.instagram.com/reel/Cx1AbC2DeFg/"


def test_cli_process_errors_on_invalid_input(tmp_path):
    urls_md = tmp_path / "urls.md"
    result = subprocess.run(
        [sys.executable, str(HELPER_SCRIPT), "process", "https://example.com/nope", str(urls_md)],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert "error" in payload
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_instagram_capture_helper.py -v`
Expected: `ModuleNotFoundError: No module named 'instagram_capture_helper'` (the module doesn't exist yet)

- [ ] **Step 4: Write the implementation**

Create `scripts/instagram_capture_helper.py`:

```python
"""Deterministic helper for the Instagram capture pipeline: shortcode extraction,
canonical URL building, dedup checking, and confirmed append to read-video's
inbox_dir/urls.md queue. No network, no browser — the capture subagent shells
out to this for every reel so the fragile parsing/append logic never depends
on freeform agent judgment."""
import argparse
import json
import re
import sys
from pathlib import Path

_URL_RE = re.compile(r"instagram\.com/(?:reel|p|tv)/([A-Za-z0-9_-]+)")
_SHORTCODE_RE = re.compile(r"^[A-Za-z0-9_-]{5,15}$")


def extract_shortcode(url_or_code: str) -> str:
    s = url_or_code.strip()
    m = _URL_RE.search(s)
    if m:
        return m.group(1)
    if _SHORTCODE_RE.match(s):
        return s
    raise ValueError(f"not a recognizable Instagram reel/post URL or shortcode: {url_or_code!r}")


def canonical_url(shortcode: str) -> str:
    return f"https://www.instagram.com/reel/{shortcode}/"


def is_duplicate(url: str, urls_md_path: Path) -> bool:
    if not urls_md_path.exists():
        return False
    lines = urls_md_path.read_text(encoding="utf-8").splitlines()
    return url in (line.strip() for line in lines)


def append_and_confirm(url: str, urls_md_path: Path) -> bool:
    urls_md_path.parent.mkdir(parents=True, exist_ok=True)
    with urls_md_path.open("a", encoding="utf-8") as f:
        f.write(url + "\n")
    lines = urls_md_path.read_text(encoding="utf-8").splitlines()
    return url in (line.strip() for line in lines)


def process(url_or_code: str, urls_md_path: Path) -> dict:
    url = canonical_url(extract_shortcode(url_or_code))
    if is_duplicate(url, urls_md_path):
        return {"url": url, "duplicate": True, "appended": False, "safe_to_unsave": True}
    appended = append_and_confirm(url, urls_md_path)
    return {"url": url, "duplicate": False, "appended": appended, "safe_to_unsave": appended}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="instagram_capture_helper")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("process", help="canonicalize, dedup-check, and append a reel URL")
    p.add_argument("url_or_code")
    p.add_argument("urls_md_path")
    args = parser.parse_args(argv)

    if args.command == "process":
        try:
            result = process(args.url_or_code, Path(args.urls_md_path))
        except ValueError as e:
            print(json.dumps({"error": str(e)}))
            return 1
        print(json.dumps(result))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_instagram_capture_helper.py -v`
Expected: 16 passed

- [ ] **Step 6: Run the full suite to confirm no regressions**

Run: `python -m pytest -q`
Expected: all tests pass (55 pre-existing + 16 new = 71)

- [ ] **Step 7: Commit**

```bash
git add scripts/instagram_capture_helper.py tests/test_instagram_capture_helper.py tests/conftest.py
git commit -m "feat: deterministic helper for Instagram capture (shortcode, dedup, confirmed append)"
```

---

### Task 2: Capture subagent definition (tool-scoped)

**Files:**
- Create: `.claude/agents/instagram-capture-subagent.md`

**Interfaces:**
- Consumes: `scripts/instagram_capture_helper.py`'s `process` CLI command from Task 1 (`python scripts/instagram_capture_helper.py process <url_or_code> <urls_md_path>` → JSON with `url`/`duplicate`/`appended`/`safe_to_unsave` keys, or `{"error": ...}` with exit 1).
- Produces: a custom subagent named `instagram-capture-subagent`, invocable via the Agent tool, that Task 3's orchestrator command dispatches with `N` and `urls_md_path` (and a `dry_run` flag) in its prompt. Returns a final message reporting `{captured: [urls...], count: N}` in dry-run mode (`captured` = candidates it *would* process, nothing written) or after a live run (`captured` = URLs actually appended, `count` = len(captured)).

- [ ] **Step 1: Write the subagent definition**

Create `.claude/agents/instagram-capture-subagent.md`:

```markdown
---
name: instagram-capture-subagent
description: Scoped browser-automation subagent that captures reel URLs from the user's Instagram "courses" saved-collection into read-video's urls.md queue, unsaving each as its dedup marker. Dispatched only by the /instagram-capture orchestrator command — never invoke this directly for anything outside that workflow.
tools: Read, Bash, mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__read_page, mcp__claude-in-chrome__find
---

You capture reel URLs from a specific Instagram saved-collection called "courses" into a local
queue file, unsaving each reel only after its URL is durably captured. You are dispatched with
three inputs in your prompt: `N` (max reels to process this run), `urls_md_path` (absolute path to
the queue file), and `dry_run` (true/false).

## Constraints — read before acting

- **Public accounts/content only.** The "courses" collection is user-confirmed public-only; you
  are not handling private content.
- **Append-before-unsave, always.** Never unsave a reel until `scripts/instagram_capture_helper.py
  process` reports `safe_to_unsave: true` for its URL.
- **Human-paced.** Wait a few seconds between navigating, scrolling, and clicking — do not act in
  rapid succession.
- **Dry run means READ-ONLY.** If `dry_run` is true, you must never click "unsave" and never
  invoke the helper's `process` command (which appends to disk) — only read the grid and report
  what you find.
- **Abort on selector/layout surprises.** If the "courses" grid, a reel tile, or the unsave control
  don't look like what's described below, stop immediately and report exactly what you saw and
  where — do not guess at alternative clicks.

## Algorithm

1. Use `mcp__claude-in-chrome__tabs_context_mcp` to find or create a tab, then
   `mcp__claude-in-chrome__navigate` to the user's Instagram "courses" saved-collection.
2. Use `mcp__claude-in-chrome__read_page` (or `find`) to read the grid and identify the next
   reel tile you have not yet handled this run.
3. Extract that tile's reel URL or shortcode from its link.
4. **If `dry_run` is true:** add this URL to your running `captured` list and go to step 8 (do not
   run the helper, do not click anything).
5. **If `dry_run` is false:** run
   `python scripts/instagram_capture_helper.py process "<url_or_code>" "<urls_md_path>"` via Bash.
   - If it exits 1 (`{"error": ...}`): this tile's link didn't parse as a valid reel/post URL —
     skip it, note the error, continue to the next tile (don't abort the whole run over one bad
     tile).
   - If `safe_to_unsave` is `false` in the JSON result: do NOT unsave this reel. Log it as a
     failure for this item and continue to the next tile — it will be retried on a future run.
   - If `safe_to_unsave` is `true`: use `mcp__claude-in-chrome__computer` to open the reel and
     click its unsave control, then add the returned `url` to your `captured` list.
6. Wait a few seconds (human-paced) before the next tile.
7. Repeat from step 2 until you've handled `N` reels or the collection has no more unprocessed
   tiles.
8. Return your final message as a single JSON object: `{"captured": [...urls], "count": <len>}`.
   If you aborted early due to a selector surprise, instead return
   `{"captured": [...urls so far], "count": <len>, "aborted": true, "reason": "<what you saw>"}`.
```

- [ ] **Step 2: Verify frontmatter and required content**

Run:
```bash
grep -c "^name: instagram-capture-subagent$" .claude/agents/instagram-capture-subagent.md
grep -c "mcp__claude-in-chrome__navigate" .claude/agents/instagram-capture-subagent.md
grep -c "safe_to_unsave" .claude/agents/instagram-capture-subagent.md
grep -c "dry_run" .claude/agents/instagram-capture-subagent.md
```
Expected: each command prints `1` or greater (confirms the frontmatter name, the required tool
reference, and the dedup/dry-run logic references are all present — this is a structural sanity
check, not a behavioral test; this file is a prompt, not executable code).

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/instagram-capture-subagent.md
git commit -m "feat: tool-scoped subagent for Instagram capture"
```

---

### Task 3: Orchestrator command + docs

**Files:**
- Create: `.claude/commands/instagram-capture.md`
- Modify: `README.md` (append a new `## Instagram capture (optional)` section, after the existing "## Contributing" section — see exact insertion point below)

**Interfaces:**
- Consumes: Task 2's `instagram-capture-subagent` (dispatched via the Agent tool with `N`, `urls_md_path`, `dry_run` in its prompt).
- Produces: the user-facing entry point, `/instagram-capture [N] [--dry-run]`.

- [ ] **Step 1: Write the orchestrator command**

Create `.claude/commands/instagram-capture.md`:

```markdown
---
description: Capture up to N reel URLs from your Instagram "courses" saved-collection into read-video's inbox queue. Add --dry-run to preview without writing or unsaving anything.
argument-hint: [N] [--dry-run]
---

Parse `$ARGUMENTS`:
- An integer, if present, is `N` (default 10 if omitted).
- The literal flag `--dry-run`, if present, sets `dry_run = true` (default `false`).

Resolve the queue file path:
1. Read the installed skill's `workspace.json` — `~/.claude/skills/read-video/workspace.json`
   (i.e. `$env:USERPROFILE\.claude\skills\read-video\workspace.json` on Windows) — for its
   `inbox_dir` value. This is the live installed copy, not this repo's `skill/` directory (which
   has no `workspace.json` — it's gitignored local config, created only at install time; see
   `skill/workspace.example.json` for the template).
2. `urls_md_path` = `<inbox_dir>/urls.md`.
3. If that `workspace.json` doesn't exist or has no `inbox_dir`, stop and tell the user to
   configure one first (copy `skill/workspace.example.json` to
   `~/.claude/skills/read-video/workspace.json` and set `inbox_dir`) — this command has nowhere to
   write captured URLs without it.

Dispatch the `instagram-capture-subagent` (via the Agent tool) with a prompt stating exactly:
`N=<N>`, `urls_md_path=<resolved path>`, `dry_run=<true|false>`.

**Before dispatching a live (non-dry-run) run for the first time this session, confirm with the
user that they're watching** — this drives real clicks (navigate, unsave) against their live
Instagram account. Skip this confirmation for `--dry-run` invocations (read-only, nothing to
watch for).

When the subagent returns, report its result plainly:
- Dry run: "Would capture N reels: <list of URLs>" (nothing was written or unsaved).
- Live run: "Captured N reels into <urls_md_path>: <list of URLs>" plus, if the subagent reported
  `aborted: true`, surface its `reason` verbatim rather than treating the run as fully successful.

Do not trigger `read-video` processing automatically — that is a separate, future step the user
runs themselves.
```

- [ ] **Step 2: Verify frontmatter and required content**

Run:
```bash
grep -c "^description:" .claude/commands/instagram-capture.md
grep -c "instagram-capture-subagent" .claude/commands/instagram-capture.md
grep -c "dry_run" .claude/commands/instagram-capture.md
grep -c "workspace.json" .claude/commands/instagram-capture.md
```
Expected: each command prints `1` or greater.

- [ ] **Step 3: Add the README section**

Read `README.md` first to find the exact text of the `## Contributing` section (added at the end,
right before `## License`). Insert the new section directly before `## Contributing`:

```markdown
## Instagram capture (optional)

If you save job-hunting/AI/programming reels into an Instagram collection named **"courses"**, the
`/instagram-capture [N] [--dry-run]` Claude Code command (this repo's `.claude/commands/` +
`.claude/agents/`) can pull up to N of their URLs straight into `read-video`'s `inbox_dir/urls.md`
queue — a scoped subagent drives the browsing via `claude-in-chrome`, unsaving each reel only after
its URL is confirmed captured. Claude-Code-only (depends on the `claude-in-chrome` MCP tools); it
does not extend to the other harnesses `read-video` itself supports. Always dry-run first
(`--dry-run` — lists candidates, writes/unsaves nothing) before a live run, and watch the first
live run end-to-end. It never triggers `read-video` processing itself — run `probe`/`estimate`/`run`
against the populated queue separately, exactly as documented above.

```

- [ ] **Step 4: Run the full suite to confirm no regressions**

Run: `python -m pytest -q`
Expected: all tests pass (71, unchanged from Task 1 — this task adds no Python code)

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/instagram-capture.md README.md
git commit -m "feat: /instagram-capture orchestrator command + docs"
```

---

### Task 4: Dry-run verification against the real Instagram collection

**Files:** none (no code changes — this is a live manual verification task, per the spec's Testing section: browser-driving behavior against a real external service cannot be meaningfully unit-tested).

**Interfaces:**
- Consumes: Tasks 1-3's complete `/instagram-capture --dry-run` command.

- [ ] **Step 1: Invoke the command in dry-run mode**

Run `/instagram-capture 10 --dry-run` in this Claude Code session (requires the user's Chrome,
logged into Instagram, on the "courses" saved-collection or reachable from it).

- [ ] **Step 2: Verify the reported candidate list**

Confirm: the reported URLs are well-formed `https://www.instagram.com/reel/<shortcode>/` links,
the count matches what's visible in the "courses" collection (up to 10), and — check this
explicitly — that `urls.md` was NOT modified and no reel was unsaved (re-check the collection's
saved count before/after).

- [ ] **Step 3: Fix any selector/parsing issues found**

If step 2 surfaces a problem (wrong tiles read, malformed URLs, wrong collection), fix the
relevant file from Task 2 or Task 3 and re-run Step 1. Do not proceed to Task 5 until a dry run
produces a correct, clean candidate list.

---

### Task 5: First live run (watched)

**Files:** none (live manual verification — this task performs the first real, non-dry-run
invocation).

**Interfaces:**
- Consumes: Tasks 1-4's complete, dry-run-verified `/instagram-capture` command.

- [ ] **Step 1: Confirm with the user before running live**

This is the point flagged by the spec's Testing section and the user's own standing directive
(pause before anything irreversible/detrimental) — unsaving reels from their real Instagram
account is exactly that. Ask the user to confirm they're ready to watch, with a small `N` (e.g.
2-3) for this first run.

- [ ] **Step 2: Invoke the command live, user watching**

Run `/instagram-capture 3` (no `--dry-run`) with the user observing the browser actions in
real time.

- [ ] **Step 3: Verify the append-before-unsave ordering held**

Confirm: `urls.md` contains the newly captured URLs, and each corresponding reel was unsaved from
"courses" only after (never before) its line was confirmed present. Confirm no unintended clicks
occurred.

- [ ] **Step 4: Report to the user and update the progress ledger**

Summarize the outcome (captured count, any issues) and append a line to
`.superpowers/sdd/progress.md` recording all 5 tasks complete, ready for the final whole-branch
review and `finishing-a-development-branch`.
