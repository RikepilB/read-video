# OpenAI Build Week submission runbook

## Devpost-ready summary

`read-video` is a Codex skill and CLI that turns local files or video URLs into sampled frames and
timestamped transcripts, estimates GPT-5.6 API-equivalent cost before work begins, and lets Codex
produce grounded answers with `[MM:SS]` citations. The Build Week extension adds adaptive local
transcription for longer videos, conservative fallback-chain pricing, explicit model-download
consent, and a hard cloud privacy gate that rejects uploads before audio conversion unless the user
approved `--allow-cloud`.

Category: **Developer Tools**. Public test path: generate `samples/build-week-demo.mp4` with
`python scripts/create-demo-fixture.py`, run the README estimate/run commands, then ask Codex to
summarize the generated artifacts.

## 2:40 demo storyboard

- **0:00–0:20 — Problem:** coding agents read images and text, not video; cost and audio privacy
  are easy to hide.
- **0:20–0:45 — Install + fixture:** run the one-command installer and generate the original local
  fixture. State that no key or copyrighted media is required.
- **0:45–1:15 — Gate:** probe, then estimate with `gpt-5.6-terra`. Point to patch-token accounting,
  API-equivalent label, backend-chain worst-case cost, model status, and approval fields.
- **1:15–1:40 — Grounded result:** run locally and have Codex answer from frames + sidecar with
  `[MM:SS]` citations.
- **1:40–2:05 — Transcription improvement:** on an original >45-second spoken clip, compare
  `--transcribe-mode fast` with `thorough`; show medium model, tuned VAD, and no previous-text
  conditioning.
- **2:05–2:25 — Privacy proof:** attempt an OpenAI/Groq fallback chain without `--allow-cloud` and
  show rejection before audio conversion/upload. Use the `samples/privacy-proof.mp4` copy (README's
  install section) — the main demo fixture has a sidecar transcript, which resolves for free and
  never reaches the cloud backend at all, so it won't trigger the gate.
- **2:25–2:40 — Collaboration + impact:** explain what Codex/GPT-5.6 implemented and the human
  decisions on threshold, privacy, cost conservatism, and scope.

Use only original screen and audio. Keep the public YouTube video under three minutes.

## Evidence and final human actions

- Last pre-event commit: `bf45369`, dated 2026-07-09.
- Build Week branch: `codex/build-week-read-video`, implementation dated 2026-07-17.
- Add the authorized post–July 13 release commit hash to README and this file.
- Implementation Codex task: `019f708e-5615-7f00-9a02-b0e5bc435efd`.
- Run `/feedback` in the primary end-to-end Codex task and paste the returned session ID here.
- Manually compare fast/thorough transcripts on 2–3 original videos longer than 45 seconds.
- Test from a clean clone, record/upload the public demo, add the public repository URL, and submit
  Devpost before July 21, 2026, 5:00 PM PT.
