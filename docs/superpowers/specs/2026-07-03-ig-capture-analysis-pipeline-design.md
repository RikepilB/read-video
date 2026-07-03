# Instagram Capture → Analysis Pipeline (Sub-project #2 / "Phase 2") — Design

**Date:** 2026-07-03
**Status:** Retroactive — design written after the work shipped. This is documentation of an
already-completed spike (all 46 captured URLs processed, output verified in the user's Second
Brain vault), not a plan gating future implementation.
**Scope:** Analysis phase — turn `urls.md`'s captured reel URLs into a searchable personal
knowledge index + per-video notes, using `read-video`'s existing engine unmodified.

## Context

`2026-07-02-instagram-capture-design.md` (sub-project #1) explicitly deferred this phase as a
non-goal: "transcription, analysis, report generation, or indexing... designed separately later."
That later point came mid-session, when the user asked for exactly this: for each captured reel,
get title/synopsis/priority in one index, plus a separate per-video file with the full transcript,
notes/action items, and a usability assessment — filed in `out_dir` (the same
`workspace.json`-configured directory `read-video` already writes to).

This was explicitly run as a spike/test first ("if all said and set then let's go and test the
full process... in 5 urls"), then scaled to the full batch once the 5-video test proved the
approach ("if all is working fine try finishing the [remaining] urls").

## Goals

1. **Index** — one row per processed video in `_ig-index.md`: priority, title, one-line synopsis,
   link to its full note file, source URL.
2. **Per-video note** — `ig-<shortcode>.md` per video: title, source line (duration/language/
   format), priority + one-line reason, synopsis, notes & action items, usability assessment, full
   timestamped transcript.
3. **Priority rubric** — relevance to the user's stated interest domains: job-hunting, AI-agent
   tooling, programming fundamentals, system design, security, project-lifecycle. High = concrete
   technique/tool directly usable; Medium = relevant but pointer-only or partial; Low = tangential
   or ad/course-upsell content with no actionable technique.
4. **Reuse, don't rebuild** — every video goes through `read-video`'s existing `probe → estimate →
   run` unmodified; this sub-project only adds what happens *after* `run` returns frames+transcript
   (reading them, writing the note, updating the index).
5. **Respect the cost gate at batch scale** — one estimate covering the whole batch, one go/no-go,
   not 46 individual approvals (transcription was $0 out-of-pocket via local `faster-whisper`; only
   agent-token cost, ~$0.65/video, frames-dominant).

## Constraints

- **No concurrent writes to the index** — every subagent that processes one video returns its
  result to the controller; the controller (not the subagent) appends the index row. Prevents
  interleaved writes corrupting `_ig-index.md` when multiple videos process in parallel.
- **Queue state lives on disk, not in memory** — the "what's left to process" list is regenerated
  from a disk diff each round (`urls.md`'s shortcodes minus `Transcripts/ig-*.md`'s shortcodes),
  never trusted as a remembered count. A memory-based count drifted once during the real run
  (miscounted 46 vs. the actual 45 URLs) before this was adopted.
- **Fetch-feasibility is not guaranteed by capture** — a URL landing in `urls.md` does not mean
  `yt-dlp` can fetch it later. Instagram requires authentication for anonymous fetches; this
  sub-project depends on `READ_VIDEO_YTDLP_COOKIES` being set (see `video.py`'s cookie-auth
  mechanism, commit `c23912a`) for any of this to work at all.
- **Not every captured URL is a video** — some `/reel/<shortcode>/` URLs resolve to multi-slide
  image carousels (Instagram allows this under the same URL shape). These have no video track;
  `yt-dlp` correctly reports "No video formats found," not a fetch failure.

## Non-goals

- **A reusable script or slash command in this repo.** Unlike sub-project #1 (`/instagram-capture`,
  a real command backed by `instagram_capture_helper.py` + tests), this phase was run entirely as
  controller-orchestrated background `Agent` dispatches against the vault — there is no
  `/instagram-analyze` command, no helper module, no test coverage for this phase in
  `read-video`'s own test suite. Formalizing it into real, tested tooling is explicitly future
  work, not part of this spec.
- **Automatic hand-off from capture.** The user runs this phase manually against whatever's
  accumulated in `urls.md`; no automation triggers it when new URLs land.
- **Deduplication against already-indexed videos.** This run assumed every URL in `urls.md` at
  batch-start was unprocessed (true, since sub-project #1's unsave-as-dedup already prevents
  re-capturing). A future formalized version would need its own re-run/skip-if-indexed guard.

## Architecture

```
urls.md (46 captured reel URLs)
        │
        ▼
Controller: disk-diff queue ──► regenerate remaining list each round
        │
        ▼
"Wave" dispatch: ~5 concurrent background Agent subagents
        │
        ├─► per video: video.py run <url> --tier both --backend faster-whisper
        ├─► Read frames/ + transcript.txt
        ├─► classify priority (rubric above)
        ├─► write out_dir/ig-<shortcode>.md (template below)
        ├─► delete its temp workdir
        └─► return {shortcode, priority, title, synopsis} to controller
        │
        ▼
Controller appends one row to out_dir/_ig-index.md per completion
        │
        ▼
On completion notification: dispatch a replacement subagent to refill the wave
        │
        ▼
Repeat until disk-diff is empty
```

## Components

### 1. Per-video subagent (ad-hoc `general-purpose` dispatch, not a named agent type)

Self-contained: given one URL, it runs the full `read-video` flow, reads the output itself,
writes its own note file, cleans up its own workdir, and returns a short structured summary. It
never touches the index file directly (see concurrency constraint above).

### 2. Note file template (`ig-<shortcode>.md`)

```markdown
# <Title>

Source: <URL> (<duration>, <language>, <format notes>)
Priority: **<High|Medium|Low>** — <one-line reason>

## Synopsis
<2-4 sentences>

## Notes & Action Items
- <bullet notes, concrete takeaways, follow-ups>

## Usability
<1-3 sentences: how directly this applies to the user's stated interest domains>

## Full Transcript
[MM:SS] <line>
[MM:SS] <line>
...
```

### 3. Skip marker (non-video posts)

```markdown
# [SKIPPED] Not a video — image carousel

Source: <URL>
Priority: N/A — no video content to process.

## Notes
<one-line reason from yt-dlp's own output, e.g. playlist_count and "No video formats found">
```

Written so the disk-diff queue-tracking treats it the same as a real note file (satisfies "this
shortcode has been handled"), without fabricating a transcript/analysis for content that has none.

### 4. Index file (`_ig-index.md`)

```markdown
# Instagram Capture — Processed Index

Auto-generated from `urls.md`'s captured "Cursos" reels. One row per processed video; full
transcript + notes live in the linked file. Priority = relevance to job-hunting / AI-agent
tooling / programming fundamentals / system design / security / project-lifecycle.

| Priority | Title | Synopsis | File | Source |
|---|---|---|---|---|
| High | ... | ... | [ig-xxx.md](ig-xxx.md) | https://www.instagram.com/reel/xxx/ |
```

## Data flow

```
urls.md ──shortcodes──► disk diff ──► remaining queue
                                            │
                          dispatch (≤5 concurrent)
                                            │
                video.py probe → estimate → run (existing engine, unmodified)
                                            │
                              Read frames + transcript
                                            │
                          classify + write ig-<code>.md
                                            │
                    controller appends _ig-index.md row
                                            │
                              refill wave, repeat
```

## Error handling

- **Fetch fails (auth)** — this is what surfaced the fetch-feasibility gap this session: fixed at
  the `read-video` engine level (`READ_VIDEO_YTDLP_COOKIES`), not something this phase works around
  itself.
- **Non-video carousel post** — write the `[SKIPPED]` marker (component 3), don't fabricate
  analysis, don't loop forever re-attempting it (disk-diff sees the marker file and treats it as
  handled).
- **Concurrent-write race on the index** — prevented by construction (subagents never write the
  index; only the controller does, one append per completion notification).
- **Queue drift** — prevented by construction (disk-diff regenerated each round, never trusted as
  a remembered count — see Constraints).

## Testing

No `pytest` coverage — this phase has no code in the repo to test; it's controller-orchestrated
subagent work against a user's personal vault (outside the repo, not git-tracked). Acceptance was
empirical, same philosophy as sub-project #1: a 5-video test batch run end-to-end and manually
inspected before scaling to the full 45 remaining URLs. Known limitation, called out explicitly:
if this phase gets formalized into real tooling (see Non-goals), *that* tooling should get real
test coverage the way `instagram_capture_helper.py` did.

## Known quality gaps (carried into "Next steps," not fixed by this spec)

- Auto-generated note quality was spot-checked on only 2 of 41 real videos during the batch itself
  (one during the run, one afterward on user request) — no systematic review of title accuracy or
  priority-judgment consistency across the full set.
- Transcript completeness degrades on longer videos (~>45s) due to default faster-whisper VAD/
  `condition_on_previous_text` settings tuned for short clips — tracked separately as its own
  sub-project (transcription-thoroughness tiers, parked design, see
  `2026-07-03-transcription-thoroughness-tiers-design.md`).

## Credits

No third-party code. Built entirely on `read-video`'s existing `probe`/`estimate`/`run` CLI and
the cookie-auth mechanism added this session (commit `c23912a`).
