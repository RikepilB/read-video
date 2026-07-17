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
- User must review the SkillSpector report and decide whether to accept/document the intentional
  cloud capability, remove it from the submission, or authorize a scanner-focused remediation.
- Manually compare fast vs thorough transcripts on 2–3 original >45-second videos.
- After explicit authorization: create dated post–July 13 commits containing only the Build Week
  scope, then test installation and fixture flow from a clean clone.
- Run the full skill in the primary GPT-5.6 Codex task, submit `/feedback`, and replace the README/
  runbook placeholder with the confirmed session ID.
- Record/upload the <3-minute public demo and complete Devpost by July 21, 2026, 5:00 PM PT.

## Files in this folder
- `HANDOFF.md` — this curated digest
- `transcript.md` — full `/export` of the session (if captured)
- `snapshot-<HHMMSS>.md` — auto git-snapshots written by the PreCompact hook, if any
