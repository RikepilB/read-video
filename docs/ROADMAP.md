# read-video → Universal Save-and-Read Pipeline — Long-Term Roadmap

**Status: planning only.** No implementation authorized by this document. Each milestone below
still needs its own `brainstorming → writing-plans → subagent-driven-development` cycle when work
actually starts on it — same process used for every thread shipped so far in this repo. This doc
exists so the vision isn't lost, not as a green light to start building.

## Vision

Turn `read-video` from a personal Instagram-reel tool into an open-source, multi-platform,
multi-media "save something anywhere → get it read and organized" pipeline — usable by
developers, by AI agents, and by non-technical people, not just by one person's own workflow.

## Guiding principles (carried over from what already exists here)

- **Cost-gate before spend, always** — every new capture-adapter or media-reader inherits
  `SKILL.md`'s existing philosophy: estimate first, ask before any paid/cloud spend.
- **Local-first / privacy-first** — never send captured content to any cloud service without an
  explicit gate the user approves.
- **Harness-neutral where feasible** — reuse Thread C's multi-harness packaging pattern
  (`SKILL.md` + `scripts/install-skill.*`) so new pieces install the same way on Claude Code,
  Codex, Gemini CLI, Copilot CLI.
- **Small, independently spec'd modules** — one platform or one media type per cycle, never a
  big-bang rewrite. This is the same discipline that kept Threads A/C/D/E reviewable.
- **Legal/ToS risk is a first-class constraint** — each platform's automation gets its own
  terms-of-service and rate-limit review before it ships past "just for me," and especially
  before any hosted/SaaS use.

## The three audience tracks

This is why it's not one project — three genuinely different deliverables, built on the same
core:

1. **Technical people** — the open-source repo itself: code, docs, self-serve.
2. **AI agents** — the pipeline packaged so an *agent*, not a human, can discover and drive it
   (skill manifests, MCP-style tool surfaces, machine-readable guides).
3. **Non-technical people** — no code at all: demo videos, one-line installers, eventually a
   hosted website/SaaS product.

## Phase 0 — Foundation: generalize the two axes this repo currently hard-codes

Everything today is hard-wired to "Instagram" (capture) and "video" (read). Two orthogonal
interfaces need to exist before anything else in this roadmap makes sense:

- **Capture axis** — bookmark / saved-collection / folder → queue file. Today:
  `instagram_capture_helper.py` does this for one platform via Claude-in-Chrome browser
  automation, writing to `urls.md`.
- **Read axis** — media → frames/transcript/text → notes. Today: `video.py`'s
  `probe → estimate → run`, video-only.

**Milestone 0.1 — Capture-adapter interface.** Separate what `instagram_capture_helper.py` does
that's IG-specific (selectors, auth, saved-collection shape) from what's generic (append-to-queue,
dedup via unsave-or-mark, dry-run-first, abort-cleanly-on-selector-break). Define that interface
once, so a new platform is "implement this interface," not "copy and rewrite the whole thing."

**Milestone 0.2 — Media-reader interface.** Same exercise for `video.py`: separate
video-specific mechanics (frame extraction, fps/duration tiering) from generic mechanics
(cost-gate shape, output note template). This is where the already-parked **Thread B** (extend
media types) and **Thread F** (transcription thoroughness tiers) naturally become the first real
test cases of this interface.

## Phase 1 — Media-type expansion (the "read" side)

- **1.1 Images** — static posts and carousels (today: skipped entirely — see Thread E's
  `[SKIPPED]` marker convention). Vision-only tier, no transcript.
- **1.2 Audio-only** — podcasts, voice memos, X Spaces, LinkedIn audio posts. Reuses the existing
  transcription-backend cascade almost as-is.
- **1.3 Blog / post / text** — Substack articles, LinkedIn posts, X threads, long-form blogs. No
  frames or transcript at all — closer to "fetch + summarize" than to `video.py`'s current shape.
  May end up as its own lightweight script rather than being forced through the video interface.

## Phase 2 — Platform expansion (the "capture" side)

One milestone per platform, each its own spec/plan/implementation cycle, each gated on: does the
platform have a bookmark/saved-collection concept; what does its ToS say about automation; is
there a Claude-in-Chrome-drivable UI or a real API alternative.

- **2.1 X (Twitter) bookmarks**
- **2.2 TikTok favorites/saved**
- **2.3 LinkedIn saved posts**
- **2.4 Substack saved/subscribed posts** — likely API/RSS-based, not browser automation;
  Substack has no bookmark-grid UI to drive the way IG/TikTok do.

## Phase 3 — Technical-audience packaging

Builds on Phase 0-2; realistically starts once at least one new platform and one new media type
exist, so the docs describe a real pattern instead of a single one-off.

- **3.1** Generalize "how to use" docs (SKILL.md/README/CONTRIBUTING already exist in miniature
  for read-video alone) to cover N platforms × M media types.
- **3.2** Write the "how to build your own adapter/reader" meta-guide — walks a contributor
  through Phase 0's interfaces so they can add platform #5 or media-type #4 without reading this
  whole roadmap.
- **3.3** Public-launch documentation polish — revisit once the Phase 0 interfaces have actually
  stabilized; don't announce a public API surface that's about to be redesigned.

## Phase 4 — AI-agent-consumable packaging

Can start any time after Phase 0 — doesn't block on Phase 1/2/3.

- **4.1** Formalize each capture-adapter and media-reader as its own installable skill bundle
  (same `SKILL.md` + `scripts/install-skill.*` pattern already shipped for read-video), so an
  agent harness can install "the LinkedIn adapter" independently of "the audio reader."
- **4.2** Agent-facing discovery docs — not prose for humans, a machine-readable index (tool
  manifest / `agents.md`-style file) so an agent can discover what it can read and capture from,
  without a human curating every session.
- **4.3** Consider an MCP server wrapping the whole pipeline, so any MCP-capable agent (not only
  Claude Code) can drive it as tool calls instead of shelling out to a CLI.

## Phase 5 — Non-technical distribution

- **5.1** Demo videos per platform/media-type combo (screen recordings of the full
  capture→read→note flow) — a genuinely good use of read-video on itself.
- **5.2** One-line installers / packaged downloads for non-developers (no git clone, no Python
  setup) — needs its own design pass (binary bundling? Docker? hosted installer script?).
- **5.3** A plain marketing/docs website hosting the demo videos, guides, and downloads from
  5.1/5.2 — static site, not the SaaS product yet.

## Phase 6 — Hosted SaaS ("as a service")

The biggest, riskiest, most separate piece of this whole roadmap — likely its own product/repo,
not a feature bolted onto this one.

- **6.1** Product design pass: what "as a service" concretely means — connect-your-account and
  auto-process saved items, a paste-a-link one-off tool, or both.
- **6.2** Auth, multi-tenancy, billing — none of this exists today; genuinely new infrastructure,
  not a generalization of the CLI.
- **6.3** LLM SDK integration layer (Vercel AI SDK + Anthropic/OpenAI/others) — replaces this
  project's own agent-token cost *estimate* with real per-user billing/usage metering.
- **6.4** **Legal review — a hard gate before any public launch.** Automating captures from other
  people's accounts at SaaS scale is a materially different ToS/rate-limit/abuse-risk situation
  than one person's personal tool (today's scope). This alone could be a go/no-go for the entire
  SaaS track, independent of whether it's technically buildable.

## Suggested sequencing (a sane default, not a commitment)

1. **Phase 0 first** — everything else depends on the two interfaces existing.
2. **Phase 1 + Phase 2 in parallel**, one milestone at a time — whichever platform or media type
   you personally want next, proving the Phase 0 interfaces actually generalize.
3. **Phase 3** once ≥2 platforms and ≥2 media types exist, so the docs reflect a real pattern.
4. **Phase 4** any time after Phase 0 — independent of Phase 1-3's progress.
5. **Phase 5** after Phase 3 — needs stable docs to build videos/guides from.
6. **Phase 6 last**, and only after its own dedicated product + legal design pass — a different
   kind of project, not a natural extension of the CLI.

## Open questions (flagged, not decided here)

- **Naming/identity** — "read-video" undersells a multi-platform, multi-media,
  capture-and-read pipeline. Rename the whole thing, or keep `read-video` as the "reader" half
  and give capture-adapters their own umbrella name?
- **One repo or many** — does Phase 0's generalization argue for splitting into a `read-anything`
  reader engine plus one `capture-adapters/*` package per platform inside this repo, or into
  fully separate repos?
- **Per-platform ToS ownership** — who actually reads and signs off on each platform's terms
  before an adapter ships, even at "developers self-host it" scope, let alone SaaS scope?
