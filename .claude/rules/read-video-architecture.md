# read-video — Architecture & Workflow

## Shape: single-file CLI engine, packaged as a portable agent skill

No web app, no database, no network boundaries. `read-video` is one Python CLI
(`skill/scripts/video.py`) driven agent-first: `probe → estimate → [cost gate] → run`. It's
distributed as a Claude-Code-style "skill" bundle (`SKILL.md` + the script + reference docs)
that any harness (Claude Code, Codex, etc. — see `docs/harness-support.md`) can install via
`scripts/install-skill.ps1`/`.sh`.

## Layout
- `skill/scripts/video.py` — the whole engine: probing, cost estimation, frame extraction,
  transcription-backend cascade (sidecar → captions → local whisper/trx → paid APIs). One
  intentionally large file by convention — CLI subcommands stay colocated so an agent reads one
  file to understand the tool, not a multi-module package.
- `skill/references/backends.md` — transcription-backend setup/keys/costs, loaded on demand
  (not preloaded into every session).
- `skill/pricing.json` — per-model token rates for the agent-cost estimate; update
  `model_per_mtok._active` if the operating model changes.
- `skill/workspace.json` (gitignored, machine-local) — optional `{inbox_dir, out_dir,
  whisper_model}`; `skill/workspace.example.json` is the template.
- `scripts/instagram_capture_helper.py` + `.claude/agents/instagram-capture-subagent.md` +
  `.claude/commands/instagram-capture.md` — an optional, separate add-on (Instagram
  saved-collection → `urls.md` capture) that feeds `video.py` as input; not part of the core
  engine and must not reach into `video.py` internals beyond its public CLI.
- `scripts/install-skill.ps1`/`.sh` — installs the skill bundle into a harness's skills
  directory; keep both in parity (`tests/test_install_skill.py` checks this).
- `tests/` — one file per concern (`test_chunking.py`, `test_dedup.py`, `test_estimate.py`,
  `test_frames.py`, `test_hardening.py`, `test_instagram_capture_helper.py`,
  `test_install_skill.py`, `test_pins.py`, `test_skill_md_wording.py`, `test_thumbs.py`,
  `test_timestamps.py`).

## Boundaries
- `scripts/instagram_capture_helper.py` (the capture add-on) must not import from
  `skill/scripts/video.py` internals — it only ever produces plain URLs that `video.py` consumes
  as ordinary CLI input. Keeps the add-on removable without touching the core engine.
- No credentials read from files this project scans itself (`.env`, cookie stores). Auth
  material (e.g. `READ_VIDEO_YTDLP_COOKIES`, API keys) is read **only** from environment
  variables the user sets themselves.

## Git workflow

| When | Action |
|---|---|
| Starting a feature | Branch: `feat/<name>` or `fix/<name>` |
| Before merging | `pytest` (all suites under `tests/`) must pass — no lint/typecheck config exists in this repo (pure-stdlib Python, no build step) |
| New backend/cost path | Update `skill/pricing.json` and `skill/references/backends.md` together — an estimate that doesn't match the actual call site is a silent cost-gate bypass |

## Key reminders
- **The cost gate is the point of the whole tool** — any change touching `estimate`/`run` must
  keep `cost_usd`/`free`/`needs_install` accurate; a wrong estimate defeats the project's core
  privacy/budget promise (see `SKILL.md`'s "COST GATE" section).
- **Server/local-first by default** — prefer local/free transcription paths (sidecar, captions,
  local whisper) before any paid API; never send audio to a cloud API without the user's
  explicit go-ahead at the cost gate.
- Update this file the moment the layout above changes — this is the file an agent actually
  reads to plan a change, not `docs/architecture.md` (which doesn't exist in this repo; this file
  is the single source of truth).
