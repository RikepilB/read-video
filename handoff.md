# Goal
Thread A (active, near done): port upstream `bradautomates/claude-video` v0.2.0 into our `read-video` fork — frame dedup, Whisper API auto-chunking, `--timestamps`, argv hardening, pytest suite — per approved spec (`docs/superpowers/specs/2026-07-01-upstream-v020-port-design.md`) and 10-task plan (`docs/superpowers/plans/2026-07-01-upstream-v020-port.md`). Zero-cost path stays default; paid backends opt-in behind cost gate. Parked: thread C (agent-harness packaging), thread D (Instagram capture — design awaiting user go/no-go), thread B (media types).

## Current state
**Subagent-driven development, branch `upstream-v020-port`.** Authoritative ledger: `.superpowers/sdd/progress.md`. **Tasks 1-9 of 10 complete and reviewed clean** (commits 2e8518c, 2a83559, 5100e89, 9149f65, 9149f65..67070c7 (incl. fix), 17068d2, 6785532, 119f870, 3b50c3d). All runtime code for the port is DONE: dedup (3-5), pins (1,6), hardening (2), chunking (7-8), estimate note (9). **Task 10 (docs + spec fix + full-suite re-run + live-install sync — the FINAL task) is dispatched and running** (sonnet, agent aa1cdc334bb5f28ba, BASE=3b50c3d). It updates `skill/SKILL.md`, `docs/cli-reference.md`, `CREDITS.md`, fixes a spec inaccuracy (Gemini wrongly listed as chunking backend — Files API has no 25MB cap), re-runs `pytest -v` expecting all-pass, then copies `skill/scripts/video.py` + `skill/SKILL.md` to the live install `~/.claude/skills/read-video/` (must NOT touch `.env`/`workspace.json`/`load-env.ps1` there), then commits.

After Task 10 lands + reviewed: final whole-branch review (most capable model, `review-package $(git merge-base main HEAD) HEAD`, hand it all 9 tasks' ledgered Minor findings for triage — see ledger for full list, ~15 minors, all low-severity/brief-inherited), then `superpowers:finishing-a-development-branch` (merge decision is user's).

SDD flow per task: `task-brief PLAN_FILE N` → implementer → `review-package BASE HEAD` (BASE = commit before dispatch, never HEAD~1) → reviewer (sonnet) → fixes if Critical/Important → ledger line. Scripts: `C:\Users\a2021\.claude\plugins\cache\claude-plugins-official\superpowers\6.0.3\skills\subagent-driven-development\scripts\`.

## Files in flight
- `skill/SKILL.md`, `docs/cli-reference.md`, `CREDITS.md`, `docs/superpowers/specs/2026-07-01-upstream-v020-port-design.md` — Task 10 implementer editing (docs only, no runtime code).
- Live install `C:\Users\a2021\.claude\skills\read-video\scripts\video.py` + `SKILL.md` — about to be overwritten by Task 10's sync step (from already-tested repo `skill/` copies).

## Changed
Branch commits (all reviewed clean, zero Critical/Important across all 9 tasks): 6470f1f spec → b4c464e pin-overflow fix → 473c7be zero-cost constraint → 9cfd0a1 plan → 2e8518c T1 (scaffolding+`_parse_timestamp`) → 2a83559 T2 (Path.resolve hardening) → 5100e89 T3 (`_frame_delta`+`_dedupe_jobs`) → 9149f65 T4 (`_thumb_frames`) → 1141fde T5 (extraction wiring, conftest scene_clip green→lime fix) → 67070c7 T5-fix (frames_deduped default) → 17068d2 T6 (`--timestamps` pins) → 6785532 T7 (`_split_audio`/`_audio_duration`) → 119f870 T8 (chunked API transcription) → 3b50c3d T9 (estimate `note` + regression guard). 46/46 tests passing as of T9. SDD artifacts (untracked): `.superpowers/sdd/{progress.md, task-N-brief/report.md, review-*.diff}`.

## Failed attempts
- SkillSpector static scan of upstream = blanket 100/100 CRITICAL; useless verdict, manual review was resolution.
- CSS `green` in scene_clip fixture: luma byte-identical to red under gray conversion (both 76) — any luma dedup collapses them. Fixed with `lime` (150).
- Carried, unfixed by design (spec non-goals): `--backend captions` hard-errors despite probe `captions_available: true`; `run()` never applies inbox expansion to bare filenames; `_trx` argv not resolved (unreachable); luma-only dedup can't distinguish equal-brightness/different-chroma frames (upstream design limit, disclosed in fixture docstring); `_fmt_estimate` (--human CLI output) doesn't surface the new `note` key (JSON-only).

# Next steps
1. **Immediate**: await Task 10 completion notification → `review-package 3b50c3d HEAD` → dispatch reviewer (sonnet) → on approval, ledger "Task 10 complete" → mark all SDD tracker tasks done.
2. Final whole-branch review: most capable model, `review-package $(git merge-base main HEAD) HEAD`, feed it the ~15 accumulated Minor findings from the ledger for triage (none blocking so far).
3. `superpowers:finishing-a-development-branch` — merge decision is user's, present the reviewed branch for go/no-go.
4. Post-port items to surface to user: captions_available bug, inbox-expansion bug, luma-only dedup limitation, --human note visibility — none block merge, all are follow-up candidates.
5. Parked: thread C (agent-harness), thread D (Instagram capture, design awaiting go/no-go), thread B (media types).
