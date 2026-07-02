# Goal
Thread A (active): port upstream `bradautomates/claude-video` v0.2.0 into our `read-video` fork — frame dedup, Whisper API auto-chunking, `--timestamps`, argv hardening, pytest suite — per approved spec (`docs/superpowers/specs/2026-07-01-upstream-v020-port-design.md`) and 10-task plan (`docs/superpowers/plans/2026-07-01-upstream-v020-port.md`). Zero-cost path stays default; paid backends opt-in behind cost gate. Parked: thread C (agent-harness packaging), thread D (Instagram capture — design awaiting user go/no-go), thread B (media types).

## Current state
**Subagent-driven development, branch `upstream-v020-port`.** Authoritative ledger: `.superpowers/sdd/progress.md`. Tasks 1-4 complete + reviewed clean (commits 2e8518c, 2a83559, 5100e89, 9149f65). Task 5 (oversample+dedup wired into `_extract_frames`, `--no-dedup`, `--timestamps` CLI flag, `frames_deduped` in run JSON) implemented at commit 1141fde, 33/33 tests passing, reviewer APPROVED with one Important finding: `frames_deduped` key absent from run() JSON on audio-only tier (brief's own code gap; fix aligns with spec). **Fix subagent (haiku, agent a490186e55d2e9f00) dispatched and running**: one-line fix (default `"frames_deduped": 0` in base result dict) + monkeypatched audio-tier test, commit msg `fix: always include frames_deduped in run() output`, appends to task-5-report.md. After fix lands: re-review (review-package 9149f65 HEAD → sonnet reviewer), then ledger Task 5, then Task 6.

Task 5 notables: implementer changed `tests/conftest.py` scene_clip green→lime (deviation ruled SOUND by reviewer — CSS green and red have byte-identical luma 76 under ffmpeg gray conversion; lime=150 distinct). Luma-only dedup can't distinguish equal-brightness chroma-differing frames — inherited upstream design limit, disclosed in fixture docstring.

SDD flow per task: `task-brief PLAN_FILE N` → implementer (haiku tasks 6,7,9; sonnet 8,10) → `review-package BASE HEAD` (BASE = commit recorded before dispatch, never HEAD~1) → reviewer (sonnet) → fixes if Critical/Important → ledger line. Scripts at `C:\Users\a2021\.claude\plugins\cache\claude-plugins-official\superpowers\6.0.3\skills\subagent-driven-development\scripts\`. After Task 10: final whole-branch review (most capable model, `review-package $(git merge-base main HEAD) HEAD`, hand it ledger Minors for triage), then finishing-a-development-branch (merge = user's call).

## Files in flight
- `skill/scripts/video.py` + `tests/test_frames.py` — fixer subagent adding frames_deduped default + test (in progress).
- `.superpowers/sdd/task-5-report.md` — fixer appends fix section.

## Changed
Branch commits: 6470f1f spec → b4c464e pin-overflow → 473c7be zero-cost constraint → 9cfd0a1 plan → 2e8518c Task 1 (test scaffolding + `_parse_timestamp`) → 2a83559 Task 2 (Path.resolve hardening) → 5100e89 Task 3 (`_frame_delta` + `_dedupe_jobs`) → 9149f65 Task 4 (`_thumb_frames`) → 1141fde Task 5 (extraction wiring). SDD artifacts (untracked): `.superpowers/sdd/{progress.md, task-N-brief/report.md, review-*.diff}`.

## Failed attempts
- SkillSpector static scan of upstream = blanket 100/100 CRITICAL; useless verdict, manual review was resolution. Do NOT re-run expecting different.
- CSS `green` in scene_clip fixture: luma identical to red under gray conversion — any luma dedup collapses them. Use `lime`.
- Carried: `--backend captions` hard-errors despite probe `captions_available: true` — pre-existing bug, spec non-goal, surface to user post-port. Also pre-existing: run() never applies inbox expansion to bare filenames (Task 2 reviewer finding); `_trx` argv not resolved (unreachable).

# Next steps
1. **Immediate**: fixer completes → `review-package 9149f65 HEAD` → re-review (sonnet) → ledger "Task 5 complete" → `task-brief ... 6`, record BASE, dispatch Task 6 (`--timestamps` pin parsing in run(), haiku). Note for Task 6: fallback-to-filter path in `_extract_frames` silently drops pins (reviewer minor).
2. Tasks 7-10 same cycle. Then final whole-branch review + finishing-a-development-branch.
3. Post-port user items: captions_available bug, inbox-expansion bug, luma-only dedup limitation, copy `skill/` → live install (Task 10 covers).
