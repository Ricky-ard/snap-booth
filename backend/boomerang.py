"""Boomerang / ping-pong GIF + MP4 encoder.

Input: an ordered list of RGB frames (uint8 numpy arrays or PIL Images).
Output: two files

    - a ping-pong .gif  (forward + reversed, with head/tail dedup)
    - a ping-pong .mp4  (H.264, safe for iOS/Android inline playback)

Both are looped by the players themselves (GIF via loop=0, MP4 via the
`<video loop>` attribute in the guest gallery), so we only need to write
the ping-pong sequence once — no need to repeat it in the file.

The MP4 encoder streams through ffmpeg (bundled via imageio-ffmpeg), so no
system ffmpeg install is required on the event laptop.
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Sequence

import numpy as np
from PIL import Image


def _ping_pong(frames: Sequence, drop_endpoints: bool = True) -> list:
    """Return frames + reverse-of-frames.

    drop_endpoints=True removes the duplicated first/last frames so the loop
    doesn't stutter at the reversal points (e.g. 1-2-3 + 2-1 not 1-2-3 + 3-2-1).
    """
    frames = list(frames)
    if len(frames) <= 1: return frames
    if drop_endpoints:
        return frames + list(reversed(frames[1:-1]))
    return frames + list(reversed(frames))


def _to_pil(frames) -> List[Image.Image]:
    out = []
    for f in frames:
        if isinstance(f, Image.Image):
            out.append(f.convert("RGB"))
        else:
            arr = np.asarray(f)
            if arr.ndim == 3 and arr.shape[2] == 4:
                arr = arr[..., :3]
            out.append(Image.fromarray(arr, "RGB"))
    return out


def encode_ping_pong_gif(frames, out_path: str, fps: int = 10,
                        max_width: int = 640) -> str:
    """Encode a ping-pong GIF at `fps` frames per second.

    Frames are downscaled to ``max_width`` (preserving aspect) to keep the
    file small enough for phone downloads. Palette is optimised per frame.
    """
    pil = _to_pil(frames)
    # Scale
    if pil and pil[0].width > max_width:
        ratio = max_width / pil[0].width
        new_size = (max_width, int(pil[0].height * ratio))
        pil = [f.resize(new_size, Image.LANCZOS) for f in pil]

    seq = _ping_pong(pil)
    duration = int(1000 / max(1, fps))  # ms per frame
    seq[0].save(
        out_path, save_all=True, append_images=seq[1:],
        duration=duration, loop=0, optimize=True, disposal=2,
    )
    return out_path


def encode_ping_pong_mp4(frames, out_path: str, fps: int = 10,
                        max_width: int = 720) -> str:
    """Encode a ping-pong H.264 MP4 via imageio-ffmpeg (bundled binary)."""
    import imageio.v3 as iio
    pil = _to_pil(frames)
    if pil and pil[0].width > max_width:
        ratio = max_width / pil[0].width
        new_size = ((max_width // 2) * 2, (int(pil[0].height * ratio) // 2) * 2)
        pil = [f.resize(new_size, Image.LANCZOS) for f in pil]
    else:
        # H.264 needs even dimensions
        w, h = pil[0].size
        pil = [f.resize(((w // 2) * 2, (h // 2) * 2), Image.LANCZOS) for f in pil]

    seq = _ping_pong(pil)
    arr = np.stack([np.asarray(f) for f in seq], axis=0)
    iio.imwrite(
        out_path, arr, fps=fps, codec="libx264",
        macro_block_size=1,  # accept our exact frame dims
        pixelformat="yuv420p",
        ffmpeg_params=["-movflags", "+faststart", "-preset", "veryfast", "-crf", "23"],
    )
    return out_path
