---
description: Full Instagram pipeline — capture up to N reels from your "Cursos" saved collection, then analyze each new one into a per-video vault note + priority-ranked index. Add --dry-run to preview capture only (nothing written/unsaved, no analysis phase).
argument-hint: [N] [--dry-run]
---

Parse `$ARGUMENTS`:
- An integer, if present, is `N` (default 10 if omitted).
- The literal flag `--dry-run`, if present, sets `dry_run = true` (default `false`).

## 1. Resolve paths

1. Read the installed skill's `workspace.json` — `~/.claude/skills/read-video/workspace.json`
   (`$env:USERPROFILE\.claude\skills\read-video\workspace.json` on Windows) — for `inbox_dir` and
   `out_dir`. If missing or incomplete, stop and tell the user to configure it first (copy
   `skill/workspace.example.json` to that path and fill it in).
2. `urls_md_path` = `<inbox_dir>/urls.md`.
3. `skill_dir` = the directory containing that `workspace.json` (i.e.
   `~/.claude/skills/read-video`) — this is where `scripts/video.py` and `pricing.json` live.
4. `out_dir` = the `workspace.json` value directly — notes live in fixed topic subfolders under
   here (see `ig-analyze-subagent`'s "Fixed category folders"), and `_ig-index.md` lives at its
   root.

## 2. Resolve the cookies path (required before any analysis)

Check, in order:
1. The current shell's `READ_VIDEO_YTDLP_COOKIES` env var.
2. If empty, the persisted Windows user-level value:
   `powershell.exe -Command "[Environment]::GetEnvironmentVariable('READ_VIDEO_YTDLP_COOKIES','User')"`
   — this reads back a value the user already set themselves via `setx`; it is not a credential
   scan of any file or store.

If both are empty, stop and tell the user: analysis needs `READ_VIDEO_YTDLP_COOKIES` pointing at
their exported Instagram `cookies.txt` (see `skill/references/backends.md` for how to export one),
set via `setx READ_VIDEO_YTDLP_COOKIES "<path>"` or `export` in their shell, then re-run. Do not
search the filesystem for a cookies file yourself.

Call the resolved value `cookies_path` for the rest of this command — pass it explicitly into
every subagent dispatch below (never rely on a subagent inheriting it from the environment).

## 3. Capture phase

**Before dispatching a live (non-`--dry-run`) run for the first time this session, confirm with
the user that they're watching** — this drives real clicks (navigate, unsave) against their live
Instagram account. Skip this confirmation for `--dry-run` invocations.

Dispatch the `instagram-capture-subagent` (via the Agent tool) with `N=<N>`,
`urls_md_path=<resolved path>`, `dry_run=<true|false>` — identical contract to `/instagram-capture`.

- If the result has `aborted: true`: report "Stopped early after <count> reel(s) — <reason>" with
  whatever partial `captured` list came back. If `dry_run` was true, stop here (nothing to
  analyze). If `dry_run` was false and at least one reel was captured, continue to the analysis
  phase for just those — an aborted capture still legitimately unsaved what it captured.
- If `dry_run` was true and not aborted: report "Would capture N reels: <list>" and **stop** — dry
  run previews capture only, no analysis phase runs.
- Otherwise: report "Captured N reels into <urls_md_path>: <list>" and continue.

## 4. Build the analysis queue (dedup guard)

1. Parse every reel URL out of `urls_md_path`, extracting each one's shortcode (the segment
   between `/reel/`, `/p/`, or `/tv/` and the trailing slash).
2. Recursively find every `*.md` file under `out_dir` (all category subfolders, excluding
   `_ig-index.md`) and extract the shortcode from each file's `Source:` line (the segment between
   `/reel/`, `/p/`, or `/tv/` and the trailing slash in that line's URL) — notes are no longer
   named `ig-<code>.md`, so the shortcode must be read from file content, not the filename.
3. Queue = shortcodes from step 1 minus shortcodes from step 2 (disk diff, not a remembered
   count — regenerate this list fresh, don't trust an in-memory tally from the capture phase).

If the queue is empty, report "Nothing new to analyze — all captured reels already have notes" and
stop.

## 5. Analysis phase — wave dispatch

Process the queue in waves of up to 5 concurrent `ig-analyze-subagent` dispatches (Agent tool).
Each dispatch's prompt states exactly: `url=<full reel URL>`, `out_dir=<resolved path>`,
`skill_dir=<resolved path>`, `cookies_path=<resolved path>`.

`_ig-index.md` is organized as one `## <Category Display Name>` section per category (in the
fixed order below), each holding its own `| Priority | Title | Synopsis | File | Source |` table.
Category → display name:

`Claude-Code_Agent_Workflows` → "Claude Code & Agent Workflows" ·
`Job_Hunting_Interviews` → "Job Hunting & Interviews" ·
`AI_ML_Learning_Projects` → "AI/ML Learning & Projects" ·
`System_Design_CS_Fundamentals` → "System Design & CS Fundamentals" ·
`Security_Privacy` → "Security & Privacy" ·
`Design_UI` → "Design & UI" ·
`Startups_Business_Legal` → "Startups, Business & Legal" ·
`Tools_Utilities` → "Tools & Utilities" ·
`Off_Topic_Local` → "Off-Topic / Local Interest" ·
`_Skipped` → "Skipped (no video content)"

As each subagent returns:
- If `skipped: true`: log the shortcode + reason (its own skip-marker file is already written by
  the subagent — you do not need to write anything for it). Do not count it in the index.
- If `skipped: false`: **you** (the controller) add one row to the matching category's table in
  `<out_dir>/_ig-index.md`:

  ```markdown
  | <priority> | <title> | <synopsis> | [<file>](<file>) | <source_url> |
  ```

  If `_ig-index.md` doesn't exist yet, create it first with the standard intro (see any existing
  copy for wording) and no category sections. If the returned category's `## <Display Name>`
  section doesn't exist yet, create it (with its own header row) in the fixed order above —
  insert it immediately before the next category (in that order) that already has a section, or
  at the end if none do. If the section already exists, append the new row as the table's last
  line before the following blank line/heading.

Never let a subagent write to `_ig-index.md` directly — only append here, in the controller, one
row per completion notification, to avoid interleaved writes.

Refill each wave slot as its subagent completes; repeat until the queue (step 4) is exhausted.

## 6. Final report

Report: reels captured this run, reels analyzed (broken down by High/Medium/Low and by category
folder), reels skipped (with reasons), and the path to `_ig-index.md`. Note explicitly that this
command has no `pytest` coverage — same as `/instagram-capture`, it's browser/agentic
orchestration, not unit-testable logic; acceptance is the user inspecting the resulting notes.
