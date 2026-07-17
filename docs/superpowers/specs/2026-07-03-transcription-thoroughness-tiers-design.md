# Transcription Thoroughness Tiers — Design

**Date:** 2026-07-03
**Status:** Implemented 2026-07-17 on `codex-fix-workspace-run-resolution`. Kept here as the approved design record and acceptance checklist.
**Scope:** `_faster_whisper()` in `skill/scripts/video.py` only. No other backend, no frame-side
changes.

## Context

Found while spot-checking the IG capture-analysis batch (`2026-07-03-ig-capture-analysis-pipeline-
design.md`): transcripts for clips ≤~45s come out fully accurate; longer clips have omitted words/
phrases (not the full length), even though synopsis/notes/action-items still land fine because
frames + the partial transcript compensate.

Root cause (`skill/scripts/video.py:751-756`, `_faster_whisper()`): all-default Silero VAD params
(`threshold=0.5`, `min_speech_duration_ms=250`, `min_silence_duration_ms=2000`,
`speech_pad_ms=400`), default `model="small"`, and faster-whisper's default
`condition_on_previous_text=True` — a known Whisper long-form failure mode (word-dropping/text
drift), not a bug in this project's code. A live test video (98s, single clean speaker, no music
bed) transcribed completely despite being over the 45s line — reinforcing that **duration is a
proxy for audio complexity (music beds, quick cuts, multiple speakers), not the root cause
itself.** It's used as the routing signal anyway because it's cheap and knowable upfront (unlike
"is this audio complex," which isn't decidable before transcribing).

## Goals

1. Keep the existing fast path exactly as-is for short clips — it's already proven correct;
   nothing about it should change.
2. Give longer clips a higher-recall (slower, still $0 out-of-pocket) transcription path.
3. Decide routing automatically from something knowable before transcription runs (duration),
   not from something only knowable after (priority — which is assigned by the analysis step that
   reads the transcript, so gating on priority is a chicken-and-egg problem).
4. Keep an explicit override so a specific video can be forced either direction regardless of
   duration.

## Constraints

- No cloud spend — `thorough` must stay a local CPU path, same as `fast`. This is non-negotiable
  per `SKILL.md`'s cost-gate philosophy (never send audio to a paid API without explicit
  approval).
- No behavior change for any caller that doesn't hit the new threshold — existing callers/tests
  for `_faster_whisper()` on short clips must see identical output to today.
- Reuse the existing offline-first model-fallback chain (`_new_whisper`/candidates loop) rather
  than building a second one for the `thorough` model size.

## Non-goals

- Solving the actual root cause (audio complexity detection) — out of scope; duration is an
  accepted proxy, not a fix for the proxy's imprecision.
- Any change to the frame/visual side of the pipeline.
- Any change to API-backend transcription paths (Groq/OpenAI/OpenRouter/Gemini) — this is
  local-whisper-only.
- Retroactively re-transcribing the 41 already-processed IG videos — a separate decision for
  whoever picks this spec up to implement, not part of this design.

## Architecture

Two named profiles inside `_faster_whisper()`, selected by audio duration:

| | `fast` (≤45s, default, **unchanged**) | `thorough` (>45s) |
|---|---|---|
| Model | `"small"` | `"medium"` (one-time local download via existing fallback chain) |
| `condition_on_previous_text` | `True` (library default, untouched) | `False` (avoids long-form repetition/drift) |
| VAD params | library defaults (`min_silence_duration_ms=2000`, `speech_pad_ms=400`) | tuned: `min_silence_duration_ms=500`, `speech_pad_ms=300` (less aggressive merging, less risk of clipping words at segment boundaries) |

**Threshold:** 45s literal (the user's own empirical boundary from real IG-batch review),
configurable via `workspace.json`'s `transcription_thorough_threshold_s` (falls back to the
hardcoded default if unset — preserves the "no `workspace.json` → behaves exactly as before"
guarantee `SKILL.md` already promises).

**Cost-gate integration:** no new mechanism. `estimate` already reports `needs_install`; the
first `thorough` run on a machine without `medium` cached trips that flag through the existing
path. Runtime cost is slower (bigger model, CPU) but still $0 out-of-pocket.

**Override:** `--transcribe-mode fast|thorough` flag on `estimate`/`run`, wins over the duration
default in either direction.

## Error handling

- Duration unknown/`probe` fails → default to `fast` (never silently assume the costlier path).
- `medium` unavailable for `thorough` → same fallback chain already in `_faster_whisper()` (tries
  candidates, prints a `WARNING`, degrades to `small`) — no new failure mode to build.
- Old faster-whisper without `vad_parameters` support → same existing
  `except (TypeError, ValueError)` catch already in the code, degrades to plain `transcribe()`
  (loses VAD tuning, still works, doesn't crash).
- `--transcribe-mode` override always wins — no conflict state is possible by construction.
- No `workspace.json` → hardcoded 45s default, same as today's "no config → unchanged behavior."

## Testing

Unit (following `tests/test_hardening.py` conventions):
- `_transcribe_profile(duration_s, threshold, override)` — fast/thorough/override-wins cases.
- `_faster_whisper` kwargs-per-profile — mock `model.transcribe`, assert `fast` passes today's
  defaults unchanged, `thorough` passes `model="medium"`, `condition_on_previous_text=False`, the
  tuned `vad_parameters` dict.
- Threshold override via `workspace.json`/env, same pattern as the existing `_whisper_settings()`.
- Degrade path when `vad_parameters` kwarg is unsupported by an older library version.
- CLI flag parsing (`--transcribe-mode`) on `estimate`/`run`.

**Not unit-testable, called out explicitly rather than hidden:** whether transcripts actually get
*more complete* under `thorough` is empirical — you can't assert "this is now the true content of
the audio" from inside a unit test. Acceptance test, when this gets implemented: re-run `thorough`
against 2-3 of the already-known-incomplete videos from the 41-video IG batch and manually compare
completeness before/after — same acceptance philosophy as the Instagram capture pipeline itself
(dry-run + watched live run, not automated assertions, for the parts that are inherently
real-world-dependent).

## Credits

No third-party code. Builds entirely on `faster-whisper`'s existing (already-vendored) API surface
— `model.transcribe(..., vad_filter=True, vad_parameters={...}, condition_on_previous_text=...)` —
and the model-fallback chain already shipped in `_faster_whisper()`/`_new_whisper()`.
