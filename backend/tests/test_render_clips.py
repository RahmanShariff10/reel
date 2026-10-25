"""Tests for slice-20-render-clips.

Acceptance criteria:
- Output duration within ±0.1 s of the planned duration.
- The first full-brightness frame (after the fade-in) matches the source frame at the
  planned start (SSIM >= 0.9).
- OCR on the caption region reads the planned text.
- A 1080p source gives 1280x720 H.264 yuv420p with AAC audio.
- The first and last frames are darker than the middle frame (fades).
- A source without audio still gives a (silent) audio track.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest
from rapidocr_onnxruntime import RapidOCR

from reel.common.config import RenderConfig
from reel.common.models import ReelClip
from reel.ingest.probe import find_binary
from reel.render.clips import render_clip
from tests.conftest import SyntheticMatch, make_synthetic_match

CFG = RenderConfig()
CLIP = ReelClip(
    event_id="ev-001",
    start_s=14.0,
    end_s=26.0,
    duration_s=12.0,
    caption="SIX · 16.2 ov · IND 151/3",
)


def probe(path: Path) -> dict:
    out = subprocess.run(
        [
            find_binary("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,pix_fmt",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def frame(path: Path, t: float, seek_end: bool = False) -> np.ndarray:
    args = ["-sseof", "-0.05"] if seek_end else ["-ss", f"{t:.3f}"]
    out = subprocess.run(
        [
            find_binary("ffmpeg"),
            "-v",
            "error",
            *args,
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ],
        capture_output=True,
        check=True,
    )
    return cv2.imdecode(np.frombuffer(out.stdout, np.uint8), cv2.IMREAD_COLOR)


def ssim(a: np.ndarray, b: np.ndarray) -> float:
    a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float64)
    b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float64)
    blur = lambda x: cv2.GaussianBlur(x, (11, 11), 1.5)  # noqa: E731
    mu_a, mu_b = blur(a), blur(b)
    var_a, var_b = blur(a * a) - mu_a**2, blur(b * b) - mu_b**2
    cov = blur(a * b) - mu_a * mu_b
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    num = (2 * mu_a * mu_b + c1) * (2 * cov + c2)
    den = (mu_a**2 + mu_b**2 + c1) * (var_a + var_b + c2)
    return float((num / den).mean())


@pytest.fixture(scope="module")
def rendered(synthetic_match: SyntheticMatch, tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("clips") / "ev-001.mp4"
    return render_clip(synthetic_match.video, CLIP, out, CFG, fps=25.0, has_audio=True)


class TestClip:
    def test_duration(self, rendered: Path) -> None:
        assert abs(float(probe(rendered)["format"]["duration"]) - CLIP.duration_s) <= 0.1

    def test_first_full_frame_matches_source(self, rendered: Path, synthetic_match) -> None:
        t = 0.4  # just after the 0.3 s fade-in
        ours = frame(rendered, t)
        src = frame(synthetic_match.video, CLIP.start_s + t)
        top = slice(0, int(ours.shape[0] * 0.75))  # exclude the caption bar
        assert ssim(ours[top], src[top]) >= 0.9

    def test_caption_readable(self, rendered: Path) -> None:
        img = frame(rendered, 5.0)
        h = img.shape[0]
        result, _ = RapidOCR()(img[int(h * 0.75) :, : img.shape[1] // 2])
        text = " ".join(r[1] for r in result or [])
        norm = lambda s: re.sub(r"[^A-Z0-9]", "", s.upper())  # noqa: E731
        assert norm(text) == norm(CLIP.caption)

    def test_fades(self, rendered: Path) -> None:
        first, last = frame(rendered, 0.0), frame(rendered, 0, seek_end=True)
        middle = frame(rendered, CLIP.duration_s / 2)
        assert first.mean() < middle.mean() * 0.7
        assert last.mean() < middle.mean() * 0.7


class TestFormats:
    def test_1080p_scaled_to_720p(self, tmp_path: Path) -> None:
        m = make_synthetic_match(tmp_path / "hd", duration_s=12.0, width=1920, height=1080)
        clip = CLIP.model_copy(update={"start_s": 2.0, "end_s": 8.0, "duration_s": 6.0})
        out = render_clip(m.video, clip, tmp_path / "hd.mp4", CFG, fps=25.0, has_audio=True)
        streams = {s["codec_type"]: s for s in probe(out)["streams"]}
        v, a = streams["video"], streams["audio"]
        assert (v["width"], v["height"], v["codec_name"], v["pix_fmt"]) == (
            1280,
            720,
            "h264",
            "yuv420p",
        )
        assert a["codec_name"] == "aac"

    def test_silent_track_without_audio(self, tmp_path: Path) -> None:
        m = make_synthetic_match(tmp_path / "na", duration_s=10.0, has_audio=False)
        clip = CLIP.model_copy(update={"start_s": 1.0, "end_s": 6.0, "duration_s": 5.0})
        out = render_clip(m.video, clip, tmp_path / "na.mp4", CFG, fps=25.0, has_audio=False)
        types = [s["codec_type"] for s in probe(out)["streams"]]
        assert "audio" in types
        assert abs(float(probe(out)["format"]["duration"]) - 5.0) <= 0.1


class TestCaptionPlacement:
    def test_raised_above_score_box(self) -> None:
        from reel.render.clips import caption_bottom

        margin = caption_bottom(CFG, (1280, 720), None)
        assert margin == round(720 * 0.06)
        # synthetic score box (bottom-left) → caption moves above it
        raised = caption_bottom(CFG, (1280, 720), [56, 626, 392, 64])
        assert raised >= 720 - 626
        # a score box at the top right doesn't move the caption
        assert caption_bottom(CFG, (1280, 720), [1000, 20, 250, 50]) == margin
        # 1080p source boxes are scaled to the 720p output
        assert caption_bottom(CFG, (1920, 1080), [84, 939, 588, 96]) >= 720 - 626
