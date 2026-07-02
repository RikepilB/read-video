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
