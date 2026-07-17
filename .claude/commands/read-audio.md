---
description: Transcribe one or more local audio (or video) files into vault notes using read-video's engine — cost-gated, local-first. Not tied to Instagram; for voice memos, calls, meeting recordings, anything on disk.
argument-hint: <path1> [path2 ...] [--out <dir>] [--tier audio|both] [--backend faster-whisper|...]
---

Parse `$ARGUMENTS`:
- Every space-separated token that isn't a recognized flag is an input file path (quote paths with
  spaces). At least one is required — if none given, stop and ask the user which file(s).
- `--out <dir>`: absolute path to write notes into. If omitted, default to
  `<out_dir>/_Audio_Notes` (see path resolution below) — a flat catch-all, separate from the
  Instagram pipeline's category folders.
- `--tier audio|both` (default `audio`): `audio` skips frame extraction — the right default for
  voice memos/calls with no meaningful video track. Pass `--tier both` for a file where visual
  content also matters.
- `--backend <name>` (default `faster-whisper`): local, free, on-device transcription. Only
  override this if the user explicitly asks for a different backend.

## 1. Resolve paths

1. Read `~/.claude/skills/read-video/workspace.json` (`$env:USERPROFILE\.claude\skills\read-video\workspace.json`
   on Windows) for `out_dir`. If missing, stop and tell the user to configure it first.
2. `skill_dir` = the directory containing that `workspace.json`.
3. `notes_dir` = `--out` if given, else `<out_dir>/_Audio_Notes`.

## 2. Per-file processing (sequential is fine — this is normally 1-3 files, not a batch)

For each input path:

1. Resolve to an absolute path (support a bare filename relative to the workspace `_Inbox` the
   same way `video.py` does internally). If it doesn't exist, report the error for that file and
   continue to the next one — don't abort the whole batch over one bad path.
2. `cd` into `skill_dir` and run `python scripts/video.py probe "<path>"` to confirm it's readable
   and get duration.
3. Run `python scripts/video.py estimate "<path>" --tier <tier> --backend <backend>`.
   - **Cost gate.** If `needs_install: true`: stop for this file, tell the user what's missing
     (see `skill/references/backends.md`), don't install anything yourself, move to the next file.
   - If `needs_model_download: true` (the duration-routed whisper model — e.g. `thorough` mode's
     `medium` — isn't cached locally): tell the user a one-time model download is required, and
     get explicit go-ahead before proceeding — never download a model silently. Only pass
     `--allow-model-download` on the `run` call below after that go-ahead.
   - If `free: false` (a paid backend was explicitly requested): tell the user the estimated
     `cost_usd.total` and get explicit go-ahead before proceeding with that file — never spend
     real money silently, even on a single personal file.
   - Otherwise (expected case: local/free) continue.
4. Run `python scripts/video.py run "<path>" --tier <tier> --backend <backend> --workdir <a temp
   dir, e.g. under the system temp directory>`, adding `--allow-model-download` only if the user
   approved it in step 3.
5. `Read` the resulting `transcript.txt` (and `frames/*.jpg` in filename order if `--tier both`).
6. Write a note — synthesize a synopsis and action items yourself from the actual transcript
   content, the same way `ig-analyze-subagent` does; this is a semantic read, not a template fill.
   Slugify the source filename (or a short descriptive title if the filename is generic, e.g.
   `Recording.m4a`) for the note's filename: lowercase, non-alphanumeric runs → single `-`, strip
   leading/trailing `-`. If a file already exists at `<notes_dir>/<slug>.md`, append `-2`, `-3`,
   etc. Structure:

   ```markdown
   # <Title>

   Source: `<original path, relative to a recognizable root if long>` (local file, <duration>,
   <language if identifiable>, transcribed locally with <backend>)

   ## Synopsis
   <2-4 sentences on what's actually discussed/said>

   ## Notes & Action Items
   - <concrete takeaways, decisions, follow-ups actually present in the audio>

   ## Full Transcript
   [MM:SS] <line>
   [MM:SS] <line>
   ...
   ```

   Clips over ~45s already get `faster-whisper`'s `thorough` profile automatically (tuned VAD,
   no previous-text conditioning — see `skill/references/backends.md`); if the transcript still
   has visibly noisy or garbled stretches, add a one-line flag in Notes & Action Items naming
   those timestamp ranges rather than silently presenting a possibly-incomplete transcript as
   clean.
7. Delete the temp workdir from step 4.

## 3. Final report

Report, per file: note path written (or the specific error/skip reason), duration, and whether the
transcript-completeness caveat applies. No `pytest` coverage exists or is expected for this command
— it's semantic transcription + note-writing, not unit-testable logic; acceptance is the user
reading the resulting note against the source audio.
