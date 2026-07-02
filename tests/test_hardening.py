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
