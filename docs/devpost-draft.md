# Devpost draft — OpenAI Build Week

This is working copy for project `1332780`. Edit it into Richard's natural voice before the final
submission; the Build Week announcement explicitly asks participants not to submit AI-written
project descriptions unchanged.

## Project overview

**Name:** read-video

**Tagline:** Turn videos into grounded GPT-5.6 answers—with cost and privacy gates before the work starts.

**Built with:** Python, Codex, GPT-5.6, ffmpeg, ffprobe, yt-dlp, faster-whisper, pytest

**Links:**

- https://github.com/RikepilB/read-video
- https://rikepilb.github.io/read-video/

## Description

### Why I built it

Coding agents can read code, text, and images, but they cannot directly inspect a video file. The
usual workaround—extracting hundreds of frames and uploading the audio—also hides two important
decisions from the user: how many vision tokens the job may consume, and whether private audio is
about to leave the machine.

I built `read-video` as a Codex skill and a small, non-interactive Python CLI. It turns a local
video or URL into the two artifacts an agent can reason over: sampled JPEG frames and a timestamped
transcript. Codex then answers from those artifacts with grounded `[MM:SS]` citations.

### What it does

The workflow is deliberately explicit:

1. `probe` inspects duration, resolution, audio, captions, and local sidecars.
2. `estimate` calculates transcription spend and an API-equivalent GPT-5.6 vision/token estimate.
3. The user reviews the cost, dependency, model-download, and cloud-privacy gates.
4. `run` extracts only the approved frames and transcript.
5. Codex reads the manifest and artifacts and produces a timestamped answer.

The default path is local-first. A backend chain containing OpenAI, Groq, OpenRouter, or Gemini is
rejected before media download or audio conversion unless the user explicitly passes
`--allow-cloud`. A first-time Whisper model download has its own separate approval flag.

### What I added during Build Week

`read-video` existed before July 13, so I kept the event extension easy to audit. The Build Week
work adds:

- adaptive local transcription: fast through 45 seconds, then a higher-recall medium Whisper
  profile with tuned VAD and previous-text conditioning disabled;
- GPT-5.6 Sol, Terra, and Luna pricing with native 32×32 image-patch estimation;
- worst-case pricing and dependency checks across complete fallback chains;
- hard CLI enforcement for cloud processing and model-download consent;
- an agent-facing CLI protocol with a self-describing `manifest`, compact JSON, optional
  `{ok,data,error,meta}` envelopes, and deterministic exit/error metadata;
- a reproducible, copyright-free demo fixture with a sidecar transcript so judges need no API key
  or external media.

### How I used Codex and GPT-5.6

I used Codex with GPT-5.6 throughout the extension: first to inspect the existing repository and
separate pre-event behavior from eligible Build Week work, then to implement tests and features,
run a focused code review, and exercise the real probe → estimate → gate → run flow. The review
found nine issues in the new cost/consent logic; I fixed the six underlying causes and added
regressions before continuing.

The human decisions stayed human: the 45-second routing boundary came from my own videos; I chose
local-first privacy, conservative fallback pricing, explicit per-run consent, and the decision to
keep the hackathon scope to the CLI/skill instead of expanding into a web product or browser
scraper.

### Challenges

The hardest part was making a helpful fallback chain without weakening the privacy boundary. It is
not enough to inspect the first backend: a later fallback can still upload audio or cost money.
The estimator and runtime gate therefore examine the whole chain, and tests verify that conversion
and upload functions are never reached without consent.

Another challenge was first-run local transcription. A medium Whisper model can be hundreds of
megabytes, so `estimate` checks cache status and surfaces the download before `run` rather than
surprising the user halfway through a task.

### What I am proud of

- The current suite has 120 passing tests, including subprocess-level CLI tests, installer tests,
  threshold boundaries, model fallback, workspace filenames, GPT-5.6 patch pricing, and blocked
  cloud uploads.
- Judges can generate and analyze the demo fixture locally without keys or copyrighted media.
- Existing callers keep their original JSON, while agents can opt into a compact stable envelope.
- The repository documents the intentional static-security warning created by optional cloud API
  keys instead of hiding it.

### What I learned

Agent Experience is different from ordinary CLI ergonomics. Agents benefit from reflection,
compact structured output, stable exit semantics, zero interactive prompts, and approval gates
that are explicit flags rather than hidden confirmations. I also learned that cost estimation is
part of product design: the dominant cost is often the agent reading frames, not transcription.

### What's next

After Build Week I want to validate the thorough transcription profile on more original long-form
videos and extract a cleaner media-reader interface from the working CLI. Broader capture adapters
and browser automation remain deliberately outside this submission.

## Submission fields

| Field | Draft answer |
|---|---|
| Submitter Type | Individual |
| Country | Canada (Toronto) |
| Category | Developer Tools |
| Repository | https://github.com/RikepilB/read-video |
| Project/test URL | https://rikepilb.github.io/read-video/ — follow the key-free judge demo below |
| `/feedback` Session ID | **PENDING: run `/feedback` in the primary build task** |

### Installation, platforms, and judge test

Supported: Windows 11 PowerShell; macOS/Linux Bash; Python 3.10+; Codex and other agents that read
the standard `SKILL.md` format. `ffmpeg`/`ffprobe` are required; `yt-dlp` is only needed for URLs;
`faster-whisper` is optional.

From the public repository:

```powershell
.\scripts\install-skill.ps1
python scripts/create-demo-fixture.py
python skill/scripts/video.py manifest --compact
python skill/scripts/video.py estimate samples/build-week-demo.mp4 --tier both --backend captions --agent-model gpt-5.6-terra --envelope --compact
python skill/scripts/video.py run samples/build-week-demo.mp4 --tier both --backend captions --workdir samples/build-week-output --envelope --compact
```

No key, account, or copyrighted sample is required. Read
`samples/build-week-output/manifest.json`, its three frames, and `transcript.txt`, then ask Codex
for a summary with `[MM:SS]` citations.

## Missing before final submission

- Rewrite/polish the description in Richard's own voice.
- Commit and push the agent-facing CLI contract added after this draft was started.
- Run a clean-clone installation test.
- Run `/feedback` and add the confirmed session ID.
- Record and upload the public <3-minute YouTube demo with voiceover.
- Add a project thumbnail and final screenshots on Devpost.
- Review every answer, then explicitly authorize final submission.
