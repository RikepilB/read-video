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

When the subagent returns, first check for `aborted: true` — this can happen during a dry run just
as easily as a live run (the subagent's step 1 and step 3 abort triggers fire regardless of
`dry_run`; only step 5's trigger is live-run-only). If aborted, report it as an incomplete run
regardless of mode: "Stopped
early after <count> reel(s) — <reason>" plus whatever partial `captured` list came back — never
report a partial, aborted list as if it were the full requested N.

If not aborted, report the result plainly:
- Dry run: "Would capture N reels: <list of URLs>" (nothing was written or unsaved).
- Live run: "Captured N reels into <urls_md_path>: <list of URLs>".

Do not trigger `read-video` processing automatically — that is a separate, future step the user
runs themselves.
