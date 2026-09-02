"""3D .cube LUT support for SnapBooth.

- parse_cube_file(text) -> (lut_array, domain_min, domain_max, size)
    lut_array is a numpy array of shape (N, N, N, 3), float32 in [0,1].
    Axis order is (R, G, B) as per Adobe's .cube spec.

- apply_lut_trilinear(image_rgb_u8, lut) -> uint8 image
    Exact trilinear interpolation used for the PRINT render. Matches the
    reference `scipy.interpolate.RegularGridInterpolator` output within
    floating-point rounding.

- lut_to_strip_png(lut) -> bytes
    Produces the 2D "unrolled strip" texture (N*N wide, N tall) that the
    frontend WebGL shader samples for the LIVE PREVIEW. Layout: each of the
    N blue slices occupies an N x N block laid out horizontally, with
    R across the block's X and G down the block's Y. This is the standard
    layout expected by the shader in /app/frontend/src/lib/webglLut.js.
"""
from __future__ import annotations
import io
import re
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image


def parse_cube_file(text: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """Parse an Adobe .cube 3D LUT.

    Returns (lut, domain_min, domain_max, size).
    Raises ValueError on malformed input.
    """
    size = 0
    dmin = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    dmax = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    entries = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        key = parts[0].upper()
        if key == "LUT_3D_SIZE":
            size = int(parts[1])
        elif key == "LUT_1D_SIZE":
            raise ValueError("1D LUTs are not supported — provide a 3D .cube")
        elif key == "DOMAIN_MIN":
            dmin = np.array([float(x) for x in parts[1:4]], dtype=np.float32)
        elif key == "DOMAIN_MAX":
            dmax = np.array([float(x) for x in parts[1:4]], dtype=np.float32)
        elif key == "TITLE":
            continue
        else:
            # data row: r g b
            try:
                r, g, b = (float(parts[0]), float(parts[1]), float(parts[2]))
                entries.append((r, g, b))
            except (ValueError, IndexError):
                # ignore unknown keyword-style lines
                continue

    if size <= 1:
        raise ValueError("missing or invalid LUT_3D_SIZE")
    if len(entries) != size ** 3:
        raise ValueError(f"expected {size**3} entries, got {len(entries)}")

    # .cube storage order: the R axis varies fastest, then G, then B.
    #   for b in 0..N-1: for g in 0..N-1: for r in 0..N-1: emit(r,g,b)
    arr = np.asarray(entries, dtype=np.float32).reshape(size, size, size, 3)
    # arr indexed as [b, g, r, channel] -> reorder to [r, g, b, channel]
    lut = np.transpose(arr, (2, 1, 0, 3)).copy()
    return lut.astype(np.float32), dmin, dmax, size


def _prepare_input(img: np.ndarray, dmin: np.ndarray, dmax: np.ndarray) -> np.ndarray:
    """Normalize u8 RGB image into LUT domain-normalized floats in [0,1]."""
    f = img.astype(np.float32) / 255.0
    span = np.maximum(dmax - dmin, 1e-6)
    f = (f - dmin[None, None, :]) / span[None, None, :]
    return np.clip(f, 0.0, 1.0)


def apply_lut_trilinear(img_rgb_u8: np.ndarray, lut: np.ndarray,
                        dmin: np.ndarray | None = None,
                        dmax: np.ndarray | None = None) -> np.ndarray:
    """Apply a 3D LUT to an RGB uint8 image using trilinear interpolation.

    This is the print-path implementation. Vectorised numpy — a 1200x1800
    image processes in ~150 ms on a mid-range laptop CPU.
    """
    if img_rgb_u8.ndim != 3 or img_rgb_u8.shape[2] != 3:
        raise ValueError("expected HxWx3 RGB image")
    if lut.ndim != 4 or lut.shape[3] != 3 or not (lut.shape[0] == lut.shape[1] == lut.shape[2]):
        raise ValueError("expected LUT of shape (N,N,N,3)")

    N = lut.shape[0]
    if dmin is None: dmin = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    if dmax is None: dmax = np.array([1.0, 1.0, 1.0], dtype=np.float32)

    f = _prepare_input(img_rgb_u8, dmin, dmax) * (N - 1)  # -> [0..N-1]
    # r,g,b coordinate arrays
    r = f[..., 0]; g = f[..., 1]; b = f[..., 2]
    r0 = np.floor(r).astype(np.int32); r1 = np.minimum(r0 + 1, N - 1)
    g0 = np.floor(g).astype(np.int32); g1 = np.minimum(g0 + 1, N - 1)
    b0 = np.floor(b).astype(np.int32); b1 = np.minimum(b0 + 1, N - 1)
    rd = (r - r0)[..., None]; gd = (g - g0)[..., None]; bd = (b - b0)[..., None]

    # 8 corner samples
    c000 = lut[r0, g0, b0]; c100 = lut[r1, g0, b0]
    c010 = lut[r0, g1, b0]; c110 = lut[r1, g1, b0]
    c001 = lut[r0, g0, b1]; c101 = lut[r1, g0, b1]
    c011 = lut[r0, g1, b1]; c111 = lut[r1, g1, b1]

    # Interpolate along R, then G, then B (trilinear)
    c00 = c000 * (1 - rd) + c100 * rd
    c10 = c010 * (1 - rd) + c110 * rd
    c01 = c001 * (1 - rd) + c101 * rd
    c11 = c011 * (1 - rd) + c111 * rd
    c0 = c00 * (1 - gd) + c10 * gd
    c1 = c01 * (1 - gd) + c11 * gd
    out = c0 * (1 - bd) + c1 * bd

    return np.clip(out * 255.0, 0, 255).astype(np.uint8)


def lut_to_strip_png(lut: np.ndarray) -> bytes:
    """Encode a 3D LUT as a 2D "strip" PNG for a fragment shader.

    Layout: N horizontal blocks (one per B slice), each N x N.
      x = b_slice * N + r_index   in [0, N*N)
      y = g_index                 in [0, N)
    """
    N = lut.shape[0]
    strip = np.zeros((N, N * N, 3), dtype=np.uint8)
    # lut is indexed [r, g, b, ch]; we want strip[g, b*N + r, ch]
    for b in range(N):
        block = lut[:, :, b, :]           # (r, g, ch)
        block = np.transpose(block, (1, 0, 2))  # -> (g, r, ch)
        strip[:, b * N:(b + 1) * N, :] = np.clip(block * 255.0, 0, 255).astype(np.uint8)
    img = Image.fromarray(strip, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def identity_cube(size: int = 17) -> str:
    """Generate a valid identity .cube file (for tests + defaults)."""
    lines = [f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for b in range(size):
        for g in range(size):
            for r in range(size):
                fr = r / (size - 1); fg = g / (size - 1); fb = b / (size - 1)
                lines.append(f"{fr:.6f} {fg:.6f} {fb:.6f}")
    return "\n".join(lines)
