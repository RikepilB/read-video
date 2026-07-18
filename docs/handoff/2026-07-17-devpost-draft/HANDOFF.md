# Session Handoff — 2026-07-17-devpost-draft

## Goal
Harden `read-video`'s CLI/skill for Agent Experience and create the OpenAI Build Week Devpost
project draft without making the final hackathon submission.

## What was done
- Read the official live submission requirements, judging criteria, key dates, and July 17
  announcement through the authenticated Devpost connector.
- Kept the suggested request/response interception or “bypass” package out of scope; used
  `agent-browser` only for normal form discovery and moved to the authenticated Devpost connector
  when the headed session could not retain authentication.
- Added an opt-in, backward-compatible agent CLI protocol: `manifest`, `--envelope`, `--compact`,
  `{ok,data,error,meta}`, protocol version `1.0`, and exit codes 0–6.
- Added conservative error retryability: corrupt media is a non-retryable input error; explicit
  transient/rate-limit markers are retryable operation failures.
- Added nine subprocess/unit/documentation tests via red→green TDD. Full suite is now **120 passed**.
- Ran a real fixture flow through manifest → probe → estimate → run; cloud rejection returned exit
  4 and created no audio; malformed usage returned machine-readable exit 2.
- Updated `SKILL.md`, README, and CLI reference for the agent protocol; created
  `docs/devpost-draft.md` with overview copy, custom-field drafts, judge test commands, and missing
  final actions.
- Updated Devpost project `1332780`: name `read-video`, tagline, overview description, technologies,
  public repo, and landing page. Devpost automatically set the project page to `published` at
  `https://devpost.com/software/read-video`, but the Build Week entry remains unsubmitted
  (`submitted_at: null`). No final submission tool was called.

## Files changed
- `skill/scripts/video.py` — machine protocol, manifest, compact output, error taxonomy.
- `tests/test_agent_cli_contract.py` — subprocess contract and retryability regressions.
- `skill/SKILL.md`, `README.md`, `docs/cli-reference.md` — agent-facing usage contract.
- `docs/devpost-draft.md` — editable overview and submission-field working copy.
- `docs/handoff/.current-session`, `docs/handoff/HANDOFF.md`, this file — session state.

## Failed attempts
- `agent-browser --auto-connect` could not attach to the user's logged-in Chrome; a headed session
  opened Devpost but later timed out. No credentials were handled. The authenticated Devpost
  connector completed the project update safely.
- `skillspector scan skill --no-llm` still returns `100/100 CRITICAL — DO NOT INSTALL` (15 findings),
  chiefly the documented intentional API-key → cloud-transcription request flow. This is unchanged
  in substance from `SECURITY.md`; no installation was performed.
- The requested “draft” overview update caused Devpost to publish the standalone project page.
  It did **not** submit the project to OpenAI Build Week. There is no exposed MCP unpublish action,
  so the page was left intact rather than attempting a destructive workaround.

## Next steps
- Richard should rewrite/polish the Devpost description in his own voice; the organizer explicitly
  warns not to submit AI-generated copy unchanged.
- Update the country field on the actual Devpost form to Canada (Toronto) — corrected in the local
  draft only; no Devpost connector was available in the follow-up turn to push it live.
- Run `/feedback` in the primary build task and enter the confirmed ID.
- Test-install from a clean clone.
- Record/upload the public <3-minute YouTube demo with voiceover, add thumbnail/screenshots, then
  complete the remaining custom fields and explicitly authorize the final hackathon submission.
- Keep network interception/browser-bypass ideas parked outside this Build Week submission.
- Merge PR #7 (https://github.com/RikepilB/read-video/pull/7) when ready; re-point GitHub Pages
  Settings to `main` afterward (currently serves from this branch).

## Update — verification + commit (follow-up turn)

The `/ultraplan` cloud container reported failure after 90 minutes ("ExitPlanMode never reached"),
but its changes were already on disk, uncommitted. Rather than trust the "failed" status or the
"successful" claims in this file at face value, independently re-verified: ran `pytest` fresh
(120 passed, confirmed), read the entire `skill/scripts/video.py` diff, and ran a real command to
check exit-code behavior. Confirmed the work is sound with one nuance worth flagging: the
"backward-compatible" claim above holds for the legacy JSON *shape* but not for process exit codes
— every error now returns a classified code (2-6) instead of the old always-`1`, even without
`--envelope`. Safe in this repo (nothing here checks exit codes) but not literally 100%
backward-compatible at the process-exit level.

User reviewed and decided: keep the redesigned landing page, commit now, and corrected the
Devpost draft's wrong "Chile" country default to **Canada (Toronto)**. Committed as two logical
groups — `728a770` (agent CLI protocol) and `12c775d` (landing page redesign + Devpost draft) —
and pushed, updating PR #7 automatically.

## Update — Vercel deploy attempt (same turn)

User asked to also deploy the landing page to Vercel (keep both, alongside GitHub Pages). Attempt
blocked: `deploy_to_vercel` returned `403 forbidden` ("You don't have permission to create a
project"), and `list_projects` requires a `teamId` that doesn't exist (`list_teams` returned empty
— personal account). This is a Vercel account/connector permission issue, not something fixable
from this session. User chose to skip Vercel for now; GitHub Pages remains the only live landing
page. Revisit once the Vercel connector has project-create scope, or once the user supplies an
existing project name/ID to deploy into instead of creating a new one.

## Update — /gsd-ship again: contamination cleanup + PR #8 (same day)

User ran `/gsd-ship` again asking to "commit, test, push, ship all the things." Orientation
revealed the situation had changed significantly: **PR #7 was already merged** to `main`
(`123b7b4`), then a separate commit (`4ef7f3d`, "Delete .claude directory", authored directly by
Richard) removed this repo's own `.claude/` automation (ig-pipeline, instagram-capture, read-audio,
architecture rules) from `main`. Meanwhile the local working tree on this branch had accumulated
**unrelated contamination**: `docs/index.html` was overwritten with a different project's content
(title read "Voidscape", not read-video — cross-session bleed, not real work here), and a full
generic full-stack agent/skill scaffold (architect, database-reviewer, e2e-runner, shadcn,
tailwind-design-system, ~20 skill folders) had appeared uncommitted — none of it applicable to this
stdlib-only Python CLI.

Did not blindly "ship everything" as literally instructed — flagged all three findings to the user
before touching anything. Resolved: discarded the Voidscape `docs/index.html` (restored the
committed tape-deck redesign), discarded the entire foreign scaffold, and — per the user's
clarification ("keep my claude.md locally but not in the repo") — untracked `.claude/` from git
repo-wide (`git rm --cached`, added to `.gitignore`) while leaving the real automation files on
disk untouched, matching what already happened on `main`. Kept three new, legitimately-scoped,
read-only capture-adapter planning agents (youtube-private-queue-planner, x-bookmarks-planner,
substack-rss-planner — matches the already-parked ROADMAP vision) plus their `.codex/agents/*.toml`
mirrors, since those were real and well-formed, not contamination.

Committed (`ad1ed83`), pushed. Since PR #7 was already merged, opened **PR #8** for the 5 remaining
unmerged commits (AX protocol, landing redesign, Devpost draft, handoff updates, this cleanup):
https://github.com/RikepilB/read-video/pull/8. `pytest`: 120 passed, confirmed after cleanup.

User also asked for a portfolio-entry template. Found `PROYECTOS/Portfolio/src/data/projects.ts`
already has a `read-video` entry (`id: '14'`, `status: 'coming-soon'`) with stale pre-Build-Week
numbers (997 lines, 67 tests/11 files, 46 commits) — the user's pasted text was that exact existing
draft. Verified current real numbers against the live repo (1,300 lines, 120 tests/17 files, 62
commits on `main`) rather than trusting the old draft, and wrote `docs/portfolio-entry.md`: a
ready-to-paste replacement matching Portfolio's exact `Project` TypeScript schema, adding a Build
Week/agent-protocol/adversarial-review methodology phase, a 4th result tile, the live GitHub Pages
link, and recommending `status: 'shipped'` (flagged, not silently applied). Did **not** edit the
Portfolio repo directly — out of scope for a read-video session; the user pastes it in themselves.
Committed `72e7272`, pushed.

## Files in this folder
- `HANDOFF.md` — this curated digest
- `transcript.md` — full `/export` of the session (if captured)
- `snapshot-<HHMMSS>.md` — auto git-snapshots written by the PreCompact hook, if any
