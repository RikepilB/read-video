# Upstream v0.2.0 Port — Design

**Date:** 2026-07-01
**Status:** Approved (design); spec pending user review
**Scope:** Port selected features from `bradautomates/claude-video` v0.2.0 into `skill/scripts/video.py`

## Context

`read-video` forked its frame/caption logic from `bradautomates/claude-video` (MIT) at ~v0.1.x.
Upstream released v0.2.0 on 2026-07-01 with features our fork lacks. This spec ports the ones
that fit our architecture and skips the ones that would regress it.

Security note: a SkillSpector static scan of the upstream repo scored 100/100 CRITICAL.
Manual review of all 61 findings showed they are pattern-matches inherent to any media tool
(subprocess calls to ffmpeg/yt-dlp, audio uploads to transcription APIs, config-file reads);
the two highest-signal findings (`dev-sync.sh:43`, `hooks/scripts/check-setup.sh`) were
hand-verified benign. The user approved proceeding on 2026-07-01 with an algorithm-only port:
we vendor hand-reviewed algorithm code only, and never port upstream's session hook,
`setup.py` installer, or `.env` config reader. Scan record: session scratchpad
`claude-video-scan.json`.

## Goals

1. **Frame deduplication** — stop spending the frame budget on held slides and static screens.
2. **Whisper API auto-chunking** — remove the ~50-minute ceiling on paid API transcription.
3. **`--timestamps`** — exact-moment frame grabs.
4. **Subprocess hardening** — `Path.resolve()` before ffmpeg/ffprobe argv (upstream issue #2).
5. **Test suite** — pytest, no network, ffmpeg-synthesized fixtures. The fork currently has zero tests.

## Constraints

- **The zero-cost path is the default and must always remain fully functional**: URL captions and
  local `faster-whisper` cover the free case end to end, with no API key present. Paid backends
  (Groq / OpenAI / Gemini, via the user's env-var keys) remain strictly opt-in behind the
  existing cost gate — nothing in this port may route audio to a paid API without the gate.

## Non-goals

- **Scene-aware frame selection / `--detail` dial.** Upstream's `balanced` mode full-decodes the
  entire video to find scene cuts. Our fast-seek extraction (wall-clock scales with frame count,
  not duration) is the fork's headline perf win; full-decode would undo it. Oversample+dedup
  captures most of the value without it. Revisit only if dedup proves insufficient on real inputs.
- **Upstream's config system** (`~/.config/watch/.env`, session-start hook, `setup.py` installer).
  Our fork deliberately reads keys from real environment variables only (`references/backends.md`).
- **The `captions_available` probe bug** (probe says captions exist, `run --backend captions`
  hard-errors). Known, separate defect; fix is not part of this port. Tracked in `handoff.md`.
- **Self-contained skill packaging for other harnesses** (thread C). Separate future spec.

## Architecture

All runtime changes land in `skill/scripts/video.py` — the single-file CLI stays. A new `tests/`
directory at the repo root holds the pytest suite. Zero new dependencies: dedup thumbnails are
produced by one extra ffmpeg pass (upstream's pure-stdlib approach), not Pillow.

CLI surface: `probe / estimate / run` unchanged. `run` gains two flags:

- `--timestamps T1,T2,…` — pin frames at absolute times (`SS`, `MM:SS`, or `HH:MM:SS`, optional `.ms`).
- `--no-dedup` — disable the dedup pass.

Development happens in the repo; `skill/` is copied to the live install
(`~/.claude/skills/read-video/`) only after tests pass.

## Components

### 1. Oversampled extraction + perceptual dedup

- Extraction oversamples: `candidates = min(2 × frame_budget, duration × 2 fps)` frames via the
  existing parallel fast-seek mechanism (unchanged code path, larger count).
- One ffmpeg pass renders the candidate JPEG sequence to 16×16 grayscale rawvideo
  (`-vf scale=16:16,format=gray -f rawvideo`); the raw stream is sliced into one 256-byte
  thumbnail per frame.
- Greedy pass drops any frame whose mean absolute per-pixel difference from the last **kept**
  frame is ≤ 2.0 (0–255 scale). Mismatched thumbnail lengths are treated as maximally different
  so a decode hiccup never collapses distinct frames.
- If survivors still exceed the budget, even-sample down to the budget.
- Dropped JPEGs are deleted; survivors are reindexed `frame_0001…` and the manifest is rebuilt
  so frame→timestamp mapping stays exact.
- `run` JSON output gains `frames_deduped` (count of near-duplicates dropped).

### 2. Whisper API auto-chunking

Applies to the OpenAI-compatible paid backends only (`groq`, `openai`, `openai-mini`, `openrouter`); Gemini's Files API has no 25 MB cap so it stays unchunked, and local
`faster-whisper`/`trx` read media directly and never chunk.

- After the existing mono 64 kbps mp3 encode, if the file exceeds the 25 MB upload cap:
  split with ffmpeg into evenly sized chunks, each under the cap.
- Each chunk is transcribed with the existing per-request retry logic.
- Segment timestamps are shifted by the chunk's start offset back into source time, then merged.
- Partial failure is tolerated: a failed chunk becomes a
  `[transcription gap: chunk N of M failed]` marker in the transcript. The backend hop errors
  only if **every** chunk fails.
- Backend chaining semantics preserved: chunking happens inside each hop; if all chunks fail the
  hop fails and the chain falls through to the next backend. Audio is encoded once and reused
  across hops (existing behavior).

### 3. `--timestamps`

- Parses each entry as `SS`, `MM:SS`, or `HH:MM:SS` (optional fractional seconds).
- Each timestamp becomes a pinned frame: fast-seeked exactly, reserved against the frame budget,
  never dropped by dedup, marked `"pinned": true` in the manifest.
- Out-of-range timestamps (beyond duration) are skipped with a stderr warning; the run continues.
- Pins count against the frame budget. If the pin list alone exceeds the budget, the first
  `budget` pins (in timestamp order) are honored and the rest are skipped with a stderr warning.

### 4. Subprocess hardening

- All local media paths are passed through `Path.resolve()` before being placed in
  ffmpeg/ffprobe argv, so a relative path starting with `-` cannot be parsed as a flag.
- yt-dlp needs no change: `URL_RE = ^https?://` (video.py:42) already guarantees only
  `http(s)://`-prefixed strings reach yt-dlp, which cannot be option-injected.

### 5. Estimate behavior

- Dollar math unchanged. The gate prices the **full** frame budget (worst case), staying
  conservative — dedup can only reduce the real frame count.
- `estimate` output gains a note that dedup may reduce actual frames below the budgeted count.

## Data flow

`run`: input → (URL? download) → duration → frame budget **B** → extract
`C = min(2B, duration × 2fps)` candidates in parallel → thumbnail pass → greedy dedup → merge
pinned `--timestamps` frames → if > B, even-sample down → reindex + manifest → done.

Audio: sidecar / captions / local whisper paths unchanged. API path: encode mp3 → size check →
(over cap? chunk) → transcribe per chunk with retries → shift + merge → `transcript.txt`.

## Error handling

- **Dedup is fail-open.** Any thumbnail-pass error (ffmpeg failure, unparseable frame name,
  byte-count mismatch) → keep the plain even-sampled set, print a stderr `WARNING`, never fail
  the run because of dedup.
- **Chunking degrades gracefully.** Failed chunk → gap marker, continue. All chunks fail → hop
  fails → chain falls through (existing chain semantics).
- **Pinned timestamps** out of range → skip + warn, run continues.
- Frame-count caps and budget math are otherwise unchanged; only the candidate multiplier is new.

## Testing

Pytest suite in `tests/`, modeled on upstream's approach: no network, fixtures synthesized with
ffmpeg in `conftest.py` (a static color clip and a scene-change clip). ffmpeg is required to run
the tests — same requirement as the skill runtime.

Coverage:

- Dedup: static clip collapses to few frames; scene-change clip keeps all distinct frames;
  `--no-dedup` bypasses; fail-open path (corrupt thumbnail input) returns the original set.
- Delta math: known byte patterns → exact mean-abs-diff values; length mismatch → infinite delta.
- Chunking: split boundaries respect the size cap; timestamp shift math; partial-failure merge
  produces gap markers; all-fail raises.
- `--timestamps`: parse all accepted formats; pinned frames survive dedup; out-of-range skipped.
- Hardening: `is_url` acceptance/rejection; resolved paths in built argv.
- Estimate: regression on the existing cost math (unchanged by this port).

Run with `python -m pytest` from the repo root.

## Performance

Extraction does ~2× the current frame seeks — still parallel, still seconds. The thumbnail pass
is a single cheap ffmpeg run over small JPEGs. No full-stream decode anywhere.

## Credits

Ported logic derives from `bradautomates/claude-video` v0.2.0 (MIT). Update `CREDITS.md` as part
of implementation.
