# Codex Agent Mirrors

This directory intentionally tracks Codex-compatible mirrors of the source-specific agents in `.claude/agents/`.

They are not general-purpose agents:
- `instagram-capture-subagent` is dispatched only by the Instagram capture workflow.
- `ig-analyze-subagent` is dispatched only by the Instagram capture-to-analysis workflow.
- `youtube-private-queue-planner`, `x-bookmarks-planner`, and `substack-rss-planner` are planning-only until their respective adapters and controller commands exist.

No source agent may be used as a substitute for another source's process. Keep these files aligned with their `.claude/agents/*.md` counterparts when the workflow contract changes.
