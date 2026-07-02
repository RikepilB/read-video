# Agent-Harness Packaging — Design

**Date:** 2026-07-02
**Status:** Approved
**Scope:** Make `read-video` installable and usable across Claude Code, Codex, Gemini CLI, and Copilot CLI

## Context

`read-video` currently installs only to `~/.claude/skills/read-video/` and its `SKILL.md` speaks in
Claude-Code-specific terms ("Claude's `Read` tool", "Claude"). The engine itself
(`skill/scripts/video.py`) has no Claude Code dependency — it's a stdlib-only Python CLI driven by
`probe → estimate → [gate] → run`, already usable by anything that can shell out and read files.

Research into how other agent CLIs discover skills (superpowers' own cross-runtime tool-mapping
docs, `using-superpowers/references/{codex,gemini,copilot,claude-code}-tools.md`) surfaced a key
fact: Codex, Gemini CLI, and Copilot CLI all read one shared cross-runtime directory,
`~/.agents/skills/`, using the **identical** `SKILL.md` format (a subdirectory with `name` +
`description` YAML frontmatter) that Claude Code uses at `~/.claude/skills/`. Claude Code does
**not** read `~/.agents/skills/`. This means no per-harness adapter or format translation is
needed — the same `skill/` directory, installed to two roots, covers all four target harnesses.

## Goals

1. **Multi-harness install** — one command installs `skill/` to both `~/.claude/skills/read-video/`
   (Claude Code) and `~/.agents/skills/read-video/` (Codex, Gemini CLI, Copilot CLI — shared).
2. **Harness-neutral skill prose** — `SKILL.md` describes the workflow in action terms ("read the
   frames", "run the CLI") rather than naming Claude Code's `Read` tool specifically.
3. **Verification** — the install step confirms both installed copies are structurally valid
   (frontmatter present, CLI runnable) before declaring success.
4. **Documentation** — a new doc records the `~/.agents/skills/` discovery and the install
   mechanism for future maintainers.

## Constraints

- **Zero runtime code changes.** `skill/scripts/video.py` and the cost-gate pipeline
  (`probe`/`estimate`/`run`) are already harness-neutral; this work is prose + tooling only.
- **Never touch local config/secrets during install.** `workspace.json`, `.env`, `load-env.ps1` at
  either install destination must survive an install run untouched (matches the precedent set
  during the v0.2.0 port's live-install sync).
- **Windows-primary environment.** The install script must work natively in PowerShell; a
  Bash/macOS/Linux counterpart is provided for parity but PowerShell is the reference
  implementation and gets tested first.

## Non-goals

- **Agent SDK / custom-bot integration** and **non-interactive automation** (cron, n8n) — the user
  scoped this thread to "Claude-Code-like CLIs" only (Codex, Gemini CLI, Copilot CLI). Those other
  integration modes are explicitly out of scope and may become their own future thread.
- **Symlink-based install.** Rejected in favor of copy+script: Windows symlinks need Developer Mode
  or admin rights, which isn't guaranteed on this machine or a future user's.
- **Restructuring `video.py` or the cost-gate architecture.** Out of scope — it doesn't need to
  change for this goal.
- **PyPI/pip packaging of the CLI.** Not requested; the CLI stays a plain script invoked via
  `python scripts/video.py ...`, as today.

## Architecture

`skill/` in the repo remains the single source of truth. A new install script copies it, verbatim
minus excluded local-config files, to both target roots:

```
skill/  ──install script──►  ~/.claude/skills/read-video/     (Claude Code)
                         └─► ~/.agents/skills/read-video/      (Codex, Gemini CLI, Copilot CLI)
```

No new runtime dependency, no new install-time dependency beyond what's already required
(PowerShell on Windows, ffmpeg/ffprobe/yt-dlp already documented as prerequisites).

## Components

### 1. `skill/SKILL.md` prose edit

Replace Claude-Code-specific phrasing with harness-neutral action language, consistent with the
"speak in actions" convention used by superpowers' own cross-runtime skill docs:

- `description:` frontmatter: `"...so Claude can SEE..."` / `"...for Claude to..."` → rephrase
  around the agent generically (e.g. "so the agent can see the visual track").
- Body: `"Claude's `Read` tool renders images and PDFs — not video."` → `"An agent's file-reading
  tool renders images and PDFs — not video."` (or equivalent), and every other bare `"Claude"` →
  `"the agent"` where it refers to whichever model is driving the skill, not the Anthropic product
  specifically.
- The CLI mechanics section (`probe`/`estimate`/gate/`run`, backend cascade, output contract) is
  already tool-agnostic prose and needs no changes.

### 2. Install scripts

`scripts/install-skill.ps1` (primary) and `scripts/install-skill.sh` (parity, for macOS/Linux/Git
Bash users), both performing the same steps:

1. Resolve `$REPO_ROOT/skill` as the source.
2. For each target root (`~/.claude/skills/read-video`, `~/.agents/skills/read-video`):
   - Create the target's parent directory if missing (e.g. `~/.agents/` may not exist yet if none
     of Codex/Gemini CLI/Copilot CLI are installed — this is harmless and future-proofs the install
     for whichever the user adds later).
   - Copy every file under `skill/` to the target, **excluding** `workspace.json`, `.env`,
     `load-env.ps1` if they already exist at the destination (never overwrite live local config;
     if the destination has no such file yet, nothing to preserve, so this is a no-op).
   - Copy `skill/workspace.example.json` normally (it's a template, not secret, and safe to
     overwrite).
3. Run verification (component 3) against each target independently.
4. Print a per-target `OK` / `FAILED` summary; exit non-zero only if **every** target failed (a
   single-harness environment, e.g. a machine with only Claude Code installed, is a valid success
   state — `~/.agents/skills/` still gets created and populated for future-proofing, but its
   verification passing isn't required for overall success if, say, Python isn't on PATH the same
   way — see Error Handling).

### 3. Verification step

For each installed target, run two checks and report both independently:

- **Frontmatter check** — parse the installed `SKILL.md`'s YAML frontmatter block; confirm `name`
  and `description` keys exist and are non-empty strings.
- **CLI check** — run `python scripts/video.py --help` (or `probe --help`) from the installed
  target's `scripts/` directory; confirm exit code 0.

Both checks are informational per-target; a failure at one target is reported clearly but does not
abort checking the other target.

### 4. `docs/harness-support.md` (new)

Documents:
- The four target harnesses and which install root each reads.
- The `~/.claude/skills/` vs `~/.agents/skills/` split and why Claude Code needs its own copy.
- Why no per-harness adapter/translation exists (identical `SKILL.md` format across all four).
- How to re-run the install script after editing `skill/` (there is no live-sync watcher — this is
  a manual, explicit step, same model as the v0.2.0 port's live-install sync).

### 5. README update

New "Multi-harness install" section referencing the install script and pointing to
`docs/harness-support.md`, added alongside (not replacing) the existing manual
`cp -r` / `Copy-Item` instructions — those remain valid for Claude-Code-only users who don't want
the extra `~/.agents/skills/` copy.

## Data flow

```
developer edits skill/
        │
        ▼
run scripts/install-skill.ps1 (or .sh)
        │
        ├─► copy skill/* → ~/.claude/skills/read-video/   (excl. local config)
        │        └─► verify: frontmatter + `--help`
        │
        └─► copy skill/* → ~/.agents/skills/read-video/   (excl. local config)
                 └─► verify: frontmatter + `--help`
        │
        ▼
print per-target OK/FAILED summary
```

No change to the agent-facing runtime data flow — `probe → estimate → [gate] → run` behaves
identically regardless of which harness invokes it, since it's the same script either way.

## Error handling

- **Target parent directory missing** (e.g. `~/.agents/` doesn't exist) — create it. Never treat
  this as an error; it just means no cross-runtime CLI has been installed yet on this machine.
- **Copy step fails** for one target (e.g. permissions) — report that target's failure clearly,
  still attempt the other target, still run verification against whichever target(s) succeeded.
- **Verification fails** at one target (bad frontmatter, `--help` non-zero exit, e.g. because
  Python isn't on PATH in that shell context) — report it, don't block the other target's success
  report.
- **Local config collision** — if `workspace.json`/`.env`/`load-env.ps1` already exist at a
  destination, the script must never overwrite them; if they don't exist yet, nothing to preserve.
- **Overall exit code** — non-zero only if every target's copy step failed outright (i.e., nothing
  was installed anywhere); a partial success (one target installed and verified, the other's
  parent dir didn't exist so it was created and populated but Python isn't on that machine's PATH
  for verification) still exits 0 with a clear summary, since "harness not yet configured on this
  machine" isn't a failure of this script's job.

## Testing

No `pytest`/`video.py` changes — the CLI itself is untouched. Verification is the test: the install
script's own frontmatter-parse + `--help`-exit-code checks, run against both installed copies
after every install, serve as the acceptance test for this feature. A manual end-to-end pass
(run the script fresh against a machine with no prior install, confirm both directories are
created and populated correctly, re-run against an existing install to confirm local config
survives) is the closing verification step before this ships.

## Credits

No third-party code ported for this thread — packaging/tooling only, informed by superpowers'
existing cross-runtime tool-mapping documentation (already present in this environment, not a new
dependency).
