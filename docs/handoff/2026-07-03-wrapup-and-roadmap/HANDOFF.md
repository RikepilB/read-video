# Session Handoff — 2026-07-03-wrapup-and-roadmap

## Goal
Continue from a prior compacted session: resolve Thread D/E open decisions, diagnose+design a fix
for a transcription-completeness gap found during quality review, wrap up and ship everything to
`main`/`origin`, and capture the user's long-term multi-platform product vision as a roadmap.

## What was done
- User resolved two open decisions: Thread D Task 5 (live capture run) counts as **done** despite
  not matching the original controller-watched-run design; Thread E (IG analysis pipeline) gets a
  **retro spec** written.
- User flagged a real quality finding while reviewing Thread E's output: transcripts on clips
  >~45s omit words/phrases; ≤45s clips are fully accurate.
- Diagnosed root cause: `skill/scripts/video.py:751-756`, `_faster_whisper()` — all-default Silero
  VAD params + default `condition_on_previous_text=True` + `model="small"`, a known Whisper
  long-form failure mode, not a code bug.
- Ran `superpowers:brainstorming` for a fix: duration-routed `fast`(≤45s, unchanged)/`thorough`
  (>45s: bigger model, tuned VAD, `condition_on_previous_text=False`) transcription profiles,
  threshold configurable, cost-gate reuses existing `needs_install`, `--transcribe-mode` override.
  User approved the design.
- Test-read one video live (`https://www.instagram.com/p/DaR7Ycjj5e7/`, 98s) end-to-end
  (`probe→estimate→run`), then on request saved it into the vault as `ig-DaR7Ycjj5e7.md` (rated
  High) + appended to `_ig-index.md` — reused the already-read transcript/frames, no re-extraction.
- Wrap-up (user: "test, commit, push, prepare the repo for open source"):
  - Found and fixed a mismatch: user assumed "design approved" = shippable, but Thread F had zero
    code. Surfaced this plus two other gaps (branch never merged, stray sensitive/scratch files)
    before doing anything, via `AskUserQuestion`. All three resolved with the recommended options.
  - `.gitignore`: added patterns for session-transcript exports and `task-*-brief/report.md` SDD
    scratch files (protected from ever being committed, left on disk).
  - Deleted `docs/branding.md` (100% unfilled TODO stub, not applicable to this repo).
  - Rewrote `.claude/rules/read-video-architecture.md` — was a generic web-app/DB template that
    never matched this repo's real single-file-CLI-engine shape.
  - Wrote `docs/superpowers/specs/2026-07-03-ig-capture-analysis-pipeline-design.md` (Thread E
    retro spec) and `docs/superpowers/specs/2026-07-03-transcription-thoroughness-tiers-design.md`
    (Thread F, marked **approved, not implemented — parked**).
  - Ran full test suite (79/79 passing), merged `instagram-capture-pipeline` → `main`
    (fast-forward, no conflicts), deleted the merged branch, pushed to `origin/main`
    (`46504b1..9dc030b`, then `9dc030b..6957013` for the final handoff commit).
- Wrote `docs/ROADMAP.md` — long-term vision: generalize into a multi-platform
  (IG/X/TikTok/LinkedIn/Substack) × multi-media (image/audio/text) pipeline, packaged for three
  audiences (technical repo, AI-agent skill bundles/MCP, non-technical UI/hosted SaaS). Explicitly
  planning-only; Phase 0 (generalize capture-adapter + media-reader interfaces) is the
  prerequisite; Phase 6 (SaaS) has a hard legal-review gate. **Left uncommitted** — user's call.
- Initialized this `docs/handoff/` tree (this session) — repo previously used only the legacy
  flat root `handoff.md`.
- **New ask this session: "do 45 more saved videos" + "make a command for that pipeline."**
  Diagnosed via disk-diff that `urls.md`'s 45 existing URLs were all already processed (46
  `ig-*.md` notes on disk, one per shortcode) — so "45 more" means capturing brand-new reels from
  the live "Cursos" collection, not reprocessing.
  - Confirmed with user: command name `/ig-pipeline` (not `richard-igpipeline` — shorter, matches
    existing `/instagram-capture` naming), and rollout **5 live first, inspect, then the rest**
    (not all 45 at once) — matches the retro spec's own validated 5-then-scale approach, catches a
    command bug before 45 live unsaves instead of after.
  - Built `.claude/commands/ig-pipeline.md` — orchestrator: parses `N`/`--dry-run`, resolves
    `workspace.json` paths, resolves `READ_VIDEO_YTDLP_COOKIES` (session env, falling back to the
    persisted Windows user-level value via `[Environment]::GetEnvironmentVariable` — never scans
    for a cookies file itself, per the repo's credential boundary), dispatches
    `instagram-capture-subagent` (unchanged, reused), then disk-diffs `urls.md` shortcodes against
    existing `ig-*.md` filenames to build a dedup'd analysis queue, wave-dispatches (~5 concurrent)
    the new `ig-analyze-subagent`, and appends index rows itself (subagents never write the index
    — same concurrency-safety rule as the retro spec).
  - Built `.claude/agents/ig-analyze-subagent.md` (new) — formalizes the retro spec's ad-hoc
    per-video subagent into a real, reusable agent: per-video dedup guard (skip if
    `ig-<shortcode>.md` already exists), per-video cost-gate check on `estimate` before `run` (even
    though the batch itself was pre-approved), explicit cookie export in every `Bash` call (no
    reliance on env inheritance — this bit the project earlier this session), skip-marker template
    for non-video/fetch-failure/needs_install cases.
  - Ran `pytest` — 79/79 still passing (no `video.py` changes, pure new prompt files).
  - Resolved `cookies_path` for this run:
    `...\06_Media\www.instagram.com_cookies.txt` (read back from the persisted user env var, not
    discovered by scanning).
  - **Stopped here, mid-task**, to get the required "confirm you're watching" go-ahead before the
    first live capture dispatch (skill's own rule for any live/non-dry-run browser run) — the
    user's next message was `/handoff-context` instead, so the live 5-video run has **not yet been
    dispatched**.
- User ran `/handoff-to-issues` — harvested this tree's pending next-steps into GitHub issues on
  `RikepilB/read-video` (read-only on the tree itself, per that skill's contract):
  - Created **#3** "Implement transcription thoroughness tiers (Thread F)" (`enhancement`).
  - Created **#4** "Spot-check auto-generated Instagram note quality" (`tech-debt` — new label).
  - Created **#5** "Kick off Phase 0 of the multi-platform roadmap" (`enhancement`) — absorbs the
    previously-parked "Thread B: extend media types."
  - Updated stale **#1** ("Commit pending handoff.md") — its named file is already committed; body
    now lists the current uncommitted set instead.
  - Deduped against existing #1/#2 first (`gh issue list`) — no duplicates created. The
    "dispatch the live 5-reel run" and "run `/export`" next-steps were deliberately **not** filed
    as issues — they're immediate interactive/manual actions, not standing backlog.
- **Ran the `/ig-pipeline` checkpoint (live, user confirmed watching):** captured 5 reels from
  "Cursos" (`DaV-yKcpt-m`, `DaR7Ycjj5e7`, `DaS-IcjjqNt`, `DY7OVZCti8P`, `DaUJVC6RcB8`) via
  `instagram-capture-subagent`, unchanged. One (`DaR7Ycjj5e7`) was the session's earlier test
  video — the new `ig-analyze-subagent`'s dedup guard correctly skipped it (note already existed).
  Wave-dispatched 4 `ig-analyze-subagent`s in parallel for the rest; all 4 succeeded (local
  `faster-whisper`, `free: true`/`needs_install: false` throughout, cookie export held with no
  inheritance failures) — 2 High, 2 Medium. Controller (me) appended all 4 rows to `_ig-index.md`
  after each returned; subagents never touched the index (concurrency rule held). **First real
  validation of the new command+subagent — worked end to end with no bugs found.** Net 4 of the
  "45 more" target reached (1 slot was a dup); ~41 still remain.
- User said "Continué" (continue) — skipped inspection, went straight to the rest. Dispatched
  `instagram-capture-subagent` live again for `N=41` (no re-confirmation needed — "watching"
  already confirmed once this session, per the skill's own "first time this session" rule).
- **Capture returned: all 41 succeeded**, no aborts, no dedup hits this time (unlike the 5-video
  checkpoint's one dup). One process hiccup the capture subagent self-corrected: the saved-grid's
  masonry layout made direct tile-clicks unreliable, so it switched to navigating each reel by its
  already-extracted `/p/<shortcode>/` URL and unsaving from there — still real extracted links,
  not guessed ones. `urls.md` now has 97 lines total.
- **Analysis wave in progress, steady-state working well.** Refill loop (append index row on
  completion → pop next shortcode off the disk queue → dispatch replacement, keep ~5 in flight) has
  been running cleanly for many rounds. **25 of 41 processed as of this handoff write** (21
  analyzed into `ig-*.md` notes + index rows, 4 correctly skip-marked — 1 genuine probe-error
  skip on `DZM3rU9CUyD` where the real yt-dlp error is masked by `video.py`'s 200-char stderr
  truncation, 3 confirmed image-carousel posts saved under `/reel/`-shaped URLs). 11 shortcodes
  remain queued on disk at
  `...\scratchpad\ig-pipeline-queue-remaining.txt` (session scratchpad dir under
  `C--Users-a2021-...-read-video\47c4edb2-d531-486c-a23a-1ad71934c632\scratchpad\`), 5 more
  in flight. If this session breaks mid-batch, the true remaining queue is always recoverable via
  disk-diff (`ig-*.md`/skip-marker files present in `out_dir` vs. shortcodes in `urls.md`'s last 41
  appended lines) — don't trust any in-conversation tally over that diff. Notable finds worth a
  look later (not urgent): one reel (`DZtV5O1JJw6`) benchmarks a competing skill called "Ponytail"
  against the user's own installed `caveman` skill; another (`DaSlJLruJf4`) reports a critical
  libssh2 CVE — both are just cataloged content, no action taken on either.
- **Batch completed and fully verified.** All 41 finished: 36 analyzed, 5 correctly skip-marked
  (4 confirmed non-video image carousels saved under `/reel/`-shaped URLs, 1 genuine probe error
  masked by `video.py`'s 200-char stderr truncation). **One real bug caught by the disk-diff
  discipline itself**: a manual queue-pop/dispatch bookkeeping slip on the controller's part
  (mine) silently skipped `DZqSEroyiLt` mid-batch — never a subagent or engine defect. Caught by
  running the final "compare `urls.md` shortcodes vs. `out_dir` note/marker files" verification
  before declaring done (exactly the practice this project already adopted after the 46-vs-45
  miscount in an earlier session) — dispatched it as the 41st/last item, verified again after, 0
  missing. Combined with the 5-video checkpoint (4 net-new + 1 dup), this session captured and
  processed **all 45 requested reels**: 40 new vault notes, 5 legitimate skips, `_ig-index.md` now
  at 85 data rows. `urls.md` unchanged going forward (still has all 97 lines — capture-side only
  ever appends, analysis-side is what tracks "handled" via note/marker files).

## Files changed
- `.gitignore`, `.claude/rules/read-video-architecture.md` — committed (`f26d2d8`).
- `docs/superpowers/specs/2026-07-03-ig-capture-analysis-pipeline-design.md`,
  `docs/superpowers/specs/2026-07-03-transcription-thoroughness-tiers-design.md` — committed
  (`9dc030b`).
- `handoff.md` (legacy root file) — committed (`6957013`); now superseded by this tree going
  forward, left in place as historical record for the pre-tree sessions (upstream port,
  agent-harness packaging, Instagram capture — 2026-06-30 through 2026-07-02).
- `docs/ROADMAP.md` — written, **not committed**.
- `docs/handoff/` tree (this file, `_meta/TEMPLATE.md`, `.current-session`) — new, not yet
  committed.
- `.claude/commands/ig-pipeline.md`, `.claude/agents/ig-analyze-subagent.md` — the formalized
  capture+analyze pipeline command, now updated again (vault-reorg turn) for content-keyed dedup +
  category-folder writes. **Not yet committed.** No test coverage exists or is expected
  (browser/agentic orchestration, same as `/instagram-capture`).
- Outside the repo (vault, not git-tracked): `ig-DaR7Ycjj5e7.md` + one `_ig-index.md` row (from the
  earlier test-read); then, vault-reorg turn — all 111 `Transcripts/ig-*.md` files renamed+moved
  into 9 category subfolders + `_Skipped`, `_ig-index.md` fully rebuilt (grouped, 111 rows, gap
  fixed), new `_rename-manifest.tsv` (audit trail, since this vault has no git history of its own).
- GitHub (not a repo file, but repo-scoped state): issues **#3**, **#4**, **#5** created; **#1**
  updated. New label `tech-debt` created on `RikepilB/read-video`.

## Failed attempts
- `yt-dlp --cookies-from-browser chrome` fails on Windows (DB lock) — fixed via `cookies.txt` +
  `READ_VIDEO_YTDLP_COOKIES` env var instead (commit `c23912a`, prior session).
- Manual queue tracking by memory drifted once (miscounted 46 vs 45) — fixed via disk-diff
  (`comm -23`), now standing practice for any future batch work.
- A background agent was resumed live by the user before a fetch-gate was verified — worked out,
  but flagged as a real conversational-only-gate gap; no code-level fix built (only matters if it
  recurs).
- **Recurred this turn, same failure class**: manually tracking "which wave slot is running/next
  in queue" across many notification-driven dispatch/refill cycles silently dropped item 13 of 20
  (`DYHfiH0Csdl`) — never dispatched, no error, just missing from the running set. Caught again by
  the standing disk-diff practice before declaring done, not by noticing during the dispatch loop
  itself. This is now a **twice-observed pattern**, not a one-off: manual notification-driven
  wave-refill bookkeeping is unreliable at ~15-20+ items; the mandatory final disk-diff is the real
  safety net, not the controller's live tracking. Worth considering for `/ig-pipeline` itself: the
  command's own spec (step 5) already puts this diff on the controller per-completion, but doesn't
  mandate a final full-queue-vs-disk sweep before the "final report" step — that gap is what let
  both incidents reach the same point (mid-batch, not just at the end) before being caught.

## What was done (continued, same session — new turn)
- User ran `/ig-pipeline 20` — first-ever **live** dispatch of the formalized command (the earlier
  45-reel batch this session was done manually, before the command existed).
- Capture phase: `instagram-capture-subagent` captured 20 net-new reels into `urls.md`, unsaved
  each (bookmark-icon-confirmed), verified via grid reload. 0 duplicates, 0 aborts.
- Analysis queue built via disk-diff (`comm -23` captured-shortcodes vs. existing `ig-*.md` files
  in vault, which had grown to 91 notes) — all 20 captured shortcodes were net-new, so queue = 20.
- Analysis phase: ran to completion across the session (wave-of-5 concurrent `ig-analyze-subagent`
  dispatches, controller refilling each slot as it freed). **All 20 processed, 0 skips** (18 High/
  Medium touching AI-agent tooling / programming / job-hunting domains, 2 Low off-topic but still
  fully noted per the "Low still gets a full note" rule). `_ig-index.md` grew from 93 → 107 rows
  (105 data rows now, was 85 before this turn).
- **One controller-side bookkeeping slip caught and fixed, same failure class as a prior session's**
  (see Failed attempts): `DYHfiH0Csdl` (item 13 of the 20-item queue) was silently never dispatched
  during manual wave-refill tracking. Caught by running the standing disk-diff-verification
  practice (`comm -23` full 20-item queue vs. `out_dir`'s actual `ig-*.md` files) before declaring
  done — found the 1 gap, dispatched it, re-ran the diff clean (0 missing), then appended its row.
  Vault now at 111 notes total (91 pre-existing + 20 from this run).

## What was done (continued, same session — vault reorg turn)
- User asked (new session, after a `/compact`): rename the 111 `ig-<shortcode>.md` notes to
  intuitive, unique, title-based filenames, and organize them into topic subfolders.
- **Blocked first, correctly:** `advisor` flagged that a naive rename breaks `/ig-pipeline`'s
  dedup — its step 4 globs `<out_dir>/ig-*.md` and reads the shortcode from the *filename*; renaming
  drops that glob to zero matches, so the next run would re-queue and re-analyze all 111 videos.
  Read one note first — confirmed the shortcode is already recoverable from each note's own
  `Source:` line, so dedup can key off file content instead of the filename. This unblocked a
  clean-title-only naming scheme.
- Asked the user two `AskUserQuestion`s before touching anything: naming style (clean title-slug
  only, dedup via the `Source:` line — chosen) and category taxonomy (9 categories derived from
  scanning all 111 synopses, plus a `_Skipped` bucket — chosen as proposed).
- **Found a second, unrelated bug via ground-truth disk read** (didn't trust `_ig-index.md`'s row
  count): dumped every `ig-*.md` file's real title/Source/Priority from disk and found **111 files
  but only 105 indexed rows** — 6 files (1 real note, `DY-fxk3BnB3` "Storytime: Selling a Website
  She Didn't Know How to Build, Using Claude Code", + 5 skip-markers) were never added to
  `_ig-index.md` at all, a latent gap from the pre-command manual 45-reel batch. Folded all 6 into
  the rebuilt index while reorganizing rather than leaving them orphaned.
- Wrote a one-off Python script (`reorg_ig_vault.py`, scratchpad) with a hand-classified
  shortcode→category mapping (all 111 judged individually against the 9 categories, not
  keyword-matched) that: slugifies each title, moves the file into
  `<out_dir>/<Category>/<slug>.md`, writes `_rename-manifest.tsv` (old→new, for audit — this vault
  isn't git-tracked, so this is the only undo trail), and rebuilds `_ig-index.md` grouped by
  category (`## <Display Name>` sections, each priority-sorted).
- **Verified before and after moving anything:** pre-move, confirmed the mapping's 111 shortcodes
  exactly matched the 111 files on disk (no typos, nothing missed) before running; post-move,
  confirmed per-category file counts summed to 111, confirmed the 6 non-`ig-*` pre-existing
  transcripts in the folder root (unrelated `video.py` runs, not this pipeline's output) were
  untouched, and read back the rebuilt index to eyeball formatting.
- Updated `.claude/commands/ig-pipeline.md` and `.claude/agents/ig-analyze-subagent.md` so future
  runs match this scheme instead of regressing to flat `ig-<code>.md` files: dedup is now a
  recursive content search for the shortcode in each note's `Source:` line (not a root-level
  filename glob); the subagent classifies a category (same fixed 9 + `_Skipped`) alongside
  priority and writes directly into `<out_dir>/<Category>/<slug>.md`; the controller's index-append
  step now inserts into the matching category's `## <Display Name>` section (creating it in fixed
  order if new) instead of one flat table.

## Next steps
1. **Vault reorg is done.** All 111 notes renamed to title-slugs and sorted into 9 category
   folders + `_Skipped`; `_ig-index.md` rebuilt grouped by category (now 111 rows, the 6-row gap
   fixed); `_rename-manifest.tsv` written for audit. `/ig-pipeline` command + subagent updated in
   lockstep so the next live run writes into this same structure instead of breaking it. **Not yet
   verified against a live run** — worth a small (`N=1`–`2`) `/ig-pipeline` dispatch next time
   before trusting the new dedup/category-append logic at full batch size.
2. **`/ig-pipeline 20` is done.** All 20 requested reels captured + processed (18 High/Medium
   notes touching stated interest domains, 2 Low but still fully noted, 0 skips), disk-diff
   re-verified clean after catching and fixing one controller-side dispatch slip mid-batch.
   Nothing pending on this thread unless the user asks for more.
3. Previously: **first 45-reel `/ig-pipeline` batch is done.** All 45 requested reels captured +
   processed (40 new notes, 5 legitimate skips), fully disk-diff-verified. Nothing pending on that
   batch.
4. Decide whether to commit `docs/ROADMAP.md`, the `docs/handoff/` tree, and the updated
   `.claude/commands/ig-pipeline.md` + `.claude/agents/ig-analyze-subagent.md` — tracked in
   GitHub issue **#1** (file list there is now stale re: the pipeline files' new content, not just
   their existence).
5. **Thread F** now tracked as GitHub issue **#3** — read the spec, go straight to `writing-plans`
   (design pre-approved) on a new `feat/transcription-thoroughness-tiers` branch.
6. **Note-quality spot-check** now tracked as GitHub issue **#4** — with 111 notes now correctly
   indexed and categorized, this is a good time to also sanity-check a few category assignments
   (hand-classified in one pass, not re-verified).
7. **Roadmap Phase 0 kickoff** (absorbs the old parked Thread B) now tracked as GitHub issue **#5**
   — needs its own `brainstorming` cycle when picked up, not a continuation of this session.
8. Remind the user to run `/export docs/handoff/2026-07-03-wrapup-and-roadmap/transcript.md` if
   they want the full raw session archived next to this digest — I can't run `/export` myself.

## Files in this folder
- `HANDOFF.md` — this file.
- `transcript.md` — not yet captured; user needs to run `/export` (see Next steps #6).
