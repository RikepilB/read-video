# read-video — Handoff Tree

Append-only context tree. `## Current state` below is replaced each session; `## Session index`
only ever grows (newest first, never delete a line). Each indexed session has its own immutable
folder: `<date>-<name>/HANDOFF.md` (curated digest) + `transcript.md` (full `/export`, if
captured) + any `snapshot-<HHMMSS>.md` auto-written by the PreCompact hook near ~30% context.

To orient fast: read `## Current state` + the top of `## Session index`. For a deep dive into a
past session, open that session's folder — `HANDOFF.md` first, `transcript.md` only if the digest
isn't enough.

## Current state

All previously-shipped work is merged to `main` and pushed to `origin/main` (through commit
`6957013`), 79/79 tests passing. Threads A (upstream v0.2.0 port), C (agent-harness packaging), D
(Instagram capture pipeline), and E (IG capture→analysis pipeline) are all complete. Thread F
(transcription thoroughness tiers — fixes a completeness gap on clips >~45s) has an **approved but
unimplemented** spec, explicitly parked by user choice. `docs/ROADMAP.md` captures a long-term
multi-platform/multi-media/three-audience vision (planning-only, currently uncommitted). This
`docs/handoff/` tree was initialized this session.

**New this session:** built `/ig-pipeline` — a real orchestrator command
(`.claude/commands/ig-pipeline.md`) + new `ig-analyze-subagent` — formalizing Thread E's
retro-spec'd capture→analyze flow into reusable tooling (dedup guard, per-video cost gate, cookie
handling baked in). Uncommitted (tracked in issue #1). First 45-reel batch (5-video checkpoint +
41-video batch, done manually before the command existed) is fully complete and disk-diff-verified
— 40 new vault notes, 5 legitimate skips, `_ig-index.md` at 85 rows at that point.

**Then, same session, `/ig-pipeline 20` was run live for the first time** (first real dispatch of
the finished command): capture phase succeeded (20 net-new reels into `urls.md`, all unsaved,
0 dupes/aborts). Analysis phase **ran to completion**: all 20 processed, 0 skips, `_ig-index.md`
grew 93→107 rows (105 data rows). One controller-side dispatch slip (`DYHfiH0Csdl` silently never
sent, a recurrence of a prior-session failure mode) was caught by the standing disk-diff-before-
done practice, fixed, and re-verified clean — vault now at 111 notes total. This is the **second**
time this exact slip class has happened; see this session's folder (Failed attempts) for the
pattern note and a possible spec gap in `/ig-pipeline` itself (no mandatory final disk-diff sweep
before its "final report" step).

**Then, a later session, the 111-note vault was reorganized**: renamed every `ig-<shortcode>.md`
to a clean title-slug and sorted into 9 topic subfolders + `_Skipped` under
`06_Media/Transcripts/`. Blocked first on `advisor`'s catch that a naive rename breaks
`/ig-pipeline`'s filename-based dedup — resolved by keying dedup off each note's own `Source:`
line instead. Also found and fixed a latent bug while at it: 6 files (1 real note + 5 skip
markers) existed on disk but were never in `_ig-index.md` at all — folded into the rebuilt,
category-grouped index (now 111 rows). Updated `.claude/commands/ig-pipeline.md` +
`.claude/agents/ig-analyze-subagent.md` in lockstep so future runs write into this same structure
(content-keyed dedup, per-video category classification, category-section index inserts) instead
of regressing to flat root-level files. **Not yet exercised by a live pipeline run** — worth a
small dispatch to confirm before trusting it at batch size. `_rename-manifest.tsv` (old→new paths)
written to the vault as the only undo trail, since that vault has no git history of its own.

**Then, new turn, a new capability was added: local audio transcription.** User handed over two
personal `.m4a` voice memos (a hackathon-project brainstorm chat with a friend, unrelated to
Instagram) and asked to both transcribe+note them and get a reusable command for future audio
files. Confirmed `video.py` already handles local audio-only input fine (`tier audio`); cost-gated
both files (`free: true, needs_install: false`, local `faster-whisper`); asked the user where to
save (new `02_Execution/01_Active_Projects/Claude_LifeSciences_Hackathon/` project folder) and
whether to proceed despite the still-parked Thread F completeness gap (both files are well past
the ~45s threshold) — user chose to proceed now. Both files transcribed and noted: file 1
(14m29s, `project-hackathon-call-1.md`) covers bioinformatics tool gaps as a project angle +
hackathon logistics; file 2 (50m42s, `project-hackathon-call-2.md`) is far idea-denser — 6
distinct candidate hackathon project ideas surfaced and ranked (paper-to-digital lab-protocol
converter most pitch-ready; "GitHub for lab results"; research bookmark/organizer tool;
result-triage layer over the bioinformatics stack; a STEM-education kit flagged out of scope; one
unrelated class project excluded), plus the actual application questions pulled verbatim. User
then pasted a raw keyword shortlist from the same conversation, folded into call 1's note as a new
section. Built `.claude/commands/read-audio.md` — general-purpose, sequential (1-3 files at a
time), cost-gated per file, not yet exercised as an actual slash-command invocation.

Repo currently has 6 uncommitted items on `main`: `docs/ROADMAP.md`, this `docs/handoff/` tree,
`.claude/commands/ig-pipeline.md`, `.claude/agents/ig-analyze-subagent.md` (both updated for the
vault reorg), and now `.claude/commands/read-audio.md` (new). Not blocking, just undecided when to
commit — loosely tracked in GitHub issue #1, whose file list is stale relative to current state.

**GitHub issues** (`RikepilB/read-video`) mirror this tree's standing backlog as of this session:
#1 (commit pending docs, updated), #3 (Thread F implementation), #4 (note-quality spot-check), #5
(roadmap Phase 0 kickoff). #2 is a pre-existing unrelated bug report. Created via
`/handoff-to-issues`, read-only on this tree.

## Session index
_(newest first)_

- **2026-07-05-f409bd2c** — reorganized the 111-note Instagram vault (title-slug filenames, 9
  topic folders + `_Skipped`, category-grouped `_ig-index.md`, `/ig-pipeline`/`ig-analyze-subagent`
  updated to match, blocked-then-fixed on an `advisor`-caught dedup-breakage risk, found+fixed a
  6-file index gap); then added a new local-audio-transcription capability — built `/read-audio`
  and used its underlying steps to transcribe two personal hackathon-brainstorm voice memos (14m +
  51m) into a new `Claude_LifeSciences_Hackathon` project folder, surfacing 6 ranked candidate
  hackathon project ideas, then folded in a user-supplied keyword shortlist from the same
  conversation.
- **2026-07-03-wrapup-and-roadmap** — resolved Thread D/E open decisions, diagnosed+designed
  (parked) a transcription-completeness fix, wrapped up and shipped everything to `main`/`origin`,
  wrote `docs/ROADMAP.md` (long-term multi-platform vision), initialized this handoff tree; then,
  same session, built `/ig-pipeline` (command + subagent) to formalize the capture→analyze flow,
  paused before its first live dispatch pending user confirmation; then ran `/handoff-to-issues`,
  filing #3/#4/#5 and refreshing stale #1 on GitHub; then ran `/ig-pipeline 20` live for the first
  time to full completion — 20 captured/processed, 0 skips, one controller-side dispatch slip
  (2nd occurrence of that failure class) caught by the standing disk-diff practice and fixed before
  declaring done, vault now at 111 notes.
- _(2026-06-30 → 2026-07-02, pre-tree: upstream v0.2.0 port, agent-harness packaging, Instagram
  capture pipeline (Threads A/C/D) — see root `handoff.md` and `git log` for detail; no per-session
  folders exist for this range.)_

<!-- compact-handoff:auto-snapshot -->
<!-- Latest auto-snapshot: docs/handoff/2026-07-05-f409bd2c/snapshot-021552.md -->
## Latest auto snapshot — 2026-07-06T02:15:52.542Z
- Session folder: `docs/handoff/2026-07-05-f409bd2c/`
- Snapshot file: `docs/handoff/2026-07-05-f409bd2c/snapshot-021552.md`
- Branch: main
