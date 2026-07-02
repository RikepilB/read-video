---
name: read-video
description: >-
  Analyze, summarize, transcribe, or answer questions about a video — a local file
  (.mp4/.mov/.mkv/.webm) or a video URL (YouTube, Loom, Vimeo, TikTok, X, etc.). Use this
  whenever the user wants the agent to "watch", "read", "summarize", "describe", "transcribe", or
  pull specific moments / quotes / timestamps out of video content — even if they never say the
  word "video" (e.g. "what does this Loom cover?", "summarize this youtube link", "what's on
  screen at 2:30?", "transcribe this screen recording", "what did they say about pricing?").
  It extracts frames so the agent can see the visual track and a transcript so it can hear the
  audio track, and ALWAYS prices the job up front so the user approves any spend or heavy step
  before it runs.
---

# Read Video

An agent's file-reading tool renders images and PDFs — **not** video. So "reading" a video means
converting it into two things an agent *can* consume: **frames** (JPEGs, the visual track) and a
**transcript** (text, the audio track). The catch is that this costs real tokens — frames
dominate — so this skill **estimates the whole job first** and only spends after the user (or a
$0 threshold) approves.

Everything runs through one agent-first CLI. Drive it in order: `probe → estimate → [gate] → run`.

```
python scripts/video.py probe    <input>
python scripts/video.py estimate <input> [--tier ...] [--backend ...] [--frames N] [--out-words W] [--human]
python scripts/video.py run      <input> [--tier ...] [--backend ...] [--frames N] [--start S --end E] [--workdir DIR]
```

`<input>` is a local path or an http(s) URL. Output is JSON (parse it); add `--human` to `estimate`
for a readable cost table. Run from the skill directory so `pricing.json` resolves.

## Workspace (optional, configured per machine)

If `workspace.json` exists in the skill dir, it points at the user's media workspace:
`{inbox_dir, out_dir}`. When it's set:

- **Inputs** — the user can pass a **bare filename** (e.g. `meeting-recording.mp4`) or a
  line from `inbox_dir/urls.md` instead of a full path. `probe`/`estimate`/`run` already resolve bare
  names against `inbox_dir`, so just hand the input straight to the CLI.
- **Outputs** — after you Read the frames/transcript and write your answer, **save the finished note to
  `out_dir/<source-stem>.md`** (the same TL;DR + `[MM:SS]` beats from the output contract below). That's
  the durable artifact the user keeps; the frame/transcript workdir is throwaway. Skip saving a file only
  if the user explicitly asked just to chat about it.
- **`whisper_model`** (optional) — pins the `faster-whisper` size (default `small`; good for non-English
  audio). Override here, or via env `READ_VIDEO_WHISPER_MODEL` / `READ_VIDEO_WHISPER_DIR`. The engine loads
  a cached model offline and falls back to a smaller cached size with a stderr `WARNING` if the chosen one
  is missing — if you see that warning, transcription accuracy is degraded (see `references/backends.md`).

No `workspace.json` → behave exactly as before (full paths / URLs only, answer in chat).

## Workflow — follow these steps

### 1. Probe
`python scripts/video.py probe <input>` → `{source, duration_s, width, height, has_audio,
captions_available, sidecar_transcript}`. This is free and instant. If it returns `{"error": ...}`,
relay the error (bad path, private/region-locked URL, missing tool) — don't guess past it.

### 2. Choose the tier
- **`visual`** — frames only. Use when the question is about what's *shown* (UI, slides, charts, scenes) or there's no meaningful speech.
- **`audio`** — transcript only. Use when the question is about what's *said* and visuals don't matter (podcast, voice memo).
- **`both`** (default) — frames + transcript. Use for general "summarize / what happens" requests.

Bias toward the cheapest tier that answers the question. A `sidecar_transcript` or
`captions_available: true` makes the audio side free, so `both` is usually fine there.

**Screen recordings / demos / silent clips → prefer `visual`.** A lot of "read this video" inputs are
narration-free screen captures (a UI walkthrough, a website demo, a slideshow) — the audio track is just
silence or background music. The value is entirely in the frames, and running audio there wastes time and
yields nothing useful. Signals it's likely silent: a desktop/browser-shaped resolution, a filename like
"Screen Recording …" / "… - Google Chrome …", or the user describing a UI/website rather than people
talking. When in doubt and the clip is short, `both` is safe (the engine skips silence with VAD, so a
silent track costs little) — but if you already ran `both` and `transcript_chars` came back tiny relative
to the duration (e.g. a few hundred chars for several minutes), that's a silent/music track: ignore the
transcript and answer from the frames.

### 3. COST GATE — the point of this skill
Always run `estimate` for the tier/backend you picked **before** `run`:

`python scripts/video.py estimate <input> --tier both --backend captions --human`

It returns `cost_usd: {transcription, agent, total}`, the `dominant_cost`, and the flags `free` and
`needs_install`. Apply this rule:

- **`free: true` AND `needs_install: false`** (no out-of-pocket $: sidecar / URL captions / local visual / local whisper) → **proceed without asking for spend approval** — no provider is billed and nothing installs. But still glance at `cost_usd.total` (agent tokens): if it's large — a long video, frames near the 100 cap, or several videos at once — tell the user the rough token cost and the cheaper levers first (`--tier audio`, fewer `--frames`, a `--start/--end` window). Small job → just run it.
- **`free: false` (a provider gets billed) OR `needs_install: true`** → **stop and show the user the `--human` estimate.** State the total, the dominant driver, and the backend. Then ask: **run as-is / pick a cheaper backend / skip.** Do not spend on an API, and do not install anything (`pip install faster-whisper`, `bun add -g @crafter/trx`), until the user says yes.

Never silently send audio to a cloud API — that's the user's data leaving the machine, and it costs
per minute. The gate is a privacy boundary as much as a budget one.

If the total is high, suggest the levers before asking: a cheaper `--backend`, fewer `--frames`, or a
focused `--start/--end` window (for "what happens at 5:00", extract only around 5:00).

### 4. Run
On approval: `python scripts/video.py run <input> --tier <t> --backend <b> [--frames N] [--start S --end E]`.
It writes a workdir containing `frames/frame_XXXX.jpg`, `transcript.txt`, and `manifest.json`
(the manifest maps every frame to its `[MM:SS]` timestamp).

Two extra `run` controls: `--timestamps 90,05:30` pins exact-moment frames (reserved against
the budget, never dropped by dedup — the manifest marks them `"pinned": true`), and
`--no-dedup` keeps every sampled frame. By default extraction oversamples ~2x the budget and
drops perceptual near-duplicates (held slides, static screens), so `frames` in the run JSON
may come back smaller than the budget with the difference in `frames_deduped` — that is the
budget being spent on distinct content, not an error.

The transcript backend cascades:

**sidecar (free) → URL captions (free) → local `faster-whisper`/`trx` (free, CPU) → Groq (cheapest API) → OpenAI-mini → OpenAI → OpenRouter / Gemini.**

`--backend` forces one; otherwise pass the backend you priced at the gate. You can also pass a
**comma-separated chain** — `--backend openrouter,groq` — to try each in order and fall through on any
failure (out of credits, rate limit, missing key). Useful for spending a limited/cheaper key first and
falling back automatically. The chain is **priced at the gate by its first hop**, so estimate/approve
against the most expensive realistic path. (Audio is extracted once and reused across hops.) Backend
setup, keys, and per-minute costs live in `references/backends.md` — read it when a backend errors on a
missing key or install.

### 5. Read and answer
Load the frames from the workdir `frames/` folder (in filename order) and `transcript.txt`. Then:

- **If the user asked a specific question** → answer it directly, grounded in what you saw/heard, citing `[MM:SS]` for any moment you reference.
- **Otherwise** → produce the default **timestamped chronological summary**:
  - A 2–3 line **TL;DR** at the top.
  - Then **`[MM:SS]` beats** down the timeline: what's on screen + what's being said at each point.

Ground every claim in a frame or a transcript line. If frames are sparse (long video, 100-frame cap),
say so and offer to re-run a focused `--start/--end` window rather than inventing detail.

If a workspace is configured (see above), **also save this answer to `out_dir/<source-stem>.md`** so the
user keeps a durable note, then tell them the path.

### 6. Clean up
The workdir is temporary. Remove it when finished, but keep its path in mind — for follow-up
questions about the same video, reuse the existing frames/transcript instead of paying to extract
again.

## Notes
- **Frames are the dominant cost.** The frame budget auto-scales with duration (≤30s→30, ≤3min→60, ≤10min→80, >10min→100, hard caps 2 fps / 100 frames). Lower `--frames` or window with `--start/--end` to cut cost.
- **Speed**: extraction grabs each frame with an independent fast input seek (parallel), not a full-stream decode — so wall-clock scales with frame *count*, not video length or fps (a 9-min 60 fps clip extracts in seconds). Local `faster-whisper` runs with VAD (silence-skipping) and is fed the media directly (no intermediate mp3), so silent/sparse audio finishes fast. If a run still feels slow, it's the model: a smaller `whisper_model`, or `--tier visual` when there's no speech, is the lever.
- **Token rates** for the agent-cost estimate live in `pricing.json` (`model_per_mtok._active`). If the user runs a different model, update `_active` so the estimate stays honest.
- **Long audio + paid APIs**: for the **API** backends only, audio is re-encoded to mono 64 kbps mp3 (~0.5 MB/min) so up to ~50 min fits the providers' ~25 MB upload cap; beyond that the engine now auto-chunks: the mp3 is split into even segments under the cap, each transcribed separately (timestamps shifted back into source time); a failed chunk leaves a `[transcription gap: ...]` marker instead of failing the run. Local `faster-whisper`/`trx` skip that step and read the media directly. API calls use no SDK (pure stdlib `urllib`) and retry on 429 / transient network errors. Keys are read **only** from environment variables — the skill never scans `.env` files.
- Prior art reused: `bradautomates/claude-video` (MIT, frame/caption logic), `crafter-station/trx` (MIT, local transcription).
