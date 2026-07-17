# Session Handoff — 2026-07-17-openai-build-week

## Goal
Implement the approved OpenAI Build Week Developer Tools extension for `read-video` while
preserving all pre-existing dirty work and withholding commits/pushes until explicitly authorized.

## What was done
- Renamed the working branch from `codex-fix-workspace-run-resolution` to
  `codex/build-week-read-video`; preserved every tracked/untracked pre-existing change.
- Stabilized the inherited work: fixed the `_transcribe` test double, restored the transcription
  tier design to clean UTF-8, resolved bare workspace filenames, and unignored `.env.example`.
- Completed adaptive local transcription (`auto` fast through 45s, thorough above 45s; explicit
  overrides; medium model, tuned VAD, `condition_on_previous_text=False`).
- Added estimate-time model cache status and explicit `run --allow-model-download` consent.
- Enforced the cloud privacy boundary: any Groq/OpenAI/OpenRouter/Gemini backend anywhere in a
  chain requires `run --allow-cloud`; rejection happens before media download/audio conversion.
- Added GPT-5.6 Sol/Terra/Luna rates, GPT-5.6 32×32 patch accounting, Claude estimator
  compatibility, `estimate --agent-model`, and API-equivalent billing labels.
- Added a deterministic generated fixture (`scripts/create-demo-fixture.py`), tests, a Build Week
  README section, and `docs/build-week-submission.md` with the 2:40 demo storyboard.
- Verified `python -m py_compile`, full `pytest` (`103 passed`), installer tests within the suite,
  `git diff --check` (no whitespace errors; LF→CRLF warnings only), and the real key-free smoke
  flow. The blocked OpenAI smoke created no `audio.mp3`.

## Files changed
- `.gitignore`, `.env.example` — make the safe environment template trackable.
- `skill/scripts/video.py`, `skill/pricing.json` — Build Week engine, gates, and GPT-5.6 pricing.
- `skill/SKILL.md`, `skill/references/backends.md`, `docs/cli-reference.md` — Codex consent and
  public interface contract.
- `README.md`, `docs/build-week-submission.md` — judged experience and submission runbook.
- `scripts/create-demo-fixture.py` — locally generated copyright-free video + sidecar.
- `tests/test_estimate.py`, `tests/test_frames.py`, `tests/test_transcribe_profiles.py`,
  `tests/test_privacy_gate.py`, `tests/test_demo_fixture.py` — regression and Build Week coverage.
- `docs/superpowers/specs/2026-07-03-transcription-thoroughness-tiers-design.md` — clean UTF-8 and
  updated consent-gate design.
- Pre-existing unrelated changes in `docs/ROADMAP.md`, `docs/decisions.md`,
  `skill/workspace.example.json`, `.codex/`, and the YouTube adapter plan were preserved and not
  folded into the Build Week implementation.

## Failed attempts
- `skillspector scan skill --no-llm` returned `100/100 CRITICAL — DO NOT INSTALL`. Its critical
  taint finding is the intentional environment API key → authenticated transcription request
  flow; it also flags external endpoints, subprocess use, undeclared permissions, and possible
  output/exfiltration patterns. No installation/distribution was performed after this result.
- No post–July 13 commit hash exists because commits/pushes were explicitly withheld. README and
  the runbook identify the pending evidence instead of inventing it.

## Next steps
- **Merge PR #7** (https://github.com/RikepilB/read-video/pull/7, 9 commits,
  `codex/build-week-read-video` → `main`) when ready. After merging/deleting the branch, re-point
  Settings > Pages from the branch to `main` — Pages currently serves from the branch specifically.
- **Record the demo video** against `docs/demo-shot-list.md` in OpenScreen (manual — the skill
  can't drive the recording). Need a real spoken clip >45s for beat 5 first.
- Run `read-video --tier visual` against the recording to review pacing/coverage beat-by-beat,
  iterate, then upload the <3-min public YouTube video.
- Run the full skill in the primary GPT-5.6 Codex task, submit `/feedback`, and replace the
  README/runbook's session-ID placeholder with the confirmed one.
- Test install from a clean clone.
- Submit Devpost (category: Developer Tools) by 2026-07-21, 5:00 PM PT.
- Tracked in GitHub issue #6 (https://github.com/RikepilB/read-video/issues/6).

## Update — later same session (post-commit)
- Working tree is now clean; commit `b6b1c61 feat: finish build week read-video plan` landed
  the Build Week scope (superseded the "commits withheld" note above).
- Ran `/codex:review` (no args) against `main...HEAD` (27 files, +1537/-89) — launched in
  background (task id `brtzh3mtk`) per user choice at the size-based prompt. Review-only, no
  fixes applied this turn. Check `/codex:status` for the result before further action.

## Update — production-readiness + presentation pass (same day, continued)

Ran `/code-review` (high effort, 8-angle finder + verify) on `main...HEAD`: 9 findings, all
CONFIRMED/PLAUSIBLE, all in the new cost/consent gate (sidecar bypass in `requires_cloud_approval`
and `run()`'s cloud check; a premature `RuntimeError` in `_faster_whisper` that skipped cached
fallback models; 3 agent-config docs not updated for `needs_model_download`; hardcoded
`Systran/faster-whisper-<model>` repo-id guess wrong for large/distil/turbo; `--agent-model`'s CLI
default overriding `pricing.json._active`; `DEFAULT_PRICING` missing two models). Then
`/ponytail-review` on the same diff (9 complexity/duplication findings, not applied — read-only).

User then ran `/plan` asking for production-readiness + a landing page + presentation materials
before the 2026-07-21 Devpost deadline. Plan approved (`~/.claude/plans/abstract-prancing-quilt.md`):
- **All 6 code-review bugs fixed** with regression tests (`pytest` 103 → 111 passed), across 3
  commits (`dd3c269`, `70f1a62`, plus doc/hygiene in `7d2534f`). Bug #2 (premature
  model-download raise) got the "real fix" per user's explicit choice — `_model_download_info`/
  `_model_available_locally` now check the full fallback chain, not just the requested model, so
  the gate only fires when nothing at all is cached.
- **SkillSpector CRITICAL** disposition: user chose accept-and-document. Added `SECURITY.md`
  explaining the flagged env-key→cloud-request flow is intentional and consent-gated; re-ran the
  scanner afterward to confirm the same `100/100 CRITICAL` root cause (TT3 tainted flow) matches
  the doc's claims.
- **Repo hygiene**: root `handoff.md` was tracked in git (an internal per-session artifact,
  superseded by this `docs/handoff/` tree) — `git rm --cached` + gitignored; the compaction hook
  still writes it locally.
- **Landing page**: `docs/index.html` built (loaded `frontend-design` skill first) — no external
  fonts/CDN (matches the project's local-first ethos; also what was silently hanging document-idle
  in this sandbox's Chrome extension during verification — screenshot capture itself is broken
  here, confirmed via `read_page`/`get_page_text` working fine while `computer screenshot` times
  out on CDP `Page.captureScreenshot`). Signature element: the cost gate rendered as a customs
  checkpoint stamp (`APPROVED $0.0392` / `HOLD — needs consent`) using real `estimate`/`run` JSON.
  Two case files (Instagram-vault pipeline, hackathon voice-memo) presented at the outcome level,
  no personal note content. Committed (`abb9a07`), pushed, **GitHub Pages enabled** (user chose
  "enable now" against this branch) — **live at https://rikepilb.github.io/read-video/**.
- **Real-command verification caught a real bug**: running the README's "privacy proof" command
  against `build-week-demo.mp4` no longer triggered the cloud gate — because the sidecar-bypass
  fix (bug #1 above) now correctly resolves it for free. Fixed by adding a `privacy-proof.mp4`
  copy (no sidecar) to the README/storyboard; verified end-to-end. Commit `00df10e`.
- **Demo video**: invoked `demo-showcase` skill. Recording/editing are entirely manual by design
  (OpenScreen/OpenVid have no CLI hook) — drafted and committed a 9-beat shot list
  (`docs/demo-shot-list.md`, commit `f0c5ac5`) adapting the existing 2:40 storyboard into exact
  commands + narration covering both Codex and GPT-5.6 usage per Devpost's requirement. Beat 5
  (fast vs thorough transcription) needs a **real spoken clip >45s that the user owns** — the
  synthetic fixture has no real speech; noted as a pre-recording prerequisite, not blocking.

All 6 commits on `codex/build-week-read-video` are pushed to origin. `pytest`: 111 passed.

## Update — Devpost reminder + parked vision (same day)

Devpost's automated halfway-point reminder arrived mid-session (deadline 2026-07-21 5PM PT).
Checked against it: repo is public (no share-with-testing@devpost.com needed), README documents
Codex+GPT-5.6 usage, project builds/runs (111 tests green). Still open: record the demo video
(shot list ready, recording is manual), retrieve the `/feedback` session ID, add Devpost team
members if any. Flagged explicitly to the user: the actual Devpost project name/description fields
should be written in their own voice, not by an agent — Devpost's own guidance says judges can
tell and penalize AI-written submission copy.

User separately floated a much bigger vision (universal browser-extension agent across
Instagram/LinkedIn/Substack/X, multi-model specialization — Gemini/Grok/GPT/open-source
orchestrator) but explicitly said to stay focused on the current submission and park the idea for
later. Logged as a new "Parked idea" section in `docs/ROADMAP.md` (commit `ee8fa94`), same pattern
as the existing follower-management-assistant entry — not scoped, not authorized, next step is
`grill-with-docs` when picked up post-submission.

## Update — handoff-to-issues + gsd-ship (same day, continued)

Ran `/handoff-to-issues`: harvested the remaining human-only next-steps into one grouped issue
(no code work left to harvest — all 6 bugs already fixed). Created label `user-action` (didn't
exist) and filed **issue #6** (https://github.com/RikepilB/read-video/issues/6) with a 9-item
checklist (record video, review, upload, `/feedback`, replace placeholder, merge-vs-branch
decision, clean-clone test, Devpost submit, own-voice description reminder). Did not touch this
handoff tree from that skill, per its read-only contract. Deliberately did not harvest the
newly-parked ROADMAP vision — out of that skill's declared source scope (HANDOFF.md +
current-session Next steps + LATER-TASKS.md only, not ROADMAP.md).

Ran `/gsd-ship`: this repo has **no GSD `.planning/` state** (`phase_found: false`,
`planning_exists: false`, confirmed via `gsd_run query init.phase-op`) — it uses this
`docs/handoff/` tree instead, not GSD's phase/plan/verify pipeline. Asked the user how to proceed;
chose "ship manually, GSD-style": ran the applicable preflight checks (clean tree, correct branch,
remote, `gh` auth — all pass), then hand-wrote a rich PR body from this session's actual commits/
tests/decisions (skipping GSD's PLAN.md/VERIFICATION.md-sourced sections and the TDD-audit
`gate_status` trailer, which don't apply to this repo's commit conventions). Created **PR #7**
(https://github.com/RikepilB/read-video/pull/7, `codex/build-week-read-video` → `main`, 9 commits).
User chose to skip an additional review round (already code-reviewed + ponytail-reviewed this
diff earlier). Did not merge — that's still the user's call.

## Files in this folder
- `HANDOFF.md` — this curated digest
- `transcript.md` — full `/export` of the session (if captured)
- `snapshot-<HHMMSS>.md` — auto git-snapshots written by the PreCompact hook, if any
