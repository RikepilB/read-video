# Upstream v0.2.0 Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port frame dedup, Whisper API auto-chunking, `--timestamps` pinned frames, subprocess hardening, and a no-network pytest suite from `bradautomates/claude-video` v0.2.0 into `skill/scripts/video.py`.

**Architecture:** All runtime changes land in the single-file CLI `skill/scripts/video.py`. Frame extraction oversamples (2× budget) via the existing parallel fast-seek, then a perceptual dedup pass (one ffmpeg rawvideo run → 16×16 grayscale thumbnails → greedy mean-abs-diff) discards near-duplicates before the budget cap. API transcription splits oversized mp3s into even chunks and shifts timestamps back into source time. A new `tests/` directory holds pytest tests using ffmpeg-synthesized fixtures — no network.

**Tech Stack:** Python 3.12 stdlib only at runtime (ffmpeg/ffprobe/yt-dlp subprocesses). pytest as the only dev dependency.

**Spec:** `docs/superpowers/specs/2026-07-01-upstream-v020-port-design.md`

## Global Constraints

- **Zero-cost path stays the default and fully functional**: captions + local `faster-whisper` must work end to end with no API key present. Paid backends stay strictly opt-in behind the cost gate; nothing may route audio to a paid API without it.
- **API keys come from real environment variables only.** Never read `.env` files (see `skill/references/backends.md`).
- **No new runtime dependencies.** Dedup thumbnails come from an ffmpeg pass, not Pillow. pytest is dev-only.
- **`skill/scripts/video.py` stays a single file.** Match its existing style: section-comment banners, terse docstrings explaining *why*, `run_cmd()` for text subprocess calls.
- **No full-stream decode in the default path.** Frame extraction stays parallel fast-seek; wall-clock scales with frame count, not duration.
- **Windows dev machine**: invoke Python as `python`, not `python3`. Repo path contains spaces — always quote.
- **Git**: work on branch `upstream-v020-port` (already checked out). Commit after every task. Never commit to `main`.
- **Live install untouched until the end**: only Task 10 copies files to `~/.claude/skills/read-video/`.
- Repo root: `C:\Users\a2021\OneDrive\Escritorio\Vibe projects workspace\PROYECTOS\read-video`. All paths below are relative to it. Run all commands from the repo root.

---

### Task 1: Test scaffolding + `_parse_timestamp`

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_timestamps.py`
- Modify: `skill/scripts/video.py` (add `_parse_timestamp` after `_ts`, near line 491)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `video._parse_timestamp(value: str) -> float` (raises `ValueError` on bad input). `tests/conftest.py` fixtures for all later tasks: `static_clip` (8s single blue color, 10fps mp4), `scene_clip` (6s red→green→blue, 2s each, 10fps mp4), `tone_mp3` (30s 440Hz mono 64kbps mp3), marker `requires_ffmpeg`, and the `sys.path` insert that makes `import video` work.

- [ ] **Step 1: Ensure pytest is installed**

Run: `python -m pytest --version`
If it errors: `python -m pip install pytest`

- [ ] **Step 2: Write conftest with ffmpeg-synthesized fixtures**

Create `tests/conftest.py`:

```python
"""Shared fixtures. All media is synthesized locally with ffmpeg — no network, no real videos."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skill" / "scripts"))

HAVE_FFMPEG = shutil.which("ffmpeg") is not None
requires_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not on PATH")


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                   check=True, capture_output=True)


@pytest.fixture(scope="session")
def static_clip(tmp_path_factory) -> Path:
    """8s of a single solid color — every frame is a near-duplicate."""
    out = tmp_path_factory.mktemp("clips") / "static.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=320x240:d=8:r=10",
            "-pix_fmt", "yuv420p", str(out))
    return out


@pytest.fixture(scope="session")
def scene_clip(tmp_path_factory) -> Path:
    """6s: red -> green -> blue, 2s each — three visually distinct scenes."""
    out = tmp_path_factory.mktemp("clips") / "scenes.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=red:s=320x240:d=2:r=10",
            "-f", "lavfi", "-i", "color=c=green:s=320x240:d=2:r=10",
            "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=2:r=10",
            "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0",
            "-pix_fmt", "yuv420p", str(out))
    return out


@pytest.fixture(scope="session")
def tone_mp3(tmp_path_factory) -> Path:
    """30s 440Hz sine, mono 16kHz 64kbps — same encode profile as _to_audio()."""
    out = tmp_path_factory.mktemp("audio") / "tone.mp3"
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=30",
            "-ac", "1", "-ar", "16000", "-b:a", "64k", str(out))
    return out
```

- [ ] **Step 3: Write the failing tests for `_parse_timestamp`**

Create `tests/test_timestamps.py`:

```python
import pytest
import video


@pytest.mark.parametrize("raw,expected", [
    ("75", 75.0),
    ("01:15", 75.0),
    ("1:15", 75.0),
    ("00:01:15", 75.0),
    ("1:01:15", 3675.0),
    ("12.5", 12.5),
    ("00:12.5", 12.5),
    (" 01:15 ", 75.0),
])
def test_parse_timestamp_ok(raw, expected):
    assert video._parse_timestamp(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "1:2:3:4", "-5", "1:-2", "1:xx"])
def test_parse_timestamp_rejects(raw):
    with pytest.raises(ValueError):
        video._parse_timestamp(raw)
```

- [ ] **Step 4: Run to verify failure**

Run: `python -m pytest tests/test_timestamps.py -v`
Expected: FAIL — `AttributeError: module 'video' has no attribute '_parse_timestamp'`

- [ ] **Step 5: Implement `_parse_timestamp`**

In `skill/scripts/video.py`, directly after the `_ts` function (around line 491):

```python
def _parse_timestamp(value: str) -> float:
    """Parse 'SS', 'MM:SS', or 'HH:MM:SS' (each part may carry .ms) into seconds."""
    s = str(value).strip()
    parts = s.split(":") if s else []
    if not parts or len(parts) > 3:
        raise ValueError(f"bad timestamp: {value!r} (want SS, MM:SS, or HH:MM:SS)")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        raise ValueError(f"bad timestamp: {value!r} (want SS, MM:SS, or HH:MM:SS)")
    if any(x < 0 for x in nums):
        raise ValueError(f"bad timestamp: {value!r} (negative component)")
    sec = 0.0
    for x in nums:
        sec = sec * 60 + x
    return sec
```

- [ ] **Step 6: Run to verify pass**

Run: `python -m pytest tests/test_timestamps.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py tests/test_timestamps.py skill/scripts/video.py
git commit -m "test: pytest scaffolding with ffmpeg fixtures; add _parse_timestamp"
```

---

### Task 2: Subprocess path hardening

**Files:**
- Create: `tests/test_hardening.py`
- Modify: `skill/scripts/video.py` — `ffprobe_local` (line 119), `run` media assignment (line 279), `_to_audio` (line 476)

**Interfaces:**
- Consumes: conftest `sys.path` insert.
- Produces: local media paths are always absolute (`Path(p).resolve()`) before entering ffmpeg/ffprobe argv, so a relative name starting with `-` can never be parsed as a flag. No signature changes.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hardening.py`:

```python
import json
from pathlib import Path

import video


def test_is_url_accepts_http_https():
    assert video.is_url("https://youtube.com/watch?v=x")
    assert video.is_url("HTTP://example.com/a.mp4")


def test_is_url_rejects_non_urls():
    assert not video.is_url("-malicious.mp4")
    assert not video.is_url("file.mp4")
    assert not video.is_url("ftp://host/x")
    assert not video.is_url("")


def test_ffprobe_local_resolves_path(monkeypatch, tmp_path):
    """The path handed to ffprobe must be absolute even when the caller passes a relative one."""
    seen = {}

    def fake_run_cmd(args):
        seen["args"] = args

        class CP:
            returncode = 0
            stdout = json.dumps({"format": {"duration": "1.0"}, "streams": []})
            stderr = ""
        return CP()

    monkeypatch.setattr(video, "run_cmd", fake_run_cmd)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "-rel.mp4").write_bytes(b"x")
    video.ffprobe_local("-rel.mp4")
    probed = seen["args"][-1]
    assert Path(probed).is_absolute()
    assert not probed.startswith("-")


def test_to_audio_resolves_src(monkeypatch, tmp_path):
    seen = {}

    def fake_run_cmd(args):
        seen["args"] = args
        # satisfy the exists/size check after "encoding"
        Path(args[-1]).write_bytes(b"mp3")

        class CP:
            returncode = 0
            stdout = ""
            stderr = ""
        return CP()

    monkeypatch.setattr(video, "run_cmd", fake_run_cmd)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "-src.mp4").write_bytes(b"x")
    video._to_audio("-src.mp4", tmp_path)
    i = seen["args"].index("-i")
    src_arg = seen["args"][i + 1]
    assert Path(src_arg).is_absolute()
    assert not src_arg.startswith("-")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_hardening.py -v`
Expected: `test_is_url_*` PASS already; `test_ffprobe_local_resolves_path` and `test_to_audio_resolves_src` FAIL (path still relative).

- [ ] **Step 3: Implement the hardening**

In `ffprobe_local` (line 119), resolve before building argv:

```python
def ffprobe_local(path: str) -> dict[str, Any]:
    path = str(Path(path).resolve())      # a relative name starting with '-' must not read as a flag
    cp = run_cmd(["ffprobe", "-v", "quiet", "-print_format", "json",
                  "-show_format", "-show_streams", path])
```

In `run` (line 279), resolve the local-media branch:

```python
    if need_media:
        media = _download(inp, wd) if info["source"] == "url" else str(Path(inp).resolve())
```

In `_to_audio` (line 476), resolve `src` before the ffmpeg call:

```python
def _to_audio(src: str, wd: Path) -> str:
    """Mono 16kHz 64kbps mp3 — ~0.5 MB/min, so ~50 min fits the providers' ~25 MB upload cap.
    (wav would be ~1.9 MB/min and blow the cap after ~13 min.)"""
    src = str(Path(src).resolve())
    out = str(wd / "audio.mp3")
```

(yt-dlp needs no change: `URL_RE = ^https?://` already guarantees only `http(s)://` strings reach it.)

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_hardening.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_hardening.py skill/scripts/video.py
git commit -m "fix: resolve local media paths before ffmpeg/ffprobe argv (option-injection hardening)"
```

---

### Task 3: Dedup core — `_frame_delta` + `_dedupe_jobs`

**Files:**
- Create: `tests/test_dedup.py`
- Modify: `skill/scripts/video.py` (new dedup section between the `_extract_frames_filter` function and the transcription banner, ~line 365)

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `video._DEDUP_THUMB = 16`, `video._DEDUP_THRESHOLD = 2.0` (module constants)
  - `video._frame_delta(a: bytes, b: bytes) -> float` — mean abs per-pixel diff, `inf` on length mismatch/empty
  - `video._dedupe_jobs(jobs, thumbs, threshold=_DEDUP_THRESHOLD) -> tuple[list, int]` where `jobs` is a chronological `list[tuple[float, Path, bool]]` (`(t_seconds, file_path, pinned)`). Greedy-drops non-pinned near-duplicates of the last kept frame, deletes dropped files, returns `(kept_jobs, dropped_count)`. Fail-open: thumb/job length mismatch returns input unchanged.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dedup.py`:

```python
from pathlib import Path

import video

T = video._DEDUP_THUMB * video._DEDUP_THUMB  # 256 bytes per thumbnail


def thumb(val: int) -> bytes:
    return bytes([val]) * T


def jobs_for(tmp_path: Path, n: int):
    out = []
    for i in range(n):
        fp = tmp_path / f"frame_{i + 1:04d}.jpg"
        fp.write_bytes(b"jpeg")
        out.append((float(i), fp, False))
    return out


def test_frame_delta_identical_is_zero():
    assert video._frame_delta(thumb(100), thumb(100)) == 0.0


def test_frame_delta_known_value():
    assert video._frame_delta(thumb(100), thumb(103)) == 3.0


def test_frame_delta_mismatch_is_inf():
    assert video._frame_delta(thumb(1), thumb(1)[:-1]) == float("inf")
    assert video._frame_delta(b"", b"") == float("inf")


def test_dedupe_drops_near_duplicates_and_deletes_files(tmp_path):
    jobs = jobs_for(tmp_path, 4)
    thumbs = [thumb(10), thumb(11), thumb(10), thumb(200)]  # deltas: 1, 1, 190
    kept, dropped = video._dedupe_jobs(jobs, thumbs)
    assert dropped == 2
    assert [j[0] for j in kept] == [0.0, 3.0]
    assert not jobs[1][1].exists() and not jobs[2][1].exists()
    assert jobs[0][1].exists() and jobs[3][1].exists()


def test_dedupe_compares_against_last_kept(tmp_path):
    """Slow drift: each step under threshold vs neighbor but eventually far from last kept."""
    jobs = jobs_for(tmp_path, 4)
    thumbs = [thumb(10), thumb(11), thumb(12), thumb(13)]  # all within 2.0 of neighbor; 13 is 3 from 10
    kept, dropped = video._dedupe_jobs(jobs, thumbs)
    assert [j[0] for j in kept] == [0.0, 3.0]
    assert dropped == 2


def test_dedupe_never_drops_pinned(tmp_path):
    jobs = jobs_for(tmp_path, 3)
    jobs[1] = (jobs[1][0], jobs[1][1], True)               # pin the middle duplicate
    thumbs = [thumb(10), thumb(10), thumb(10)]
    kept, dropped = video._dedupe_jobs(jobs, thumbs)
    assert [j[0] for j in kept] == [0.0, 1.0]
    assert dropped == 1


def test_dedupe_fail_open_on_mismatch(tmp_path):
    jobs = jobs_for(tmp_path, 3)
    kept, dropped = video._dedupe_jobs(jobs, [thumb(1)])   # 1 thumb for 3 jobs
    assert kept == jobs and dropped == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_dedup.py -v`
Expected: FAIL — `AttributeError: module 'video' has no attribute '_DEDUP_THUMB'`

- [ ] **Step 3: Implement**

In `skill/scripts/video.py`, after `_extract_frames_filter` (~line 365), add:

```python
# --------------------------------------------------------------------------- frame dedup
# Ported from bradautomates/claude-video v0.2.0 (MIT). Near-duplicate frames (held slides,
# static screens) waste the frame budget; a cheap perceptual pass drops them so the budget
# goes to distinct content. Thumbnails come from one ffmpeg rawvideo pass — no Pillow.
_DEDUP_THUMB = 16
_DEDUP_THRESHOLD = 2.0


def _frame_delta(a: bytes, b: bytes) -> float:
    """Mean absolute per-pixel difference (0-255) between two grayscale thumbnails.
    Mismatched lengths read as maximally different so a decode hiccup never collapses
    distinct frames."""
    if not a or len(a) != len(b):
        return float("inf")
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def _dedupe_jobs(jobs: list[tuple[float, Path, bool]], thumbs: list[bytes],
                 threshold: float = _DEDUP_THRESHOLD) -> tuple[list[tuple[float, Path, bool]], int]:
    """Greedily drop frames within `threshold` of the last *kept* frame.

    `jobs` is chronological `(t_seconds, path, pinned)`. Pinned jobs are never dropped.
    Deletes dropped JPEGs. Fail-open: a thumbs/jobs length mismatch returns the input
    unchanged so extraction never breaks because of dedup."""
    if len(thumbs) != len(jobs) or len(jobs) <= 1:
        return jobs, 0
    kept = [jobs[0]]
    last = thumbs[0]
    dropped: list[tuple[float, Path, bool]] = []
    for job, tb in zip(jobs[1:], thumbs[1:]):
        if not job[2] and _frame_delta(tb, last) <= threshold:
            dropped.append(job)
        else:
            kept.append(job)
            last = tb
    for _t, fp, _pin in dropped:
        try:
            fp.unlink()
        except OSError:
            pass
    return kept, len(dropped)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_dedup.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_dedup.py skill/scripts/video.py
git commit -m "feat: perceptual frame-dedup core (delta math + greedy pass)"
```

---

### Task 4: Thumbnail pass — `_thumb_frames`

**Files:**
- Create: `tests/test_thumbs.py`
- Modify: `skill/scripts/video.py` (same dedup section, after `_frame_delta`)

**Interfaces:**
- Consumes: `_DEDUP_THUMB`.
- Produces: `video._thumb_frames(paths: list[Path]) -> list[bytes]` — one ffmpeg pass over a **contiguously numbered** JPEG sequence → one 256-byte grayscale thumbnail per input. Fail-open: any error (ffmpeg failure, unparseable name, byte-count mismatch, gap in numbering) returns `[]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_thumbs.py`:

```python
import subprocess
from pathlib import Path

import pytest

import video
from conftest import requires_ffmpeg


def make_jpegs(tmp_path: Path, colors: list[str]) -> list[Path]:
    out = []
    for i, c in enumerate(colors, start=1):
        fp = tmp_path / f"frame_{i:04d}.jpg"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", f"color=c={c}:s=64x64:d=0.1",
                        "-frames:v", "1", str(fp)], check=True, capture_output=True)
        out.append(fp)
    return out


@requires_ffmpeg
def test_thumbs_one_per_frame(tmp_path):
    paths = make_jpegs(tmp_path, ["black", "black", "white"])
    thumbs = video._thumb_frames(paths)
    assert len(thumbs) == 3
    assert all(len(t) == video._DEDUP_THUMB * video._DEDUP_THUMB for t in thumbs)
    assert video._frame_delta(thumbs[0], thumbs[1]) <= video._DEDUP_THRESHOLD
    assert video._frame_delta(thumbs[1], thumbs[2]) > video._DEDUP_THRESHOLD


@requires_ffmpeg
def test_thumbs_fail_open_on_bad_name(tmp_path):
    fp = tmp_path / "noindex.jpg"
    fp.write_bytes(b"not a jpeg")
    assert video._thumb_frames([fp]) == []


def test_thumbs_empty_input():
    assert video._thumb_frames([]) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_thumbs.py -v`
Expected: FAIL — `AttributeError: module 'video' has no attribute '_thumb_frames'`

- [ ] **Step 3: Implement**

In `skill/scripts/video.py`, after `_frame_delta`:

```python
def _thumb_frames(paths: list[Path]) -> list[bytes]:
    """Decode every frame in `paths` to a small grayscale thumbnail via ONE ffmpeg pass
    over the JPEG sequence (keeps us pure-stdlib — no Pillow). `paths` must be a
    contiguously numbered sequence (frame_0001.jpg, frame_0002.jpg, ...). Fail-open:
    any ffmpeg error, unparseable name, or byte-count mismatch returns [] so the caller
    skips dedup rather than breaking extraction."""
    if not paths:
        return []
    m = re.match(r"(.*?)(\d+)(\.[A-Za-z0-9]+)$", paths[0].name)
    if m is None:
        return []
    prefix, digits, ext = m.groups()
    pattern = str(paths[0].parent / f"{prefix}%0{len(digits)}d{ext}")
    cp = subprocess.run(                       # bytes out, so not run_cmd (which is text=True)
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-start_number", str(int(digits)), "-i", pattern,
         "-vf", f"scale={_DEDUP_THUMB}:{_DEDUP_THUMB},format=gray",
         "-f", "rawvideo", "-"],
        capture_output=True)
    size = _DEDUP_THUMB * _DEDUP_THUMB
    raw = cp.stdout
    if cp.returncode != 0 or len(raw) != size * len(paths):
        return []
    return [raw[i * size:(i + 1) * size] for i in range(len(paths))]
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_thumbs.py -v`
Expected: all PASS (skips if ffmpeg missing)

- [ ] **Step 5: Commit**

```bash
git add tests/test_thumbs.py skill/scripts/video.py
git commit -m "feat: single-pass ffmpeg grayscale thumbnails for frame dedup"
```

---

### Task 5: Wire oversample + dedup into `_extract_frames`

**Files:**
- Create: `tests/test_frames.py`
- Modify: `skill/scripts/video.py` — `_extract_frames` (line 307), `_extract_frames_filter` return shape untouched, `run` (lines 258–292), `main` (lines 709–728)

**Interfaces:**
- Consumes: `_dedupe_jobs`, `_thumb_frames`, `_ts`.
- Produces:
  - `_extract_frames(media, wd, n, start, window, target_w, dedup: bool = True, pins: list[float] | None = None) -> tuple[list[dict[str, Any]], int]` — returns `(entries, deduped_count)`. Entries are `{"file": str, "t": "MM:SS"}` plus `"pinned": True` on pinned frames.
  - Helpers `_reindex_jobs(jobs) -> jobs` (renames files to chronological `frame_0001.jpg…`, returns updated jobs) and `_cap_jobs(jobs, n) -> jobs` (even-samples down to `n`, never drops pinned, deletes culled files).
  - `run(...)` gains `timestamps: str | None = None, dedup: bool = True` keyword params; run JSON gains `"frames_deduped": int`. (Pin parsing inside `run` is Task 6 — this task only threads the `dedup` flag and the new return shape.)
  - CLI: `run` subcommand gains `--no-dedup`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_frames.py`:

```python
from pathlib import Path

import video
from conftest import requires_ffmpeg


@requires_ffmpeg
def test_static_clip_collapses(static_clip, tmp_path):
    entries, deduped = video._extract_frames(str(static_clip), tmp_path, 10, 0.0, 8.0, 128)
    assert deduped > 0
    assert len(entries) < 10                      # near-identical frames were dropped
    assert all(Path(e["file"]).exists() for e in entries)


@requires_ffmpeg
def test_scene_clip_keeps_distinct(scene_clip, tmp_path):
    entries, deduped = video._extract_frames(str(scene_clip), tmp_path, 6, 0.0, 6.0, 128)
    assert len(entries) >= 3                      # at least one frame per distinct scene


@requires_ffmpeg
def test_no_dedup_keeps_budget_count(static_clip, tmp_path):
    entries, deduped = video._extract_frames(str(static_clip), tmp_path, 10, 0.0, 8.0, 128,
                                             dedup=False)
    assert deduped == 0
    assert len(entries) == 10                     # oversampled then even-sampled back to budget


@requires_ffmpeg
def test_entries_are_contiguous_and_chronological(static_clip, tmp_path):
    entries, _ = video._extract_frames(str(static_clip), tmp_path, 10, 0.0, 8.0, 128)
    names = [Path(e["file"]).name for e in entries]
    assert names == [f"frame_{i:04d}.jpg" for i in range(1, len(entries) + 1)]
    times = [e["t"] for e in entries]
    assert times == sorted(times)


def test_cap_jobs_even_samples_and_keeps_pins(tmp_path):
    jobs = []
    for i in range(10):
        fp = tmp_path / f"frame_{i + 1:04d}.jpg"
        fp.write_bytes(b"j")
        jobs.append((float(i), fp, i == 7))       # pin t=7.0
    kept = video._cap_jobs(jobs, 4)
    assert len(kept) == 4
    assert any(j[2] for j in kept)                # pin survived
    assert sum(1 for j in jobs if j[1].exists()) == 4  # culled files deleted
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_frames.py -v`
Expected: FAIL — `_extract_frames` returns a list (not a tuple) and `_cap_jobs` doesn't exist.

- [ ] **Step 3: Implement — helpers first**

In the dedup section of `skill/scripts/video.py`, after `_thumb_frames`:

```python
def _reindex_jobs(jobs: list[tuple[float, Path, bool]]) -> list[tuple[float, Path, bool]]:
    """Rename to a chronological, gap-free frame_0001.jpg... sequence (required both by
    _thumb_frames' %04d input pattern and by the read-in-filename-order contract).
    Ascending rename is collision-safe: a frame only ever moves to an index <= its own."""
    out = []
    for i, (t, fp, pin) in enumerate(sorted(jobs), start=1):
        target = fp.with_name(f"frame_{i:04d}.jpg")
        if fp != target:
            fp.replace(target)
        out.append((t, target, pin))
    return out


def _cap_jobs(jobs: list[tuple[float, Path, bool]], n: int) -> list[tuple[float, Path, bool]]:
    """Even-sample chronological jobs down to n, never dropping pinned ones.
    Deletes culled JPEGs."""
    if len(jobs) <= n:
        return jobs
    pinned = [j for j in jobs if j[2]]
    others = [j for j in jobs if not j[2]]
    slots = max(0, n - len(pinned))
    keep_idx = {int(i * len(others) / slots) for i in range(slots)} if slots else set()
    kept, culled = [], []
    for i, j in enumerate(others):
        (kept if i in keep_idx else culled).append(j)
    for _t, fp, _pin in culled:
        try:
            fp.unlink()
        except OSError:
            pass
    return sorted(kept + pinned)


def _jobs_to_entries(jobs: list[tuple[float, Path, bool]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t, fp, pin in jobs:
        e: dict[str, Any] = {"file": str(fp), "t": _ts(t)}
        if pin:
            e["pinned"] = True
        out.append(e)
    return out
```

- [ ] **Step 4: Implement — rework `_extract_frames`**

Replace the whole `_extract_frames` function (line 307) with:

```python
def _extract_frames(media: str | None, wd: Path, n: int, start: float,
                    window: float, target_w: int, dedup: bool = True,
                    pins: list[float] | None = None) -> tuple[list[dict[str, Any]], int]:
    """Extract up to n frames: oversample 2x the budget with parallel fast seeks, drop
    perceptual near-duplicates, then even-sample down to the budget.

    Each frame is grabbed with a *fast input seek* (`-ss` before `-i`, one frame out) instead of a
    single `fps=` filter pass. The filter approach must decode the entire stream to drop all but n
    frames — on a long, high-fps source (e.g. 9 min @ 60 fps that's ~33k decoded frames) that is the
    dominant cost. Fast seeks jump near each target keyframe and decode ~1 frame, so cost scales with
    frame count, not duration. Oversampling (bounded by the same 2 fps cap as the budget) gives the
    dedup pass near-duplicates to discard, so the budget goes to distinct content instead of held
    slides. `pins` are exact-moment frames the caller reserved; they always survive dedup and the
    cap. Falls back to the whole-stream filter pass if seeking yields nothing (odd container)."""
    if not media:
        raise RuntimeError("frame extraction needs a media file")
    fdir = wd / "frames"
    fdir.mkdir(exist_ok=True)
    pins = sorted(pins or [])
    slots = max(0, n - len(pins))
    cand_n = max(slots, min(2 * slots, max(1, int(window * 2)))) if slots else 0
    interval = window / cand_n if cand_n else 0.0
    times = [(start + (k - 0.5) * interval, False) for k in range(1, cand_n + 1)]
    times += [(t, True) for t in pins]
    times.sort()
    jobs = [(t, fdir / f"frame_{i:04d}.jpg", pin) for i, (t, pin) in enumerate(times, start=1)]

    def grab(job: tuple[float, Path, bool]) -> tuple[tuple[float, Path, bool], bool]:
        t, fp, _pin = job
        cp = run_cmd(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                      "-ss", f"{t:.3f}", "-i", media, "-frames:v", "1", "-an",
                      "-vf", f"scale={target_w}:-2", "-q:v", "3", str(fp)])
        return job, cp.returncode == 0 and fp.exists()

    from concurrent.futures import ThreadPoolExecutor
    workers = max(2, min(8, (os.cpu_count() or 4)))
    ok: list[tuple[float, Path, bool]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for job, success in ex.map(grab, jobs):
            if success:
                ok.append(job)

    if not ok:                                    # seeking produced nothing — robust single-pass path
        return _extract_frames_filter(media, fdir, n, start, window, target_w), 0

    ok = _reindex_jobs(ok)                        # gap-free numbering for the thumbnail pass
    deduped = 0
    if dedup and len(ok) > 1:
        thumbs = _thumb_frames([fp for _t, fp, _p in ok])
        if thumbs:
            ok, deduped = _dedupe_jobs(ok, thumbs)
        else:
            print("[read-video] WARNING: thumbnail pass failed — dedup skipped", file=sys.stderr)
    ok = _cap_jobs(ok, n)
    return _jobs_to_entries(_reindex_jobs(ok)), deduped
```

- [ ] **Step 5: Thread the new shape through `run` and `main`**

In `run` (line 258), change the signature and the frames branch:

```python
def run(inp: str, tier: str = "both", frames: int | None = None, backend: str = "captions",
        start: float = 0.0, end: float | None = None,
        workdir: str | None = None, pr: dict[str, Any] | None = None,
        timestamps: str | None = None, dedup: bool = True) -> dict[str, Any]:
```

and:

```python
    if want_frames:
        result["frames"], result["frames_deduped"] = _extract_frames(
            media, wd, n, start, window,
            int(pr.get("frame", {}).get("target_width", 512)), dedup=dedup)
```

(`timestamps` is accepted but unused until Task 6.)

In `main`, add to the `run` subparser (after the `--workdir` line, ~line 716):

```python
    r.add_argument("--no-dedup", action="store_true",
                   help="keep every sampled frame (skip the near-duplicate drop)")
    r.add_argument("--timestamps", help="comma-separated SS/MM:SS/HH:MM:SS pins, e.g. 90,05:30")
```

and change the `run` dispatch (line 728):

```python
        elif a.cmd == "run":
            _emit(run(a.input, a.tier, a.frames, a.backend, a.start, a.end, a.workdir,
                      timestamps=a.timestamps, dedup=not a.no_dedup), a.human)
```

- [ ] **Step 6: Run to verify pass**

Run: `python -m pytest tests/test_frames.py tests/test_dedup.py tests/test_thumbs.py -v`
Expected: all PASS

- [ ] **Step 7: Smoke-test the CLI end to end (visual tier, free)**

Run (from repo root):
`python "skill/scripts/video.py" run "tests-smoke.mp4" --tier visual --frames 8` — but first synthesize the clip:

```bash
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "color=c=blue:s=320x240:d=8:r=10" -pix_fmt yuv420p tests-smoke.mp4
python "skill/scripts/video.py" run tests-smoke.mp4 --tier visual --frames 8
rm tests-smoke.mp4
```

Expected: JSON with `"frames_deduped"` > 0 and fewer than 8 frame entries. Do not commit `tests-smoke.mp4`.

- [ ] **Step 8: Commit**

```bash
git add tests/test_frames.py skill/scripts/video.py
git commit -m "feat: oversample + perceptual dedup in frame extraction (--no-dedup to disable)"
```

---

### Task 6: `--timestamps` pinned frames in `run`

**Files:**
- Create: `tests/test_pins.py`
- Modify: `skill/scripts/video.py` — `run` (pin parsing before the frames branch)

**Interfaces:**
- Consumes: `_parse_timestamp` (Task 1), `_extract_frames(..., pins=...)` (Task 5).
- Produces: `run(..., timestamps="90,05:30")` yields pinned entries (`"pinned": true`) in the manifest. Invalid entries → skipped with a stderr warning. Out-of-range (outside `[start, end]`) → skipped with warning. More pins than budget → first `n` in timestamp order kept, rest skipped with warning.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pins.py`:

```python
import json
from pathlib import Path

import video
from conftest import requires_ffmpeg


@requires_ffmpeg
def test_pins_appear_in_manifest(scene_clip, tmp_path):
    res = video.run(str(scene_clip), tier="visual", frames=5, workdir=str(tmp_path),
                    timestamps="1,05")
    pinned = [e for e in res["frames"] if e.get("pinned")]
    assert len(pinned) == 2
    assert {e["t"] for e in pinned} == {"00:01", "00:05"}
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert sum(1 for e in manifest["frames"] if e.get("pinned")) == 2


@requires_ffmpeg
def test_bad_and_out_of_range_pins_skipped(scene_clip, tmp_path, capsys):
    res = video.run(str(scene_clip), tier="visual", frames=5, workdir=str(tmp_path),
                    timestamps="abc,99:99:99,2")
    pinned = [e for e in res["frames"] if e.get("pinned")]
    assert len(pinned) == 1                        # only "2" is valid and in range
    err = capsys.readouterr().err
    assert "abc" in err and "skipped" in err


@requires_ffmpeg
def test_pin_overflow_keeps_first_budget_pins(scene_clip, tmp_path, capsys):
    res = video.run(str(scene_clip), tier="visual", frames=2, workdir=str(tmp_path),
                    timestamps="1,2,3,4,5")
    pinned = [e for e in res["frames"] if e.get("pinned")]
    assert len(pinned) == 2
    assert {e["t"] for e in pinned} == {"00:01", "00:02"}
    assert "exceed" in capsys.readouterr().err
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_pins.py -v`
Expected: FAIL — no pinned entries (the `timestamps` param is accepted but ignored).

- [ ] **Step 3: Implement pin parsing in `run`**

In `run`, after `n = frames if frames else adaptive_frames(window)` and before the workdir setup, add:

```python
    pins: list[float] = []
    if timestamps:
        for tok in timestamps.split(","):
            try:
                t = _parse_timestamp(tok)
            except ValueError:
                print(f"[read-video] WARNING: --timestamps entry {tok.strip()!r} invalid — skipped",
                      file=sys.stderr)
                continue
            if not (start <= t <= end):
                print(f"[read-video] WARNING: --timestamps {tok.strip()} outside "
                      f"[{start:.0f}, {end:.0f}]s — skipped", file=sys.stderr)
                continue
            pins.append(t)
        pins.sort()
        if len(pins) > n:
            print(f"[read-video] WARNING: {len(pins)} pins exceed the frame budget ({n}) — "
                  f"keeping the first {n}", file=sys.stderr)
            pins = pins[:n]
```

and pass them to the extractor:

```python
    if want_frames:
        result["frames"], result["frames_deduped"] = _extract_frames(
            media, wd, n, start, window,
            int(pr.get("frame", {}).get("target_width", 512)), dedup=dedup, pins=pins)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_pins.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_pins.py skill/scripts/video.py
git commit -m "feat: --timestamps pinned frames (budget-reserved, dedup-immune)"
```

---

### Task 7: Audio chunk splitting — `_split_audio`

**Files:**
- Create: `tests/test_chunking.py`
- Modify: `skill/scripts/video.py` (transcription section, before `_api_transcribe`)

**Interfaces:**
- Consumes: `run_cmd`, `tone_mp3` fixture.
- Produces:
  - `video._API_UPLOAD_CAP = 24 * 1024 * 1024` (module constant; 1 MB of headroom under the providers' 25 MB cap)
  - `video._audio_duration(path: str) -> float`
  - `video._split_audio(audio: str, max_bytes: int = _API_UPLOAD_CAP) -> list[tuple[str, float]]` — `[(chunk_path, start_offset_seconds)]`; a file already under the cap returns `[(audio, 0.0)]` untouched. Chunks land next to the source as `audio_chunk_000.mp3`, `audio_chunk_001.mp3`, ….

- [ ] **Step 1: Write the failing tests**

Create `tests/test_chunking.py`:

```python
from pathlib import Path

import pytest

import video
from conftest import requires_ffmpeg


@requires_ffmpeg
def test_small_file_passes_through(tone_mp3):
    assert video._split_audio(str(tone_mp3)) == [(str(tone_mp3), 0.0)]


@requires_ffmpeg
def test_oversized_file_splits_under_cap(tone_mp3, tmp_path):
    work = tmp_path / "audio.mp3"
    work.write_bytes(tone_mp3.read_bytes())
    cap = work.stat().st_size // 3                 # force >= 3 chunks from the 30s tone
    chunks = video._split_audio(str(work), max_bytes=cap)
    assert len(chunks) >= 3
    for path, _off in chunks:
        assert Path(path).stat().st_size <= cap * 1.15   # segment split is approximate; small slack


@requires_ffmpeg
def test_offsets_accumulate_to_duration(tone_mp3, tmp_path):
    work = tmp_path / "audio.mp3"
    work.write_bytes(tone_mp3.read_bytes())
    cap = work.stat().st_size // 3
    chunks = video._split_audio(str(work), max_bytes=cap)
    assert chunks[0][1] == 0.0
    offs = [off for _p, off in chunks]
    assert offs == sorted(offs)
    total = chunks[-1][1] + video._audio_duration(chunks[-1][0])
    assert total == pytest.approx(30.0, abs=1.5)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_chunking.py -v`
Expected: FAIL — `AttributeError: module 'video' has no attribute '_split_audio'`

- [ ] **Step 3: Implement**

In `skill/scripts/video.py`, in the transcription section just before `_api_transcribe`, add:

```python
# Providers cap uploads at ~25 MB; keep 1 MB of headroom so a rounding wobble never 413s.
_API_UPLOAD_CAP = 24 * 1024 * 1024


def _audio_duration(path: str) -> float:
    cp = run_cmd(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format",
                  str(Path(path).resolve())])
    if cp.returncode != 0:
        raise RuntimeError(f"ffprobe on audio failed: {cp.stderr.strip()[:200]}")
    return float(json.loads(cp.stdout).get("format", {}).get("duration") or 0.0)


def _split_audio(audio: str, max_bytes: int = _API_UPLOAD_CAP) -> list[tuple[str, float]]:
    """Split an mp3 into even chunks each under max_bytes -> [(path, start_offset_s)].

    Ported from claude-video v0.2.0: length alone must never break API transcription.
    Stream-copy segmenting (no re-encode) is cheap and mp3 frames split cleanly. Offsets
    come from ffprobe on each real chunk (not arithmetic), so timestamp shifts stay exact
    even when the muxer lands segment boundaries off the requested time."""
    size = Path(audio).stat().st_size
    if size <= max_bytes:
        return [(audio, 0.0)]
    dur = _audio_duration(audio)
    n_chunks = max(2, math.ceil(size * 1.05 / max_bytes))   # +5% so rounding never overshoots the cap
    outpat = str(Path(audio).with_name("audio_chunk_%03d.mp3"))
    cp = run_cmd(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                  "-i", str(Path(audio).resolve()),
                  "-f", "segment", "-segment_time", f"{dur / n_chunks:.3f}",
                  "-c", "copy", outpat])
    if cp.returncode != 0:
        raise RuntimeError(f"audio chunking failed: {cp.stderr.strip()[:200]}")
    chunks = sorted(Path(audio).parent.glob("audio_chunk_*.mp3"))
    if not chunks:
        raise RuntimeError("audio chunking produced no files")
    out: list[tuple[str, float]] = []
    offset = 0.0
    for c in chunks:
        out.append((str(c), offset))
        offset += _audio_duration(str(c))
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_chunking.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_chunking.py skill/scripts/video.py
git commit -m "feat: even-split audio chunking with exact ffprobe offsets"
```

---

### Task 8: Chunked API transcription with gap tolerance

**Files:**
- Modify: `tests/test_chunking.py` (append tests)
- Modify: `skill/scripts/video.py` — `_resp_to_text` (line 605), `_api_transcribe` (line 613)

**Interfaces:**
- Consumes: `_split_audio` (Task 7), `BACKEND_API`.
- Produces:
  - `_resp_to_text(data: dict, offset: float = 0.0) -> str` — segment timestamps shifted by `offset`.
  - `_api_request(backend: str, audio: str) -> dict[str, Any]` — the former body of `_api_transcribe` (multipart build + retries), returning parsed JSON instead of text.
  - `_api_transcribe(backend: str, audio: str) -> str` — unchanged public signature. Splits, transcribes per chunk, shifts, merges. A failed chunk becomes `[transcription gap: chunk N of M failed: <err>]`; raises only when **every** chunk fails (so a backend chain still falls through).
  - Gemini stays unchunked: its Files API has no 25 MB cap (deviation from the spec's backend list, documented in Task 10).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_chunking.py`:

```python
def seg_response(*starts_texts):
    return {"segments": [{"start": s, "text": t} for s, t in starts_texts]}


def test_resp_to_text_shifts_offsets():
    out = video._resp_to_text(seg_response((0.0, "hello"), (65.0, "world")), offset=120.0)
    assert out.splitlines() == ["[02:00] hello", "[03:05] world"]


def test_chunked_transcribe_merges_with_shifts(monkeypatch, tmp_path):
    a = tmp_path / "audio.mp3"
    a.write_bytes(b"x")
    monkeypatch.setattr(video, "_split_audio",
                        lambda audio, max_bytes=video._API_UPLOAD_CAP:
                        [(str(a), 0.0), (str(a), 100.0)])
    responses = iter([seg_response((1.0, "one")), seg_response((2.0, "two"))])
    monkeypatch.setattr(video, "_api_request", lambda b, p: next(responses))
    out = video._api_transcribe("groq", str(a))
    assert out.splitlines() == ["[00:01] one", "[01:42] two"]


def test_partial_chunk_failure_leaves_gap_marker(monkeypatch, tmp_path, capsys):
    a = tmp_path / "audio.mp3"
    a.write_bytes(b"x")
    monkeypatch.setattr(video, "_split_audio",
                        lambda audio, max_bytes=video._API_UPLOAD_CAP:
                        [(str(a), 0.0), (str(a), 100.0), (str(a), 200.0)])
    calls = {"n": 0}

    def fake_request(backend, path):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("HTTP 500")
        return seg_response((0.0, f"part{calls['n']}"))

    monkeypatch.setattr(video, "_api_request", fake_request)
    out = video._api_transcribe("groq", str(a))
    lines = out.splitlines()
    assert lines[0] == "[00:00] part1"
    assert "transcription gap: chunk 2 of 3" in lines[1]
    assert lines[2] == "[03:20] part3"


def test_all_chunks_fail_raises(monkeypatch, tmp_path):
    a = tmp_path / "audio.mp3"
    a.write_bytes(b"x")
    monkeypatch.setattr(video, "_split_audio",
                        lambda audio, max_bytes=video._API_UPLOAD_CAP:
                        [(str(a), 0.0), (str(a), 100.0)])

    def boom(backend, path):
        raise RuntimeError("HTTP 500")

    monkeypatch.setattr(video, "_api_request", boom)
    import pytest as _pytest
    with _pytest.raises(RuntimeError, match="all 2 chunks failed"):
        video._api_transcribe("groq", str(a))
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_chunking.py -v`
Expected: new tests FAIL (`_resp_to_text` takes no `offset`; `_api_request` doesn't exist). Task 7 tests still PASS.

- [ ] **Step 3: Implement**

Change `_resp_to_text` (line 605):

```python
def _resp_to_text(data: dict[str, Any], offset: float = 0.0) -> str:
    segs = data.get("segments")
    if segs:
        return "\n".join(
            f"[{_ts(float(s.get('start') or 0.0) + offset)}] {(s.get('text') or '').strip()}"
            for s in segs if (s.get("text") or "").strip())
    return (data.get("text") or "").strip()
```

Rename the existing `_api_transcribe` body to `_api_request` and make it return the parsed JSON. The only changes from the current function: the name, the docstring, and the two `return`/success lines:

```python
def _api_request(backend: str, audio: str) -> dict[str, Any]:
    """POST one audio file to an OpenAI-compatible /audio/transcriptions endpoint via stdlib
    urllib and return the parsed JSON. Retries on 429 / transient network errors with
    exponential backoff."""
    key_env, endpoint, model, verbose = BACKEND_API[backend]
    key = os.environ.get(key_env)
    if not key:
        raise RuntimeError(f"{key_env} not set (needed for backend '{backend}'). "
                           f"PowerShell: $env:{key_env}=\"...\"")
    fields = {"model": model, "temperature": "0",
              "response_format": "verbose_json" if verbose else "json"}
    body, boundary = _build_multipart(fields, audio)
    headers = {"Authorization": f"Bearer {key}",
               "Content-Type": f"multipart/form-data; boundary={boundary}",
               "User-Agent": _WHISPER_UA}
    ctx = ssl.create_default_context()
    rl_hits, last = 0, ""
    for attempt in range(_MAX_ATTEMPTS):
        try:
            req = Request(endpoint, data=body, headers=headers, method="POST")
            with urlopen(req, timeout=300, context=ctx) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as ex:
            last = f"HTTP {ex.code}{_err_body(ex)}"
            if 400 <= ex.code < 500 and ex.code != 429:      # client error — retry won't help
                raise RuntimeError(f"{backend} transcription failed: {last}")
            if ex.code == 429:
                rl_hits += 1
                if rl_hits >= _MAX_429:
                    raise RuntimeError(f"{backend} rate-limited: {last}")
            delay = 2.0 * (2 ** attempt)
        except (urllib.error.URLError, TimeoutError, OSError) as ex:
            last = f"{type(ex).__name__}: {ex}"
            delay = 2.0 * (attempt + 1)
        if attempt < _MAX_ATTEMPTS - 1:
            print(f"[read-video] {backend} {last} — retry in {delay:.1f}s "
                  f"({attempt + 2}/{_MAX_ATTEMPTS})", file=sys.stderr)
            time.sleep(delay)
    raise RuntimeError(f"{backend} transcription failed after {_MAX_ATTEMPTS} attempts: {last}")
```

Then add the new `_api_transcribe` wrapper right after it:

```python
def _api_transcribe(backend: str, audio: str) -> str:
    """Transcribe via a paid API, auto-chunking audio over the upload cap. Ported from
    claude-video v0.2.0: a failed chunk becomes a gap marker instead of killing the run;
    the whole call fails only when every chunk does (so a backend chain still falls
    through). Timestamps are shifted back into source time per chunk."""
    chunks = _split_audio(audio)
    if len(chunks) == 1:
        return _resp_to_text(_api_request(backend, audio))
    parts: list[str] = []
    failures = 0
    for i, (path, offset) in enumerate(chunks, start=1):
        try:
            parts.append(_resp_to_text(_api_request(backend, path), offset))
        except Exception as ex:
            failures += 1
            parts.append(f"[transcription gap: chunk {i} of {len(chunks)} failed: {str(ex)[:120]}]")
            print(f"[read-video] {backend} chunk {i}/{len(chunks)} failed: {ex}", file=sys.stderr)
    if failures == len(chunks):
        raise RuntimeError(f"{backend} transcription failed: all {len(chunks)} chunks failed")
    return "\n".join(parts)
```

- [ ] **Step 4: Run the whole suite**

Run: `python -m pytest -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_chunking.py skill/scripts/video.py
git commit -m "feat: auto-chunked API transcription with per-chunk gap tolerance"
```

---

### Task 9: Estimate note + cost-math regression guard

**Files:**
- Create: `tests/test_estimate.py`
- Modify: `skill/scripts/video.py` — `estimate` return dict (line 243)

**Interfaces:**
- Consumes: `estimate` (unchanged math).
- Produces: `estimate(...)` output gains `"note": "frame dedup may reduce actual frames below this count"` when the tier includes visual. All existing keys and values unchanged — the regression test pins them.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_estimate.py`:

```python
import video


def fake_probe_info():
    return {"source": "local", "input": "x.mp4", "sidecar_transcript": None,
            "captions_available": False, "duration_s": 120.0, "width": 640,
            "height": 360, "fps": 30.0, "has_audio": True}


def patched_estimate(monkeypatch, **kw):
    monkeypatch.setattr(video, "probe", lambda inp: fake_probe_info())
    return video.estimate("x.mp4", pr=video.DEFAULT_PRICING, **kw)


def test_cost_math_regression(monkeypatch):
    """Pins the pre-port numbers: 120s 640x360, tier=both, backend=captions."""
    o = patched_estimate(monkeypatch)
    assert o["frames"] == 60                       # adaptive_frames(120)
    assert o["per_frame_tokens"] == 197            # ceil(512*288/750)
    assert o["tokens"]["frames"] == 60 * 197
    assert o["tokens"]["transcript"] == 400        # 2 min * 200
    assert o["tokens"]["output"] == 798            # 600 words * 1.33
    assert o["cost_usd"]["transcription"] == 0.0
    assert o["free"] is True


def test_estimate_notes_dedup_for_visual_tiers(monkeypatch):
    assert "dedup" in patched_estimate(monkeypatch)["note"]
    assert "dedup" in patched_estimate(monkeypatch, tier="visual")["note"]
    assert "note" not in patched_estimate(monkeypatch, tier="audio")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_estimate.py -v`
Expected: `test_cost_math_regression` PASS; `test_estimate_notes_dedup_for_visual_tiers` FAIL (`KeyError: 'note'`).

- [ ] **Step 3: Implement**

In `estimate`, build the return dict via a variable so the key can be conditional. Replace the final `return { ... }` (line 243) with:

```python
    out = {
        "input": inp, "source": info["source"], "duration_s": dur, "tier": tier,
        "backend": backend if want_audio else "none",
        "frames": n if want_frames else 0, "per_frame_tokens": pft,
        "tokens": {**drivers, "overhead": 2000, "read_total": read_tokens},
        "cost_usd": {"transcription": transcription_usd, "agent": agent_usd, "total": total},
        "dominant_cost": max(drivers, key=drivers.get),
        "free": transcription_usd == 0.0,  # no out-of-pocket $ (agent tokens may still apply)
        "needs_install": needs_install,
        "sidecar_transcript": info.get("sidecar_transcript"),
        "captions_available": info.get("captions_available"),
    }
    if want_frames:
        # The gate prices the full budget (worst case); dedup can only shrink the real count.
        out["note"] = "frame dedup may reduce actual frames below this count"
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_estimate.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_estimate.py skill/scripts/video.py
git commit -m "feat: estimate notes that dedup may shrink the billed frame count"
```

---

### Task 10: Docs, spec touch-up, full suite, live-install sync

**Files:**
- Modify: `skill/SKILL.md` (Notes section + step 4 flag list)
- Modify: `docs/cli-reference.md` (run flags + output fields)
- Modify: `CREDITS.md` (v0.2.0 port line)
- Modify: `docs/superpowers/specs/2026-07-01-upstream-v020-port-design.md` (gemini chunking exemption)
- Copy to live install: `skill/scripts/video.py`, `skill/SKILL.md`

**Interfaces:**
- Consumes: everything above.
- Produces: user-facing docs match the shipped behavior; live skill updated.

- [ ] **Step 1: Update `skill/SKILL.md`**

In the step-4 (Run) section, document the new flags where `--frames`/`--start/--end` are described:

```markdown
Two extra `run` controls: `--timestamps 90,05:30` pins exact-moment frames (reserved against
the budget, never dropped by dedup — the manifest marks them `"pinned": true`), and
`--no-dedup` keeps every sampled frame. By default extraction oversamples ~2x the budget and
drops perceptual near-duplicates (held slides, static screens), so `frames` in the run JSON
may come back smaller than the budget with the difference in `frames_deduped` — that is the
budget being spent on distinct content, not an error.
```

In the Notes section, update the long-audio bullet: replace the sentence
"beyond that, prefer captions or a local backend, or window with `--start/--end` (chunking is not implemented in v1)"
with:

```markdown
beyond that the engine now auto-chunks: the mp3 is split into even segments under the cap,
each transcribed separately (timestamps shifted back into source time); a failed chunk leaves
a `[transcription gap: ...]` marker instead of failing the run.
```

- [ ] **Step 2: Update `docs/cli-reference.md`**

Add to the `run` flags table/list: `--timestamps` (comma-separated `SS`/`MM:SS`/`HH:MM:SS` pins) and `--no-dedup`. Add the new output fields: `frames_deduped` (run) and `note` (estimate). Match the file's existing formatting.

- [ ] **Step 3: Update `CREDITS.md`**

Add under the claude-video entry:

```markdown
- v0.2.0 (2026-06): perceptual frame dedup (16x16 grayscale single-pass thumbnails),
  Whisper API auto-chunking with per-chunk gap tolerance, and `--timestamps` pinned
  frames were ported and adapted to this skill's fast-seek extraction and backend chain.
```

- [ ] **Step 4: Fix the spec's chunking backend list**

In `docs/superpowers/specs/2026-07-01-upstream-v020-port-design.md`, section "2. Whisper API auto-chunking", change:

`Applies to paid API backends only (\`groq\`, \`openai\`, \`openai-mini\`, \`gemini\`); local`

to:

`Applies to the OpenAI-compatible paid backends only (\`groq\`, \`openai\`, \`openai-mini\`, \`openrouter\`); Gemini's Files API has no 25 MB cap so it stays unchunked, and local`

- [ ] **Step 5: Run the full suite one last time**

Run: `python -m pytest -v`
Expected: all PASS (thumbnail/frame/pin/chunk tests skip only if ffmpeg is missing — on this machine it is present, so nothing should skip).

- [ ] **Step 6: Sync the live install**

```bash
cp "skill/scripts/video.py" "/c/Users/a2021/.claude/skills/read-video/scripts/video.py"
cp "skill/SKILL.md" "/c/Users/a2021/.claude/skills/read-video/SKILL.md"
```

(Only these two files — the live install also holds `workspace.json`, `.env`, `load-env.ps1` which must not be touched.)

Verify: `python "/c/Users/a2021/.claude/skills/read-video/scripts/video.py" probe --help`
Expected: usage text, exit 0.

- [ ] **Step 7: Commit**

```bash
git add skill/SKILL.md docs/cli-reference.md CREDITS.md "docs/superpowers/specs/2026-07-01-upstream-v020-port-design.md"
git commit -m "docs: document dedup, chunking, --timestamps; sync spec chunking backends"
```

---

## Self-Review Notes

- **Spec coverage:** dedup → Tasks 3–5; chunking → Tasks 7–8; `--timestamps` → Tasks 1, 6; hardening → Task 2; tests → every task + fixtures in Task 1; estimate note → Task 9; docs/credits → Task 10. Constraints section honored: no new runtime deps, single file, env-var keys untouched, fast-seek preserved (oversample uses the same parallel seek), zero-cost path untouched (dedup/pins are tier-visual features; chunking touches only the paid `_api_transcribe`).
- **Spec deviation (deliberate):** Gemini exempt from chunking — Files API has no 25 MB cap; Task 10 Step 4 amends the spec.
- **Type consistency:** the job tuple is `(t: float, path: Path, pinned: bool)` in `_dedupe_jobs`, `_reindex_jobs`, `_cap_jobs`, `_jobs_to_entries`, and `_extract_frames`. `_extract_frames` returns `tuple[list[dict], int]` and both call sites in `run` unpack it; the `_extract_frames_filter` fallback keeps returning a plain list, wrapped as `(..., 0)` at the call site inside `_extract_frames`.
