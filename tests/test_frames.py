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
