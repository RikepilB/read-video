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
