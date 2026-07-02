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
