"""Boomerang encoder tests."""
from __future__ import annotations
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from boomerang import encode_ping_pong_gif, encode_ping_pong_mp4, _ping_pong  # noqa: E402


def _make_frames(n: int = 12, w: int = 320, h: int = 240):
    """A rising ramp so ping-pong direction is visible."""
    out = []
    for i in range(n):
        arr = np.zeros((h, w, 3), dtype=np.uint8)
        arr[:, : int((i + 1) * w / n), 0] = 255
        out.append(Image.fromarray(arr))
    return out


def test_ping_pong_drops_endpoints():
    """1-2-3-4 -> 1-2-3-4-3-2  (not 1-2-3-4-4-3-2-1)"""
    seq = _ping_pong([1, 2, 3, 4])
    assert seq == [1, 2, 3, 4, 3, 2]


def test_gif_encodes_ping_pong(tmp_path):
    frames = _make_frames(12)
    p = tmp_path / "b.gif"
    encode_ping_pong_gif(frames, str(p), fps=10)
    assert p.exists() and p.stat().st_size > 0
    im = Image.open(p)
    # 12 forward + 10 reversed (drop endpoints) = 22
    n = 0
    try:
        while True:
            im.seek(n); n += 1
    except EOFError:
        pass
    assert n == 22, f"expected 22 frames, got {n}"
    im.seek(0)
    assert im.width == 320 and im.height == 240


def test_mp4_encodes_ping_pong(tmp_path):
    frames = _make_frames(12)
    p = tmp_path / "b.mp4"
    encode_ping_pong_mp4(frames, str(p), fps=10)
    assert p.exists() and p.stat().st_size > 0
    # Decode back and confirm we get exactly 22 frames at ~10fps
    import imageio.v3 as iio
    arr = iio.imread(p)  # shape (T, H, W, 3)
    assert arr.shape[0] == 22, f"expected 22 frames in mp4, got {arr.shape[0]}"
    assert arr.shape[3] == 3
