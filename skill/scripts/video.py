#!/usr/bin/env python3
"""read-video engine: agent-first CLI for cost-aware video analysis.

Subcommands (the agent drives these in order):
  probe     inspect a local file or URL -> JSON {duration, resolution, audio, captions, sidecar}
  estimate  compute $ + token cost BEFORE any work -> JSON shown to the user at the cost gate
  run       extract frames (+ optional transcript) into a workdir for the agent to Read

Why this shape: Claude's Read tool sees images, not video. So "reading" a video means turning it
into frames (JPGs) + text (a transcript). The expensive part is the agent's own tokens (frames
dominate), so `estimate` exists to price the whole job up front and let the user decide go/skip.

Only ffmpeg / ffprobe / yt-dlp are needed for the FREE paths (captions + visual frames). Paid and
local transcription backends are imported lazily, so the free paths never pay an import cost and a
missing optional dependency never breaks probe/estimate.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import mimetypes
import os
import re
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import uuid
from pathlib import Path
from shutil import which
from typing import Any
from urllib.request import Request, urlopen

SKILL_ROOT = Path(__file__).resolve().parent.parent
PRICING_PATH = SKILL_ROOT / "pricing.json"
WORKSPACE_PATH = SKILL_ROOT / "workspace.json"
SUB_EXTS = (".srt", ".vtt", ".txt")
URL_RE = re.compile(r"^https?://", re.I)
# Matches a VTT/SRT cue timing line; SRT uses ',' for ms, VTT uses '.'.
TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[.,]\d{3}\s*-->")

# backend -> (api_key_env, transcribe_endpoint, model, supports_verbose_json)
# All are OpenAI-compatible /audio/transcriptions endpoints, hit with pure-stdlib urllib
# (no SDK install). verbose_json yields per-segment timestamps; gpt-4o-mini only does plain json.
BACKEND_API = {
    "groq":        ("GROQ_API_KEY",       "https://api.groq.com/openai/v1/audio/transcriptions", "whisper-large-v3",       True),
    "openai":      ("OPENAI_API_KEY",     "https://api.openai.com/v1/audio/transcriptions",      "whisper-1",              True),
    "openai-mini": ("OPENAI_API_KEY",     "https://api.openai.com/v1/audio/transcriptions",      "gpt-4o-mini-transcribe", False),
    "openrouter":  ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1/audio/transcriptions",   "openai/whisper-1",       True),
}
_WHISPER_UA = "read-video-skill/1.0 (+claude-code; python-urllib)"  # Groq's Cloudflare WAF 403s default urllib UA
_MAX_ATTEMPTS = 4
_MAX_429 = 2

# faster-whisper model selection. 'small' is the accuracy/size sweet spot for non-English speech
# (e.g. Spanish meetings); 'tiny'/'base' are much weaker there. If the chosen size can't be obtained
# we fall back to a smaller *cached* one and warn loudly, rather than silently degrading.
_WHISPER_DEFAULT = "small"
_WHISPER_FALLBACKS = ("small", "base", "tiny")

DEFAULT_PRICING: dict[str, Any] = {
    "transcription_per_min": {
        "captions": 0.0, "sidecar": 0.0, "local": 0.0, "trx": 0.0, "faster-whisper": 0.0,
        "groq": 0.0007, "openai-mini": 0.003, "openai": 0.006, "openrouter": 0.006, "gemini": 0.037,
    },
    "model_per_mtok": {"_active": "opus-4.8", "opus-4.8": {"input": 15.0, "output": 75.0}},
    "frame": {"target_width": 512},
}


# --------------------------------------------------------------------------- helpers
def load_pricing() -> dict[str, Any]:
    try:
        return json.loads(PRICING_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_PRICING


def load_workspace() -> dict[str, Any]:
    try:
        return json.loads(WORKSPACE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def resolve_input(inp: str) -> str:
    """Let the user pass a bare filename from the workspace _Inbox instead of a full path.
    URLs and already-existing paths pass through untouched; if a workspace is configured and the
    bare name exists under inbox_dir, expand to that. Keeps the global skill portable (paths live
    in workspace.json, not hardcoded here)."""
    if is_url(inp) or Path(inp).exists():
        return inp
    inbox = load_workspace().get("inbox_dir")
    if inbox:
        cand = Path(inbox) / inp
        if cand.exists():
            return str(cand)
    return inp


def is_url(s: str) -> bool:
    return bool(URL_RE.match(s))


def run_cmd(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def _have(module: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(module) is not None


# --------------------------------------------------------------------------- probe
def ffprobe_local(path: str) -> dict[str, Any]:
    path = str(Path(path).resolve())      # a relative name starting with '-' must not read as a flag
    cp = run_cmd(["ffprobe", "-v", "quiet", "-print_format", "json",
                  "-show_format", "-show_streams", path])
    if cp.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {cp.stderr.strip() or 'unknown error'}")
    data = json.loads(cp.stdout)
    streams = data.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
    astream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = float(data.get("format", {}).get("duration") or vstream.get("duration") or 0.0)
    width = int(vstream.get("width") or 0)
    height = int(vstream.get("height") or 0)
    fps = 0.0
    try:
        num, den = (vstream.get("r_frame_rate") or "0/1").split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        pass
    return {"duration_s": round(dur, 2), "width": width, "height": height,
            "fps": round(fps, 3), "has_audio": astream is not None}


def find_sidecar(path: str) -> str | None:
    """A transcript living next to the video (same stem, .srt/.vtt/.txt) is the cheapest source."""
    p = Path(path)
    for ext in SUB_EXTS:
        cand = p.with_suffix(ext)
        if cand.exists() and cand.resolve() != p.resolve():
            return str(cand)
    return None


def ytdlp_meta(url: str) -> dict[str, Any]:
    cp = run_cmd(["yt-dlp", "--no-warnings", "--skip-download", "-J", url])
    if cp.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata failed: {cp.stderr.strip()[:200]}")
    info = json.loads(cp.stdout)
    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]
    caps = bool(info.get("subtitles") or info.get("automatic_captions"))
    return {"duration_s": round(float(info.get("duration") or 0.0), 2),
            "width": int(info.get("width") or 0), "height": int(info.get("height") or 0),
            "fps": float(info.get("fps") or 0.0), "has_audio": True,
            "captions_available": caps, "title": info.get("title")}


def probe(inp: str) -> dict[str, Any]:
    inp = resolve_input(inp)             # allow a bare filename from the workspace _Inbox
    if is_url(inp):
        return {"source": "url", "input": inp, "sidecar_transcript": None, **ytdlp_meta(inp)}
    if not Path(inp).exists():
        raise FileNotFoundError(f"no such file: {inp}")
    base = ffprobe_local(inp)
    side = find_sidecar(inp)
    return {"source": "local", "input": inp, "sidecar_transcript": side,
            "captions_available": side is not None, **base}


# --------------------------------------------------------------------------- estimate
def adaptive_frames(duration_s: float) -> int:
    """Frame budget that keeps the dominant (vision) cost bounded; mirrors claude-video."""
    if duration_s <= 30:
        n = 30
    elif duration_s <= 180:
        n = 60
    elif duration_s <= 600:
        n = 80
    else:
        n = 100
    hard_cap = max(1, int(duration_s * 2))   # never exceed 2 fps
    return max(1, min(n, 100, hard_cap))


def per_frame_tokens(width: int, height: int, target_w: int) -> int:
    """Claude vision tokens ~= (w*h)/750. Frames are downscaled to target_w before reading."""
    if width and height:
        h = round(target_w * height / width)
    else:
        h = round(target_w * 9 / 16)         # assume 16:9 when resolution is unknown
    h += h % 2                                # ffmpeg scale=-2 keeps height even
    return math.ceil(target_w * h / 750)


def _have_local_backend(backend: str) -> bool:
    if backend == "trx":
        return which("trx") is not None
    if backend in ("faster-whisper", "local"):
        return _have("faster_whisper")
    return True


def estimate(inp: str, frames: int | None = None, backend: str = "captions",
             out_words: int = 600, tier: str = "both",
             pr: dict[str, Any] | None = None) -> dict[str, Any]:
    pr = pr or load_pricing()
    info = probe(inp)
    dur = info["duration_s"] or 0.0
    dur_min = dur / 60.0
    want_frames = tier in ("visual", "both")
    want_audio = tier in ("audio", "both")
    primary = backend.split(",")[0].strip() if backend else backend   # a chain is priced by its first hop

    n = frames if frames else adaptive_frames(dur)
    target_w = int(pr.get("frame", {}).get("target_width", 512))
    pft = per_frame_tokens(info.get("width", 0), info.get("height", 0), target_w)

    frames_tokens = n * pft if want_frames else 0
    transcript_tokens = round(dur_min * 200) if want_audio else 0   # ~150 wpm * 1.33 tok/word
    output_tokens = round(out_words * 1.33)

    rate = pr["transcription_per_min"].get(primary, 0.0) if want_audio else 0.0
    transcription_usd = round(dur_min * rate, 4)

    mrates = pr["model_per_mtok"]
    active = mrates.get("_active")
    m = mrates.get(active) or next((v for k, v in mrates.items() if k != "_active"),
                                   {"input": 15.0, "output": 75.0})
    read_tokens = frames_tokens + transcript_tokens + 2000          # +overhead for the prompt
    agent_usd = round(read_tokens / 1e6 * m["input"] + output_tokens / 1e6 * m["output"], 4)
    total = round(transcription_usd + agent_usd, 4)

    drivers = {"frames": frames_tokens, "transcript": transcript_tokens, "output": output_tokens}
    needs_install = want_audio and primary in ("trx", "faster-whisper", "local") \
        and not _have_local_backend(primary) and not info.get("sidecar_transcript")
    return {
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


# --------------------------------------------------------------------------- run
def run(inp: str, tier: str = "both", frames: int | None = None, backend: str = "captions",
        start: float = 0.0, end: float | None = None,
        workdir: str | None = None, pr: dict[str, Any] | None = None) -> dict[str, Any]:
    pr = pr or load_pricing()
    info = probe(inp)
    dur = info["duration_s"] or 0.0
    end = end if end is not None else dur
    window = max(0.1, end - start)
    n = frames if frames else adaptive_frames(window)

    wd = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="readvideo_"))
    wd.mkdir(parents=True, exist_ok=True)

    want_frames = tier in ("visual", "both")
    want_audio = tier in ("audio", "both")

    # Acquire the media file only when we actually need pixels or non-caption audio.
    media: str | None = None
    need_media = want_frames or (want_audio and backend != "captions"
                                 and not info.get("sidecar_transcript"))
    if need_media:
        media = _download(inp, wd) if info["source"] == "url" else str(Path(inp).resolve())

    result: dict[str, Any] = {"workdir": str(wd), "tier": tier,
                              "backend": backend if want_audio else "none",
                              "frames": [], "transcript": None}
    if want_frames:
        result["frames"] = _extract_frames(media, wd, n, start, window,
                                           int(pr.get("frame", {}).get("target_width", 512)))
    if want_audio:
        tpath, text = _transcribe(inp, info, media, wd, backend)
        result["transcript"] = tpath
        result["transcript_chars"] = len(text)
    (wd / "manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _download(url: str, wd: Path) -> str:
    out = str(wd / "source.%(ext)s")
    cp = run_cmd(["yt-dlp", "-f", "bv*[height<=720]+ba/b[height<=720]/b",
                  "--concurrent-fragments", "8", "-o", out, "--no-warnings", url])
    if cp.returncode != 0:
        raise RuntimeError(f"yt-dlp download failed: {cp.stderr.strip()[:200]}")
    files = sorted(wd.glob("source.*"))
    if not files:
        raise RuntimeError("download produced no file")
    return str(files[0])


def _extract_frames(media: str | None, wd: Path, n: int, start: float,
                    window: float, target_w: int) -> list[dict[str, str]]:
    """Sample n evenly-spaced frames, scaling to target_w in the same pass.

    Each frame is grabbed with a *fast input seek* (`-ss` before `-i`, one frame out) instead of a
    single `fps=` filter pass. The filter approach must decode the entire stream to drop all but n
    frames — on a long, high-fps source (e.g. 9 min @ 60 fps that's ~33k decoded frames) that is the
    dominant cost. Fast seeks jump near each target keyframe and decode ~1 frame, so cost scales with
    n, not duration. Seeks are independent, so a small thread pool overlaps the ffmpeg subprocesses.
    Keyframe-accurate (not exact) seeking is fine here: we want the gist of each moment, not a precise
    cut. Falls back to the whole-stream filter pass if seeking yields nothing (odd container/codec)."""
    if not media:
        raise RuntimeError("frame extraction needs a media file")
    fdir = wd / "frames"
    fdir.mkdir(exist_ok=True)
    interval = window / n
    jobs = [(k, start + (k - 0.5) * interval, fdir / f"frame_{k:04d}.jpg")
            for k in range(1, n + 1)]            # midpoint of each frame's window

    def grab(job: tuple[int, float, Path]) -> tuple[tuple[int, float, Path], bool]:
        _, t, fp = job
        cp = run_cmd(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                      "-ss", f"{t:.3f}", "-i", media, "-frames:v", "1", "-an",
                      "-vf", f"scale={target_w}:-2", "-q:v", "3", str(fp)])
        return job, cp.returncode == 0 and fp.exists()

    from concurrent.futures import ThreadPoolExecutor
    workers = max(2, min(8, (os.cpu_count() or 4)))
    ok: list[tuple[int, float, Path]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for job, success in ex.map(grab, jobs):
            if success:
                ok.append(job)

    if not ok:                                    # seeking produced nothing — robust single-pass path
        return _extract_frames_filter(media, fdir, n, start, window, target_w)

    return [{"file": str(fp), "t": f"{int(t // 60):02d}:{int(t % 60):02d}"}
            for _, t, fp in sorted(ok)]


def _extract_frames_filter(media: str, fdir: Path, n: int, start: float,
                           window: float, target_w: int) -> list[dict[str, str]]:
    """Whole-stream `fps=` fallback: slower (decodes everything) but handles containers that don't
    seek cleanly. Only used when per-frame seeking grabbed zero frames."""
    fps = n / window if window > 0 else 1.0
    cp = run_cmd(["ffmpeg", "-hide_banner", "-loglevel", "error",
                  "-ss", str(start), "-t", str(window), "-i", media,
                  "-vf", f"fps={fps:.6f},scale={target_w}:-2", "-q:v", "3",
                  str(fdir / "frame_%04d.jpg")])
    if cp.returncode != 0:
        raise RuntimeError(f"ffmpeg frame extraction failed: {cp.stderr.strip()[:200]}")
    interval = window / n
    out = []
    for k, fp in enumerate(sorted(fdir.glob("frame_*.jpg")), start=1):
        t = start + (k - 0.5) * interval
        out.append({"file": str(fp), "t": f"{int(t // 60):02d}:{int(t % 60):02d}"})
    return out


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


# --------------------------------------------------------------------------- transcription
def _transcribe(orig: str, info: dict[str, Any], media: str | None,
                wd: Path, backend: str) -> tuple[str, str]:
    # A sidecar transcript is free and beats any backend, so it short-circuits the whole chain.
    if info.get("sidecar_transcript"):
        return _save_transcript(wd, _read_sidecar(info["sidecar_transcript"]))
    # `backend` may be a comma-separated chain ("openrouter,groq"): try each in order and fall through
    # on any failure — out of credits, rate limit, missing key, not installed. Lets you spend a
    # limited/cheaper key first and fall back to another without re-running. A single backend is just a
    # one-element chain. (Audio is extracted once and reused across hops, so a fallback is cheap.)
    chain = [b.strip() for b in backend.split(",") if b.strip()] or [backend]
    if len(chain) == 1:
        return _transcribe_one(orig, info, media, wd, chain[0])
    errors: list[str] = []
    for b in chain:
        try:
            return _transcribe_one(orig, info, media, wd, b)
        except Exception as ex:
            errors.append(f"{b}: {type(ex).__name__}: {str(ex)[:140]}")
            print(f"[read-video] backend '{b}' failed -> falling back to next in chain. {errors[-1]}",
                  file=sys.stderr)
    raise RuntimeError("all transcription backends in the chain failed: " + " | ".join(errors))


def _transcribe_one(orig: str, info: dict[str, Any], media: str | None,
                    wd: Path, backend: str) -> tuple[str, str]:
    if backend == "captions" and info["source"] == "url":
        text = _fetch_captions(orig, wd)
        if text:
            return _save_transcript(wd, text)
        raise RuntimeError("no captions found for this URL; pick a local backend "
                           "(faster-whisper / trx) or an API backend, then re-run")
    # Engines that need real audio.
    if backend == "trx" and which("trx"):
        return _save_transcript(wd, _trx(media or orig))
    if backend in ("faster-whisper", "local") and _have("faster_whisper"):
        # faster-whisper decodes audio itself (PyAV/ffmpeg), so hand it the media directly instead of
        # paying for a separate lossy mp3 pass — that pass exists only to fit the API upload cap.
        return _save_transcript(wd, _faster_whisper(media or orig))
    if backend in BACKEND_API:
        return _save_transcript(wd, _api_transcribe(backend, _to_audio(media or orig, wd)))
    if backend == "gemini":
        return _save_transcript(wd, _gemini(_to_audio(media or orig, wd)))
    raise RuntimeError(
        f"no usable transcription backend for '{backend}'. Options: add a sidecar .srt/.vtt, "
        f"use captions (URL), `pip install faster-whisper`, install trx, or set an API key. "
        f"See references/backends.md")


def _save_transcript(wd: Path, text: str) -> tuple[str, str]:
    p = wd / "transcript.txt"
    p.write_text(text or "", encoding="utf-8")
    return str(p), text or ""


def _read_sidecar(path: str) -> str:
    raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    return raw if path.lower().endswith(".txt") else _cues_to_text(raw)


def _fetch_captions(url: str, wd: Path) -> str | None:
    out = str(wd / "caps")
    run_cmd(["yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs",
             "--sub-format", "vtt", "--sub-langs", "en.*,en",
             "-o", out, "--no-warnings", url])
    vtts = sorted(wd.glob("caps*.vtt"))
    if not vtts:
        return None
    return _cues_to_text(vtts[0].read_text(encoding="utf-8", errors="ignore"))


def _cues_to_text(raw: str) -> str:
    """Flatten VTT/SRT cues to '[MM:SS] line', stripping tags and rolling-caption duplicates."""
    lines: list[tuple[str, str]] = []
    cur_ts: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, cur_ts
        if cur_ts and buf:
            txt = re.sub(r"<[^>]+>", "", " ".join(buf)).strip()
            if txt:
                lines.append((cur_ts, txt))
        buf = []

    for ln in raw.splitlines():
        s = ln.strip()
        m = TS_RE.match(s)
        if m:
            flush()
            hh, mm, ss = int(m[1]), int(m[2]), int(m[3])
            cur_ts = f"{hh * 60 + mm:02d}:{ss:02d}"
        elif s and s != "WEBVTT" and not s.isdigit():
            buf.append(s)
    flush()

    out, prev = [], None
    for ts, txt in lines:
        if txt == prev:                          # exact rolling duplicate
            continue
        if prev is not None and txt.startswith(prev + " "):
            out[-1] = f"[{ts}] {txt}"            # caption scrolled & grew — keep the fuller line
            prev = txt
            continue
        out.append(f"[{ts}] {txt}")
        prev = txt
    return "\n".join(out)


def _to_audio(src: str, wd: Path) -> str:
    """Mono 16kHz 64kbps mp3 — ~0.5 MB/min, so ~50 min fits the providers' ~25 MB upload cap.
    (wav would be ~1.9 MB/min and blow the cap after ~13 min.)"""
    src = str(Path(src).resolve())
    out = str(wd / "audio.mp3")
    if Path(out).exists() and Path(out).stat().st_size > 0:
        return out                                    # reuse within a run (e.g. across a backend chain)
    cp = run_cmd(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src,
                  "-vn", "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1", "-b:a", "64k", out])
    if cp.returncode != 0:
        raise RuntimeError(f"audio extract failed: {cp.stderr.strip()[:200]}")
    return out


def _ts(seconds: float) -> str:
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


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


def _whisper_settings() -> tuple[str, str | None]:
    """Resolve the faster-whisper model + optional download dir from env, then workspace.json.
    Env wins so a machine can override without editing config: READ_VIDEO_WHISPER_MODEL (a size
    name like 'small'/'medium' or a full path to a pre-downloaded model dir) and
    READ_VIDEO_WHISPER_DIR (HuggingFace cache/download_root). Keeps the global skill portable."""
    ws = load_workspace()
    model = os.environ.get("READ_VIDEO_WHISPER_MODEL") or ws.get("whisper_model") or _WHISPER_DEFAULT
    root = os.environ.get("READ_VIDEO_WHISPER_DIR") or ws.get("whisper_model_dir")
    return model, root


def _new_whisper(size: str, download_root: str | None, offline: bool):
    from faster_whisper import WhisperModel
    # offline (local_files_only) skips the HuggingFace revision HEAD, which fails on locked-down
    # networks (WinError 10054) even when the model is fully cached on disk.
    return WhisperModel(size, device="cpu", compute_type="int8",
                        download_root=download_root, local_files_only=offline)


def _faster_whisper(audio: str, model_size: str | None = None,
                    download_root: str | None = None) -> str:
    cfg_model, cfg_root = _whisper_settings()
    requested = model_size or cfg_model
    download_root = download_root or cfg_root
    is_path = Path(requested).exists()                    # a pre-downloaded model dir is used verbatim
    candidates = [requested] if is_path else [requested] + [m for m in _WHISPER_FALLBACKS if m != requested]

    model = used = None
    errors: list[str] = []
    for i, size in enumerate(candidates):
        try:                                              # offline-first: load from cache, no network
            model, used = _new_whisper(size, download_root, True), size
            break
        except Exception as ex:
            errors.append(f"{size} offline: {type(ex).__name__}: {str(ex)[:90]}")
        if i == 0 and not is_path:                        # only download the *requested* size, not fallbacks
            for attempt in range(3):
                try:
                    model, used = _new_whisper(size, download_root, False), size
                    break
                except Exception as ex:
                    errors.append(f"{size} online#{attempt + 1}: {type(ex).__name__}: {str(ex)[:90]}")
                    if attempt < 2:
                        time.sleep(2.0 * (attempt + 1))
            if model is not None:
                break

    if model is None:
        raise RuntimeError(
            "faster-whisper could not obtain a usable model (tried "
            f"{', '.join(candidates)}); the network appears to block model downloads. "
            "Cache one on a connected machine: "
            "python -c \"from faster_whisper import WhisperModel as W; W('small')\"  then set "
            "\"whisper_model\":\"small\" (or a model-dir path in \"whisper_model_dir\") in "
            "workspace.json, or use an API backend such as groq. "
            f"Last errors: {' | '.join(errors[-3:])}")

    if used != requested:
        print(f"[read-video] WARNING: whisper model '{requested}' unavailable -> fell back to "
              f"'{used}' (lower accuracy, esp. non-English). Install '{requested}' to fix.",
              file=sys.stderr)
    else:
        print(f"[read-video] faster-whisper model: {used}", file=sys.stderr)

    # vad_filter skips non-speech via Silero VAD: on sparse/silent audio (e.g. a screen recording with
    # only background music) it transcribes seconds instead of minutes AND avoids Whisper hallucinating
    # text over silence. The bundled VAD adds no extra dependency.
    try:
        segments, _ = model.transcribe(audio, vad_filter=True)
        return "\n".join(f"[{_ts(s.start)}] {s.text.strip()}" for s in segments)
    except (TypeError, ValueError):                # older faster-whisper without VAD support
        segments, _ = model.transcribe(audio)
        return "\n".join(f"[{_ts(s.start)}] {s.text.strip()}" for s in segments)


def _trx(src: str) -> str:
    cp = run_cmd(["trx", "transcribe", src, "--output", "json"])
    if cp.returncode != 0:
        raise RuntimeError(f"trx failed: {cp.stderr.strip()[:200]}")
    data = json.loads(cp.stdout)
    if isinstance(data, dict) and data.get("segments"):
        return "\n".join(f"[{_ts(float(s['start']))}] {s['text'].strip()}" for s in data["segments"])
    return data.get("text", "") if isinstance(data, dict) else str(data)


def _build_multipart(fields: dict[str, str], path: str) -> tuple[bytes, str]:
    """Assemble a multipart/form-data body by hand so the API path stays pure-stdlib (no SDK)."""
    boundary = f"----ReadVideoBoundary{uuid.uuid4().hex}"
    eol = b"\r\n"
    buf = io.BytesIO()
    for name, value in fields.items():
        buf.write(f"--{boundary}".encode()); buf.write(eol)
        buf.write(f'Content-Disposition: form-data; name="{name}"'.encode()); buf.write(eol); buf.write(eol)
        buf.write(str(value).encode()); buf.write(eol)
    fp = Path(path)
    mime = mimetypes.guess_type(fp.name)[0] or "application/octet-stream"
    buf.write(f"--{boundary}".encode()); buf.write(eol)
    buf.write(f'Content-Disposition: form-data; name="file"; filename="{fp.name}"'.encode()); buf.write(eol)
    buf.write(f"Content-Type: {mime}".encode()); buf.write(eol); buf.write(eol)
    buf.write(fp.read_bytes()); buf.write(eol)
    buf.write(f"--{boundary}--".encode()); buf.write(eol)
    return buf.getvalue(), boundary


def _err_body(ex: urllib.error.HTTPError) -> str:
    try:
        b = ex.read()
        return f" — {b.decode('utf-8', errors='replace')[:300]}" if b else ""
    except Exception:
        return ""


def _resp_to_text(data: dict[str, Any]) -> str:
    segs = data.get("segments")
    if segs:
        return "\n".join(f"[{_ts(float(s.get('start') or 0.0))}] {(s.get('text') or '').strip()}"
                         for s in segs if (s.get("text") or "").strip())
    return (data.get("text") or "").strip()


def _api_transcribe(backend: str, audio: str) -> str:
    """POST the audio to an OpenAI-compatible /audio/transcriptions endpoint via stdlib urllib.
    Retries on 429 / transient network errors with exponential backoff."""
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
                return _resp_to_text(json.loads(resp.read().decode("utf-8", errors="replace")))
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


def _gemini(wav: str) -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set (needed for backend 'gemini')")
    try:
        from google import genai
    except ImportError:
        raise RuntimeError("pip install google-genai (needed for backend 'gemini')")
    client = genai.Client(api_key=key)
    up = client.files.upload(file=wav)
    r = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=["Transcribe this audio verbatim. Prefix each line with an [MM:SS] timestamp.", up])
    return r.text or ""


# --------------------------------------------------------------------------- cli
def _fmt_estimate(o: dict[str, Any]) -> str:
    c, t = o["cost_usd"], o["tokens"]
    out = [
        f"input: {o['input']}  ({o['source']}, {o['duration_s']}s)",
        f"tier={o['tier']}  backend={o['backend']}  frames={o['frames']}",
        f"  frames tokens:     {t['frames']:>8}",
        f"  transcript tokens: {t['transcript']:>8}",
        f"  output tokens:     {t['output']:>8}",
        "  ---",
        f"  transcription: ${c['transcription']:.4f}",
        f"  agent tokens:  ${c['agent']:.4f}",
        f"  TOTAL:         ${c['total']:.4f}   (dominant: {o['dominant_cost']})",
    ]
    if o.get("needs_install"):
        out.append("  NOTE: chosen backend needs a one-time install before it can run")
    return "\n".join(out)


def _emit(obj: dict[str, Any], human: bool) -> None:
    if human and "cost_usd" in obj:
        print(_fmt_estimate(obj))
    else:
        print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="video.py", description="cost-aware video analysis engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="inspect input -> JSON")
    p.add_argument("input")

    e = sub.add_parser("estimate", help="price the job before running")
    e.add_argument("input")
    e.add_argument("--frames", type=int)
    e.add_argument("--backend", default="captions")
    e.add_argument("--out-words", type=int, default=600)
    e.add_argument("--tier", default="both", choices=["visual", "audio", "both"])

    r = sub.add_parser("run", help="extract frames (+transcript) into a workdir")
    r.add_argument("input")
    r.add_argument("--tier", default="both", choices=["visual", "audio", "both"])
    r.add_argument("--frames", type=int)
    r.add_argument("--backend", default="captions")
    r.add_argument("--start", type=float, default=0.0)
    r.add_argument("--end", type=float)
    r.add_argument("--workdir")

    for sp in (p, e, r):
        sp.add_argument("--human", action="store_true", help="readable output instead of JSON")

    a = ap.parse_args(argv)
    try:
        if a.cmd == "probe":
            _emit(probe(a.input), a.human)
        elif a.cmd == "estimate":
            _emit(estimate(a.input, a.frames, a.backend, a.out_words, a.tier), a.human)
        elif a.cmd == "run":
            _emit(run(a.input, a.tier, a.frames, a.backend, a.start, a.end, a.workdir), a.human)
    except Exception as ex:                       # surface as JSON so the agent can react
        print(json.dumps({"error": str(ex)}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
