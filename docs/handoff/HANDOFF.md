# read-video — Handoff Tree

Append-only context tree. `## Current state` below is replaced each session; `## Session index`
only ever grows (newest first, never delete a line). Each indexed session has its own immutable
folder: `<date>-<name>/HANDOFF.md` (curated digest) + `transcript.md` (full `/export`, if
captured) + any `snapshot-<HHMMSS>.md` auto-written by the PreCompact hook near ~30% context.

To orient fast: read `## Current state` + the top of `## Session index`. For a deep dive into a
past session, open that session's folder — `HANDOFF.md` first, `transcript.md` only if the digest
isn't enough.

## Current state

OpenAI Build Week extension is implemented, code-reviewed, and fixed on
`codex/build-week-read-video` (7 commits ahead of `main`, all pushed to origin, working tree
clean). `/code-review` found 9 real bugs (all in the new cost/consent gate); all 6 underlying
fixes landed with regression tests — `pytest` 103 → **111 passed**. `SkillSpector` still returns
`100/100 CRITICAL` (intentional env-key→cloud-request flow) — disposition: **accept + document**,
covered in the new `SECURITY.md`. A **GitHub Pages landing page** (`docs/index.html`, no external
fonts/CDN) is live at **https://rikepilb.github.io/read-video/**, built from this branch. A 9-beat
demo shot list (`docs/demo-shot-list.md`) is drafted for the required <3-min Devpost video —
**recording itself is still pending** (manual, needs a real >45s spoken clip for the transcription-
tiers beat). Root `handoff.md` was untracked from git (internal artifact; this tree is canonical).

**Still open before the 2026-07-21, 5PM PT deadline:** record/upload the demo video, run
`/feedback` in the primary Codex task for the session ID, decide whether to submit from this
branch or merge to `main` first, test-install from a clean clone, then submit the Devpost form
(Developer Tools track) — written in the user's own voice, not AI-generated, per Devpost's own
guidance. A separate, much bigger vision (universal browser-extension agent + multi-model
orchestration across Instagram/LinkedIn/Substack/X) was explicitly parked for post-submission —
see `docs/ROADMAP.md`'s new "Parked idea" section, not scoped or authorized. Full detail:
`docs/handoff/2026-07-17-openai-build-week/HANDOFF.md`.

## Previous state — 2026-07-15 (superseded)

All previously-shipped work is merged to `main` and pushed to `origin/main` (through commit
`1f8dacc`), 79/79 tests passing (still green as of 2026-07-15). Threads A/C/D/E complete. Thread F
(transcription thoroughness tiers) has an **approved but unimplemented** spec, still parked.
`docs/ROADMAP.md` (committed) has a sharpened Phase 2.5 (YouTube capture-adapter, next up, no code
yet) and 2.6 (Facebook, unscoped), a `docs/decisions.md` ADR log (4 entries), and a parked,
not-authorized follower-management-assistant idea. Repo is public, OSS-scaffolded
(LICENSE/CONTRIBUTING/PR+issue templates — only `CODE_OF_CONDUCT.md` missing), with 4 GitHub
issues open (#2 bug, #3 Thread F, #4 note-quality spot-check, #5 Phase 0 kickoff). Untracked
`.codex/` dir sitting in the working tree, uncommitted and not gitignored — unexplained, worth a
look next time.

**This session** (2026-07-15-deep-catch-up) was a read-only `deep-catch-up` orientation — no code
changes. Delivered the user a full briefing on: what read-video is/does, the ROADMAP's
already-captured feature vision (Phases 0-6 + parked follower-mgmt idea), an honest startup/moat
read (thin wrapper over ffmpeg/yt-dlp/whisper — the real differentiation is cost-gate+privacy+
agent-native UX, not the underlying tech; Phase 6 SaaS is explicitly the riskiest, least-validated,
legally-gated track per the ROADMAP's own framing, not proven demand), and scalability on two axes
(technical: no billing/multi-tenancy yet, Phase 0 capture/media interfaces not yet extracted;
legal/business: ToS-at-scale is the real ceiling, Phase 6.4 gate). No direction chosen yet — user
was offered YouTube-adapter planning, SaaS/legal feasibility research, or fixing issue #2 as next
moves. Full detail in `docs/handoff/2026-07-15-deep-catch-up/HANDOFF.md`.

**Prior session** (2026-07-09-mega-request-triage) triaged a huge multi-part `/gsd-ship` request:
confirmed most of it (repo/OSS scaffold, issues) was already done in a prior session; committed +
pushed 6 pending doc/command files; logged the follower-management-assistant idea as parked with
3 learn-from-only reference repos; then ran `grill-with-docs` to sharpen the "ideate 6-platform
workflows" ask into a concrete decision: the platform-expansion track is the consumption pipeline
(not the user's own publishing workflow), **YouTube is the next capture-adapter to spec** —
official YouTube Data API v3 (not browser automation), Watch Later as the source list, videos
removed from Watch Later on capture (mirrors IG's unsave-as-marker pattern), and Phase 0's
capture-adapter interface deferred until *after* YouTube ships (extracted from two real examples,
not designed upfront from one). Full rationale in `docs/decisions.md`. **No YouTube code exists
yet** — this was ideation only, next step is a `writing-plans` cycle when picked up. Still gated,
untouched from the original ask: `/ig-pipeline` re-run (needs live user), carousel/image-post
transcription skill (ROADMAP Phase 1.1, not authorized), follower-management assistant (deferred,
behind Phase 6.4's legal/ToS gate).

**Prior sessions' history (unchanged, for context):** built `/ig-pipeline` (orchestrator command +
`ig-analyze-subagent`) formalizing the IG capture→analyze flow; ran it live twice (45-reel batch,
then a 20-reel dispatch — one controller-side dispatch-slip caught both times by disk-diff
verification, a recurring failure class worth watching for in `/ig-pipeline` itself, see the
2026-07-05 session folder); reorganized the resulting 111-note vault into title-slugged,
category-sorted files with content-keyed (not filename-keyed) dedup; added a `/read-audio` command
and used it to transcribe two personal hackathon-brainstorm voice memos into a new vault project
folder. Full detail in each dated session folder below.

**GitHub issues** (`RikepilB/read-video`): #1 (commit pending docs) **closed this session**. #2
(pre-existing bug report), #3 (Thread F implementation), #4 (note-quality spot-check), #5 (roadmap
Phase 0 kickoff) — all still open.

## Session index
_(newest first)_

- **2026-07-17-openai-build-week** — implemented the approved Developer Tools extension on
  `codex/build-week-read-video`: adaptive transcription, model/cloud consent gates, GPT-5.6
  pricing/vision accounting, fixture, tests, README, and submission runbook; `103 passed` and real
  smoke flow green, but SkillSpector returned CRITICAL/DO NOT INSTALL and human submission steps
  remain. Later same session: committed (`b6b1c61`); ran `/code-review` (9 confirmed bugs) and
  `/ponytail-review`; ran `/plan` for production-readiness + presentation, approved and executed —
  fixed all 6 bugs with tests (103→111 passed), added `SECURITY.md` (SkillSpector accept+document),
  untracked root `handoff.md`, built and shipped a GitHub Pages landing page (live at
  rikepilb.github.io/read-video), caught and fixed a real bug via manual command verification
  (privacy-proof demo command), and drafted a demo shot list (recording still pending). Parked a
  separately-floated bigger multi-platform/multi-model vision in `docs/ROADMAP.md` per the user's
  own explicit "stay focused" instruction.
- **2026-07-15-deep-catch-up** — read-only orientation session (`deep-catch-up` skill), no code
  changes: delivered a full briefing covering read-video's capacities, the ROADMAP's captured
  feature vision, an honest startup/moat assessment, and technical+legal scalability read; no
  direction chosen, three next-move options offered (YouTube adapter plan / SaaS legal feasibility
  research / issue #2 fix).
- **2026-07-09-mega-request-triage** — triaged a mixed-scope `/gsd-ship` mega-request (found
  repo/OSS-scaffold/issues already done; committed+pushed 6 pending files; closed issue #1; logged
  a parked follower-management-assistant idea with 3 reference repos); then ran `grill-with-docs`
  to sharpen 6-platform ideation into a concrete YouTube capture-adapter design (Data API v3,
  Watch Later, remove-on-capture marker, Phase 0 interface deferred) — recorded in new
  `docs/decisions.md`; no code written, ideation + docs only.
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
