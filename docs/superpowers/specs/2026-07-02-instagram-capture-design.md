# Instagram Capture Pipeline (Sub-project #1) — Design

**Date:** 2026-07-02
**Status:** Approved
**Scope:** Capture phase only — pull reel URLs from a saved Instagram collection into `read-video`'s existing input queue

## Context

The user's daily workflow: browse Instagram, save reels/posts relevant to job hunting, AI/agent
tooling, programming fundamentals, system design, security, and project lifecycle into a saved
collection named **"Cursos"** (Spanish for "Cursos" — confirmed as the collection's real name
during Task 4's live verification; earlier design conversation used the English gloss). The
long-term goal (this thread's larger vision, decomposed across
future sub-projects) is to transcribe and analyze each saved reel via the existing `read-video`
skill, produce a report per video, and eventually build a searchable knowledge library ("second
brain"). That downstream analysis/report/indexing work is explicitly **out of scope here** — this
spec covers only getting reel URLs out of Instagram and into `read-video`'s queue, safely and
observably.

`read-video` already has an input queue mechanism: when `workspace.json` is configured, bare
filenames or lines from `inbox_dir/urls.md` are accepted directly by `probe`/`estimate`/`run`. This
sub-project's only job is to populate `urls.md` — everything downstream is unmodified.

## Goals

1. **Automated capture** — an orchestrator command (e.g. `/instagram-capture [N=10]`) drives a
   scoped browser-automation subagent that reads up to N reel URLs from the "Cursos" collection
   and appends them to `read-video`'s existing `inbox_dir/urls.md`.
2. **Self-dedupe via unsave** — once a reel's URL is confirmed written to `urls.md`, the subagent
   unsaves it from the collection. A reel no longer in "Cursos" was already captured; this needs
   no separate dedup state file.
3. **Safe by default** — a dry-run mode that lists candidate URLs without writing or unsaving
   anything, so selectors can be validated before any live state-changing run.
4. **Zero coupling to read-video internals** — this sub-project only ever appends lines to
   `urls.md`. It never calls `video.py`, never triggers transcription, never touches the cost gate.
   That hand-off is a separate future sub-project, designed later once this capture step is proven.

## Constraints

- **Public accounts/content only** — the "Cursos" collection contains only saves from public
  accounts (user-confirmed); no private-content access is in scope.
- **Append-before-unsave, always** — a reel must never be unsaved unless its URL write to
  `urls.md` is confirmed first. Losing a saved reel without capturing its URL is the one truly
  bad outcome (data loss on the user's own curated collection) — the ordering exists specifically
  to prevent it.
- **Claude Code + Claude in Chrome only.** This sub-project relies on the `claude-in-chrome`
  MCP browser-automation tools, which are Claude-Code-specific. Unlike `read-video` itself (now
  multi-harness per Thread C), this capture pipeline does **not** extend to Codex/Gemini
  CLI/Copilot CLI — those harnesses have no equivalent browser-driving tool available in this
  environment.
- **Human-paced interaction** — delays between navigation/scroll/click actions, not rapid-fire
  automation, to look and behave like normal manual browsing.
- **Reuses `read-video`'s existing queue file** (`inbox_dir/urls.md`) — no new state/database
  file for tracking what's been captured.

## Non-goals

- **Transcription, analysis, report generation, or indexing** of captured reels — sub-project #2+,
  designed separately later.
- **Private accounts or non-"Cursos" collections** — out of scope; may become a future parameter
  if the user wants it, not assumed here.
- **Multi-harness support** — this is a Claude-Code-only automation, unlike `read-video`'s core.
- **Automatic scheduling/cron** — the user invokes the orchestrator command manually ("periodically
  ask in a command"); no background scheduler is being built.
- **Handling Instagram UI/selector changes gracefully** — if the page layout breaks the subagent's
  selectors, it aborts and reports plainly. Building resilient selector-fallback logic is future
  work if breakage becomes a recurring problem.

## Architecture

Two phases exist in the user's full vision; **only phase 1 is this spec**:

```
Phase 1 (this spec):  IG "Cursos" collection ──► urls.md               [capture]
Phase 2 (future):     urls.md ──► read-video (unmodified) ──► reports   [analyze]
```

Phase 1 itself has two components:

```
/instagram-capture [N=10]  (orchestrator command)
        │
        ▼
Capture subagent (scoped: Chrome navigate/read/click only)
        │
        ├─► read next reel from "Cursos" grid
        ├─► extract shortcode → build full reel URL
        ├─► append URL to inbox_dir/urls.md
        ├─► confirm the line landed (re-read file)
        ├─► unsave the reel (only after confirmed append)
        └─► repeat up to N times, or until collection exhausted
        │
        ▼
returns {captured: [urls...], count} to orchestrator
```

## Components

### 1. Orchestrator command — `/instagram-capture [N=10]`

A slash command (Claude Code custom command) that:
- Accepts an optional `N` (default 10) — max reels to capture this run.
- Resolves `inbox_dir` from `read-video`'s `workspace.json` (same config the skill already reads).
- Dispatches the capture subagent (component 2) with `N` and the resolved `urls.md` path.
- Reports the subagent's `{captured, count}` result back to the user in plain text — no further
  action taken automatically.

### 2. Capture subagent

Scoped tools only: Chrome navigation, page read, click (the `claude-in-chrome` MCP tools) — no
filesystem/Bash access beyond what's needed to append to `urls.md`. Single loop, one item at a
time:

1. Navigate to (or confirm already on) the "Cursos" saved-collection grid.
2. Read the grid, identify the next not-yet-processed reel tile.
3. Extract the reel's shortcode from its link/URL; build the canonical `instagram.com/reel/<shortcode>/`
   URL. (Confirmed during Task 4: the collection grid's own links use `/p/<shortcode>/` even for
   Reels content — expected Instagram behavior, not a bug. The helper accepts `/p/`, `/reel/`, and
   `/tv/` paths and always canonicalizes to `/reel/`.)
4. **Dupe guard**: if this URL is already present in `urls.md`, skip the append (don't double-add
   the line) but still attempt the unsave — this is exactly the recovery path for a prior run
   where the append succeeded but the unsave failed, and it's how such reels eventually drain
   from the collection instead of resurfacing as a candidate forever.
5. Append the URL as a new line to `urls.md`.
6. Re-read `urls.md` to confirm the line is present (append-before-unsave invariant).
7. Only after confirmed: open the reel and unsave it.
8. Repeat from step 2 until N reels processed or the collection has no more unprocessed items.

**Dry-run mode**: same steps 1–4 only — lists the N candidate URLs it *would* capture, performs no
writes to `urls.md` and no unsaves. Used to validate selectors before trusting the subagent with
real state changes.

## Data flow

```
"Cursos" grid ──scroll/read──► candidate tile
                                      │
                              extract shortcode
                                      │
                              build full reel URL
                                      │
                    ┌── already in urls.md? ──yes──► skip (no unsave)
                    │no
                    ▼
            append line to urls.md
                    │
            re-read, confirm write
                    │
              unsave the reel
                    │
              repeat ×N or until exhausted
                    │
                    ▼
      subagent → {captured: [...], count} → orchestrator → user
```

No automatic hand-off into `read-video` — the user runs `probe`/`estimate`/`run` against the
populated `urls.md` separately (exactly as `read-video` already supports today), or a future
sub-project wires that hand-off explicitly.

## Error handling

- **Append succeeds, unsave fails** — acceptable; the reel stays saved. On the next run, the dupe
  guard recognizes its URL is already in `urls.md`, skips re-appending, and retries the unsave —
  this is how such reels eventually drain from the collection rather than resurfacing forever.
  Never a data-loss case.
- **Append fails (write error, permissions)** — do not unsave. Abort that item, continue to the
  next if possible, report the failure in the final summary.
- **Dupe found** — skip the append, still attempt the unsave (see Component 2 step 4), continue to
  the next candidate; doesn't count against the N budget in a way that causes an error, just moves
  on.
- **Fewer than N unprocessed items available** — capture whatever exists, report the actual count
  captured (which may be less than N), not an error.
- **Selector/layout break** (grid structure, unsave button, etc. not found as expected) — abort
  immediately, report plainly what broke and where, rather than guessing at alternative clicks or
  retrying blindly.
- **Pacing** — deliberate human-ish delays between navigate/scroll/click actions; no rapid-fire
  automation that could look like scripted abuse.

## Testing

- **Dry-run first**: run in list-only mode against the real "Cursos" collection, verify the
  extracted URLs and shortcodes look correct, with zero writes/unsaves performed.
- **First live run watched manually**: the user observes the first real (non-dry-run) invocation
  end-to-end to confirm append-then-unsave ordering behaves as designed and no unintended clicks
  occur.
- No `pytest` coverage — this component drives a live browser session against a real external
  service (Instagram) and cannot be meaningfully unit-tested or run in CI. Manual verification
  (dry-run, then watched live run) is the acceptance test for this sub-project, consistent with
  how the browser-automation constraints in this codebase's tooling are generally verified.

## Credits

No third-party code ported for this sub-project. Built on the existing `read-video` input-queue
convention (`inbox_dir/urls.md`, already shipped) and the `claude-in-chrome` MCP tools already
available in this environment.
