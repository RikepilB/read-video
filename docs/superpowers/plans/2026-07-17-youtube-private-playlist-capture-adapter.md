# YouTube Private Playlist Capture Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a YouTube capture adapter that moves videos from a user-owned private queue playlist into read-video's existing `urls.md` queue, then removes each captured playlist item as the processed marker.

**Architecture:** Keep this as a second one-off adapter beside Instagram, not a generic capture interface. Use the official YouTube Data API v3 with OAuth, but do not use Watch Later: current Google docs say Watch Later playlist items are not accessible through `playlistItems.list`. The adapter should target a user-created private playlist, default title `Read Video Queue`, and reuse the same append-before-remove safety rule as Instagram.

**Tech Stack:** Python 3 stdlib (`argparse`, `json`, `urllib`, `pathlib`), YouTube Data API v3, existing `workspace.json` queue convention, pytest.

## Global Constraints

- Source queue is a user-owned private playlist, not Watch Later.
- Official-doc constraints checked 2026-07-17: `playlistItems.list` costs 1 quota unit and accepts `playlistId`, `maxResults` up to 50, and `pageToken`; it documents Watch Later access errors.
- `playlistItems.delete` costs 50 quota units and requires an authorized manage scope such as `https://www.googleapis.com/auth/youtube` or `https://www.googleapis.com/auth/youtube.force-ssl`.
- OAuth for installed apps should use a system browser/local redirect flow; no service accounts for YouTube user data.
- Append to `urls.md` before deleting/removing anything from the YouTube playlist.
- No API keys or tokens in repo files; tokens come from environment or gitignored local config only.
- Do not extract Phase 0's generic capture-adapter interface in this plan.
- Sources: https://developers.google.com/youtube/v3/docs/playlistItems/list, https://developers.google.com/youtube/v3/docs/playlistItems/delete, https://developers.google.com/youtube/v3/docs/playlists/list, https://developers.google.com/youtube/v3/guides/auth/installed-apps

---

## File Structure

- Create `scripts/youtube_capture_helper.py`: deterministic helper for playlist item listing, URL canonicalization, queue append confirmation, and safe delete decisions. Owns all YouTube API HTTP calls.
- Create `tests/test_youtube_capture_helper.py`: no-network tests for canonical URLs, pagination, dry-run behavior, append-before-delete, and API error handling through injected fake HTTP functions.
- Create `.claude/commands/youtube-capture.md`: Claude Code orchestrator mirroring `/instagram-capture`, resolving `workspace.json` and dispatching the helper.
- Create `.codex/agents/youtube-capture-subagent.toml` only if Codex needs a separate scoped agent after the Claude command proves useful. Do not create it in the first implementation task unless the command cannot express the workflow.
- Modify `README.md`: add a short optional YouTube capture section next to Instagram capture.
- Modify `docs/ROADMAP.md`: mark Phase 2.5's source queue as a private playlist, with Watch Later explicitly rejected by API docs.
- Modify `docs/decisions.md`: already updated 2026-07-17; keep it append-only.

---

### Task 1: Deterministic YouTube Helper Core

**Files:**
- Create: `scripts/youtube_capture_helper.py`
- Test: `tests/test_youtube_capture_helper.py`

**Interfaces:**
- Consumes: `urls_md_path: pathlib.Path`, YouTube playlist item JSON from Data API.
- Produces: `canonical_url(video_id: str) -> str`, `append_and_confirm(url: str, urls_md_path: Path) -> bool`, `parse_playlist_item(item: dict) -> dict`.

- [ ] **Step 1: Write failing URL and append tests**

```python
from pathlib import Path

import youtube_capture_helper as yt


def test_canonical_url_uses_watch_url():
    assert yt.canonical_url("abc123XYZ09") == "https://www.youtube.com/watch?v=abc123XYZ09"


def test_append_and_confirm_creates_parent_and_detects_duplicate(tmp_path):
    queue = tmp_path / "inbox" / "urls.md"
    url = "https://www.youtube.com/watch?v=abc123XYZ09"

    assert yt.append_and_confirm(url, queue) is True
    assert yt.is_duplicate(url, queue) is True
    assert queue.read_text(encoding="utf-8").splitlines() == [url]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_youtube_capture_helper.py::test_canonical_url_uses_watch_url tests/test_youtube_capture_helper.py::test_append_and_confirm_creates_parent_and_detects_duplicate -v`

Expected: FAIL with `ModuleNotFoundError` or missing functions.

- [ ] **Step 3: Implement minimal helper functions**

```python
# scripts/youtube_capture_helper.py
import argparse
import json
import sys
from pathlib import Path


def canonical_url(video_id: str) -> str:
    video_id = video_id.strip()
    if not video_id:
        raise ValueError("missing YouTube video id")
    return f"https://www.youtube.com/watch?v={video_id}"


def is_duplicate(url: str, urls_md_path: Path) -> bool:
    if not urls_md_path.exists():
        return False
    return url in (line.strip() for line in urls_md_path.read_text(encoding="utf-8").splitlines())


def append_and_confirm(url: str, urls_md_path: Path) -> bool:
    urls_md_path.parent.mkdir(parents=True, exist_ok=True)
    if is_duplicate(url, urls_md_path):
        return True
    with urls_md_path.open("a", encoding="utf-8") as f:
        f.write(url + "\n")
    return is_duplicate(url, urls_md_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_youtube_capture_helper.py::test_canonical_url_uses_watch_url tests/test_youtube_capture_helper.py::test_append_and_confirm_creates_parent_and_detects_duplicate -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/youtube_capture_helper.py tests/test_youtube_capture_helper.py
git commit -m "feat: add youtube capture helper core"
```

---

### Task 2: YouTube API Pagination and Playlist Item Parsing

**Files:**
- Modify: `scripts/youtube_capture_helper.py`
- Test: `tests/test_youtube_capture_helper.py`

**Interfaces:**
- Consumes: `api_get(path: str, params: dict, token: str) -> dict` injected into `list_playlist_items`.
- Produces: `list_playlist_items(playlist_id: str, token: str, limit: int, api_get=_api_get) -> list[dict]` returning dictionaries with `playlist_item_id`, `video_id`, `title`, `url`.

- [ ] **Step 1: Write failing pagination test**

```python
def test_list_playlist_items_paginates_and_extracts_video_urls():
    calls = []

    def fake_get(path, params, token):
        calls.append((path, params.copy(), token))
        if "pageToken" not in params:
            return {
                "nextPageToken": "NEXT",
                "items": [{"id": "pli_1", "snippet": {"title": "One", "resourceId": {"videoId": "vid1"}}}],
            }
        return {"items": [{"id": "pli_2", "snippet": {"title": "Two", "resourceId": {"videoId": "vid2"}}}]}

    items = yt.list_playlist_items("PL_QUEUE", "TOKEN", limit=2, api_get=fake_get)

    assert [item["url"] for item in items] == [
        "https://www.youtube.com/watch?v=vid1",
        "https://www.youtube.com/watch?v=vid2",
    ]
    assert calls[0][1]["maxResults"] == "50"
    assert calls[1][1]["pageToken"] == "NEXT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_youtube_capture_helper.py::test_list_playlist_items_paginates_and_extracts_video_urls -v`

Expected: FAIL with `AttributeError: module ... has no attribute 'list_playlist_items'`.

- [ ] **Step 3: Implement API GET and pagination**

```python
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://www.googleapis.com/youtube/v3"


def _api_get(path: str, params: dict[str, str], token: str) -> dict:
    url = f"{API_ROOT}/{path}?{urlencode(params)}"
    req = Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_playlist_item(item: dict) -> dict:
    video_id = item.get("snippet", {}).get("resourceId", {}).get("videoId")
    if not video_id:
        raise ValueError(f"playlist item has no videoId: {item.get('id')}")
    return {
        "playlist_item_id": item["id"],
        "video_id": video_id,
        "title": item.get("snippet", {}).get("title") or video_id,
        "url": canonical_url(video_id),
    }


def list_playlist_items(playlist_id: str, token: str, limit: int, api_get=_api_get) -> list[dict]:
    out = []
    page_token = None
    while len(out) < limit:
        params = {"part": "snippet", "playlistId": playlist_id, "maxResults": "50"}
        if page_token:
            params["pageToken"] = page_token
        data = api_get("playlistItems", params, token)
        for item in data.get("items", []):
            out.append(parse_playlist_item(item))
            if len(out) >= limit:
                break
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_youtube_capture_helper.py::test_list_playlist_items_paginates_and_extracts_video_urls -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/youtube_capture_helper.py tests/test_youtube_capture_helper.py
git commit -m "feat: list youtube queue playlist items"
```

---

### Task 3: Safe Capture and Delete Marker

**Files:**
- Modify: `scripts/youtube_capture_helper.py`
- Test: `tests/test_youtube_capture_helper.py`

**Interfaces:**
- Consumes: parsed playlist items from Task 2.
- Produces: `capture_items(items, urls_md_path, token, dry_run=False, api_delete=_api_delete) -> dict`.

- [ ] **Step 1: Write failing safe-delete tests**

```python
def test_capture_appends_before_delete(tmp_path):
    deleted = []
    queue = tmp_path / "urls.md"
    items = [{"playlist_item_id": "pli_1", "url": "https://www.youtube.com/watch?v=vid1", "title": "One"}]

    result = yt.capture_items(items, queue, "TOKEN", api_delete=lambda item_id, token: deleted.append((item_id, token)))

    assert result == {"captured": ["https://www.youtube.com/watch?v=vid1"], "count": 1, "dry_run": False}
    assert queue.read_text(encoding="utf-8").strip() == "https://www.youtube.com/watch?v=vid1"
    assert deleted == [("pli_1", "TOKEN")]


def test_capture_dry_run_never_writes_or_deletes(tmp_path):
    deleted = []
    queue = tmp_path / "urls.md"
    items = [{"playlist_item_id": "pli_1", "url": "https://www.youtube.com/watch?v=vid1", "title": "One"}]

    result = yt.capture_items(items, queue, "TOKEN", dry_run=True, api_delete=lambda item_id, token: deleted.append(item_id))

    assert result["captured"] == ["https://www.youtube.com/watch?v=vid1"]
    assert result["dry_run"] is True
    assert not queue.exists()
    assert deleted == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_youtube_capture_helper.py::test_capture_appends_before_delete tests/test_youtube_capture_helper.py::test_capture_dry_run_never_writes_or_deletes -v`

Expected: FAIL with missing `capture_items`.

- [ ] **Step 3: Implement delete and capture logic**

```python
from urllib.error import HTTPError


def _api_delete(playlist_item_id: str, token: str) -> None:
    url = f"{API_ROOT}/playlistItems?{urlencode({'id': playlist_item_id})}"
    req = Request(url, method="DELETE", headers={"Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=30) as resp:
        if resp.status not in (200, 204):
            raise RuntimeError(f"playlistItems.delete returned HTTP {resp.status}")


def capture_items(items: list[dict], urls_md_path: Path, token: str, dry_run: bool = False,
                  api_delete=_api_delete) -> dict:
    captured = []
    for item in items:
        url = item["url"]
        if dry_run:
            captured.append(url)
            continue
        if append_and_confirm(url, urls_md_path):
            api_delete(item["playlist_item_id"], token)
            if not is_duplicate(url, urls_md_path):
                raise RuntimeError(f"queue append disappeared before delete confirmation: {url}")
            captured.append(url)
    return {"captured": captured, "count": len(captured), "dry_run": dry_run}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_youtube_capture_helper.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/youtube_capture_helper.py tests/test_youtube_capture_helper.py
git commit -m "feat: capture youtube playlist items safely"
```

---

### Task 4: CLI Contract and Workspace Resolution

**Files:**
- Modify: `scripts/youtube_capture_helper.py`
- Test: `tests/test_youtube_capture_helper.py`

**Interfaces:**
- Consumes: `READ_VIDEO_YOUTUBE_ACCESS_TOKEN`, `workspace.json` or explicit `--urls-md`, explicit `--playlist-id`.
- Produces: CLI command `process --playlist-id PL_QUEUE --urls-md path --limit N [--dry-run]` printing JSON.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_cli_requires_token(monkeypatch, capsys):
    monkeypatch.delenv("READ_VIDEO_YOUTUBE_ACCESS_TOKEN", raising=False)
    rc = yt.main(["process", "--playlist-id", "PL", "--urls-md", "urls.md", "--limit", "1"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "READ_VIDEO_YOUTUBE_ACCESS_TOKEN" in out


def test_cli_dry_run_prints_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("READ_VIDEO_YOUTUBE_ACCESS_TOKEN", "TOKEN")
    monkeypatch.setattr(yt, "list_playlist_items", lambda playlist_id, token, limit: [
        {"playlist_item_id": "pli", "url": "https://www.youtube.com/watch?v=vid", "title": "Video"}
    ])
    rc = yt.main(["process", "--playlist-id", "PL", "--urls-md", str(tmp_path / "urls.md"), "--limit", "1", "--dry-run"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["dry_run"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_youtube_capture_helper.py::test_cli_requires_token tests/test_youtube_capture_helper.py::test_cli_dry_run_prints_json -v`

Expected: FAIL with missing CLI behavior.

- [ ] **Step 3: Implement CLI**

```python
def _token_from_env() -> str:
    token = os.environ.get("READ_VIDEO_YOUTUBE_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("READ_VIDEO_YOUTUBE_ACCESS_TOKEN is required; use OAuth setup docs to mint one")
    return token


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="youtube_capture_helper")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("process", help="capture URLs from a YouTube queue playlist")
    p.add_argument("--playlist-id", required=True)
    p.add_argument("--urls-md", required=True)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        token = _token_from_env()
        items = list_playlist_items(args.playlist_id, token, args.limit)
        result = capture_items(items, Path(args.urls_md), token, dry_run=args.dry_run)
    except Exception as ex:
        print(json.dumps({"error": str(ex)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_youtube_capture_helper.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/youtube_capture_helper.py tests/test_youtube_capture_helper.py
git commit -m "feat: add youtube capture helper cli"
```

---

### Task 5: Command and Documentation

**Files:**
- Create: `.claude/commands/youtube-capture.md`
- Modify: `README.md`
- Modify: `docs/ROADMAP.md`
- Test: `tests/test_youtube_capture_helper.py`

**Interfaces:**
- Consumes: implemented CLI from Task 4.
- Produces: user-facing `/youtube-capture N [--dry-run]` workflow contract.

- [ ] **Step 1: Add command contract**

```markdown
---
description: Capture up to N video URLs from a configured private YouTube queue playlist into read-video's inbox queue. Add --dry-run to preview without writing or removing anything.
---

Parse `$ARGUMENTS` as `N` (default 20) plus optional `--dry-run`.

1. Read the installed `read-video` skill's `workspace.json` and resolve `<inbox_dir>/urls.md`.
2. Require a configured YouTube queue playlist ID and `READ_VIDEO_YOUTUBE_ACCESS_TOKEN`.
3. Run `python scripts/youtube_capture_helper.py process --playlist-id <playlist_id> --urls-md <urls_md_path> --limit <N> [--dry-run]`.
4. For dry run, report the URLs and do not process them.
5. For live run, report the captured URLs and remind the user to run the normal read-video pipeline against the queue.
```

- [ ] **Step 2: Document setup in README**

Add a section after Instagram capture:

```markdown
## YouTube capture (optional)

YouTube capture uses the official YouTube Data API against a user-created private playlist such as `Read Video Queue`. It does **not** use Watch Later: current YouTube Data API docs report Watch Later playlist items as inaccessible through `playlistItems.list`.

The helper appends each video URL to `inbox_dir/urls.md` before deleting the playlist item, so the playlist remains a visible pending queue.
```

- [ ] **Step 3: Update ROADMAP Phase 2.5**

Replace Watch Later wording with private playlist wording and link back to the 2026-07-17 ADR in `docs/decisions.md`.

- [ ] **Step 4: Run validation**

Run: `pytest tests/test_youtube_capture_helper.py tests/test_skill_md_wording.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/youtube-capture.md README.md docs/ROADMAP.md docs/decisions.md
git commit -m "docs: plan youtube private playlist capture"
```

---

## Self-Review

**Spec coverage:** This plan covers the YouTube official-API decision, the updated private-playlist source, append-before-remove safety, dry-run behavior, queue reuse, and docs. It deliberately does not build a generic capture interface.

**Placeholder scan:** No TBD/TODO/fill-in placeholders remain. The only external setup is OAuth token creation, documented as an explicit prerequisite because tokens must not live in the repo.

**Type consistency:** `list_playlist_items` returns parsed dictionaries consumed by `capture_items`; CLI calls both by those exact names. `playlist_item_id`, `url`, and `title` are consistent across tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-17-youtube-private-playlist-capture-adapter.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints