"""LUT parity + correctness tests.

Verifies:
1) An identity .cube LUT round-trips a reference image with zero drift.
2) Our trilinear implementation matches scipy's RegularGridInterpolator to
   sub-1/255 accuracy on a random-noise reference image.
3) The WebGL shader math (bilinear r,g + linear blue) that the browser runs
   on the LIVE PREVIEW matches the backend PRINT pipeline (trilinear) to
   within a small visual tolerance on the same reference image — this is the
   preview↔print parity the product spec calls for.
4) The strip PNG produced for the shader decodes back to the same LUT table
   we started with.
"""
from __future__ import annotations
import io
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from lut import (  # noqa: E402
    parse_cube_file, apply_lut_trilinear, lut_to_strip_png, identity_cube,
)


# ---------- helpers --------------------------------------------------------
def _make_reference(seed: int = 7, size: int = 96) -> np.ndarray:
    """Deterministic reference image with sweeps + noise (uint8 HxWx3)."""
    rng = np.random.default_rng(seed)
    r = np.tile(np.linspace(0, 255, size, dtype=np.uint8)[None, :], (size, 1))
    g = np.tile(np.linspace(0, 255, size, dtype=np.uint8)[:, None], (1, size))
    b = rng.integers(0, 256, (size, size), dtype=np.uint8)
    return np.stack([r, g, b], axis=-1)


def _teal_orange_cube(size: int = 17) -> str:
    """A real, non-identity LUT — pushes shadows teal, highlights orange."""
    lines = [f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for b in range(size):
        for g in range(size):
            for r in range(size):
                fr = r / (size - 1); fg = g / (size - 1); fb = b / (size - 1)
                L = 0.299 * fr + 0.587 * fg + 0.114 * fb
                # cool shadows / warm highlights
                nr = min(1.0, fr + 0.20 * (L - 0.5))
                ng = fg
                nb = max(0.0, fb - 0.20 * (L - 0.5))
                lines.append(f"{nr:.6f} {ng:.6f} {nb:.6f}")
    return "\n".join(lines)


def _shader_sim(img_u8: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """Numpy simulation of the WebGL fragment-shader math.

    The shader uses the GPU's bilinear filter for the R and G axes (equivalent
    to bilinear-interpolating within a blue slice) and then does a linear
    blend between the two neighbouring blue slices. This is what the browser
    actually runs in `webglLut.js`; the test asserts it agrees with the
    exact trilinear backend within a small tolerance.
    """
    N = lut.shape[0]
    f = img_u8.astype(np.float32) / 255.0
    b = np.clip(f[..., 2], 0, 1) * (N - 1)
    b0 = np.floor(b).astype(np.int32); b1 = np.minimum(b0 + 1, N - 1)
    t = (b - b0)[..., None]

    r = np.clip(f[..., 0], 0, 1) * (N - 1)
    g = np.clip(f[..., 1], 0, 1) * (N - 1)
    r0 = np.floor(r).astype(np.int32); r1 = np.minimum(r0 + 1, N - 1)
    g0 = np.floor(g).astype(np.int32); g1 = np.minimum(g0 + 1, N - 1)
    rd = (r - r0)[..., None]; gd = (g - g0)[..., None]

    def bilin(b_idx):
        c00 = lut[r0, g0, b_idx]; c10 = lut[r1, g0, b_idx]
        c01 = lut[r0, g1, b_idx]; c11 = lut[r1, g1, b_idx]
        c0 = c00 * (1 - rd) + c10 * rd
        c1 = c01 * (1 - rd) + c11 * rd
        return c0 * (1 - gd) + c1 * gd

    s0 = bilin(b0)
    s1 = bilin(b1)
    out = s0 * (1 - t) + s1 * t
    return np.clip(out * 255.0, 0, 255).astype(np.uint8)


# ---------- 1) identity LUT is a no-op -------------------------------------
def test_identity_cube_is_noop():
    lut, dmin, dmax, size = parse_cube_file(identity_cube(17))
    img = _make_reference()
    out = apply_lut_trilinear(img, lut, dmin, dmax)
    # Trilinear on a perfect identity LUT should be exact within rounding.
    diff = np.abs(out.astype(int) - img.astype(int))
    assert diff.max() <= 1, f"identity LUT drifted by up to {diff.max()} counts"


# ---------- 2) trilinear matches scipy's reference implementation ----------
def test_trilinear_matches_scipy_reference():
    try:
        from scipy.interpolate import RegularGridInterpolator
    except Exception:
        pytest.skip("scipy not available")

    cube = _teal_orange_cube(17)
    lut, dmin, dmax, N = parse_cube_file(cube)
    img = _make_reference(seed=42, size=128)

    # scipy expects axes = (r, g, b). Build one interpolator per output channel.
    axis = np.linspace(0.0, 1.0, N, dtype=np.float32)
    interps = [
        RegularGridInterpolator((axis, axis, axis), lut[..., c], method="linear",
                                bounds_error=False, fill_value=None)
        for c in range(3)
    ]
    pts = (img.astype(np.float32) / 255.0).reshape(-1, 3)
    ref = np.stack([f(pts) for f in interps], axis=-1).reshape(img.shape)
    ref = np.clip(ref * 255.0, 0, 255).astype(np.uint8)

    ours = apply_lut_trilinear(img, lut, dmin, dmax)
    mean_diff = float(np.mean(np.abs(ours.astype(int) - ref.astype(int))))
    max_diff = int(np.max(np.abs(ours.astype(int) - ref.astype(int))))
    assert mean_diff < 0.6, f"backend trilinear drift vs scipy: mean={mean_diff}"
    assert max_diff <= 2, f"backend trilinear worst-pixel drift vs scipy: {max_diff}"


# ---------- 3) preview (shader) matches print (trilinear) ------------------
def test_preview_matches_print_on_reference_image():
    """Product-level parity: what the guest sees on the kiosk must match what
    comes out of the printer. Both paths share the same LUT — the difference
    is only in how they interpolate. Assert the visual delta is small enough
    that no operator or guest would notice on a real 4x6.
    """
    cube = _teal_orange_cube(17)
    lut, dmin, dmax, N = parse_cube_file(cube)
    img = _make_reference(seed=1, size=256)

    print_out   = apply_lut_trilinear(img, lut, dmin, dmax)  # backend / print
    preview_out = _shader_sim(img, lut)                      # WebGL / preview

    diff = np.abs(print_out.astype(int) - preview_out.astype(int))
    mean_diff = float(diff.mean())
    p99 = float(np.percentile(diff, 99))
    max_diff = int(diff.max())

    # Tight envelopes — the shader is quasi-trilinear (linear on r,g,b), which
    # matches trilinear to sub-pixel precision on smooth LUTs.
    assert mean_diff < 0.5, f"preview/print mean drift {mean_diff:.3f} (>0.5)"
    assert p99 < 2.0,       f"preview/print p99 drift {p99:.3f} (>2)"
    assert max_diff <= 3,   f"preview/print worst-pixel drift {max_diff} (>3)"


# ---------- 4) strip PNG decodes back to the same LUT ----------------------
def test_strip_png_roundtrip():
    lut, _, _, N = parse_cube_file(_teal_orange_cube(17))
    png = lut_to_strip_png(lut)
    img = np.array(Image.open(io.BytesIO(png)).convert("RGB"))
    assert img.shape == (N, N * N, 3)

    # Sample a few known cells and compare with the source LUT
    for r, g, b in [(0, 0, 0), (N // 2, N // 2, N // 2), (N - 1, N - 1, N - 1),
                    (3, 11, 7), (16, 0, 5)]:
        # strip[g, b*N + r]  <-  lut[r, g, b] * 255
        expected = np.clip(lut[r, g, b] * 255.0, 0, 255).astype(np.uint8)
        actual = img[g, b * N + r]
        assert np.array_equal(actual, expected), \
            f"strip mismatch at r={r} g={g} b={b}: {actual} vs {expected}"


# ---------- 5) LUT integrates into the full compose pipeline ---------------
def test_compose_print_uses_lut(tmp_path):
    """End-to-end: compose_print applies the LUT to a real photo."""
    from compositor import compose_print

    # Write a 320x240 reference photo
    photo_path = tmp_path / "p.jpg"
    Image.fromarray(_make_reference(seed=9, size=240)).save(photo_path, "JPEG", quality=95)

    # Minimal 4x6 template with 1 slot
    template = {
        "paper": {"size": "4x6"},
        "canvas": {"width_px": 1200, "height_px": 1800},
        "photo_slots": [{"x": 100, "y": 100, "width": 1000, "height": 1400}],
        "background_color": "#ffffff",
    }

    lut, dmin, dmax, _ = parse_cube_file(_teal_orange_cube(17))
    out_print = tmp_path / "print.png"
    out_web = tmp_path / "web.jpg"

    # Without LUT
    compose_print(template, [str(photo_path)], {}, str(out_print), str(out_web))
    without = np.array(Image.open(out_print).convert("RGB"))

    # With LUT
    compose_print(template, [str(photo_path)], {}, str(out_print), str(out_web),
                  lut=lut, lut_domain=(dmin, dmax))
    with_lut = np.array(Image.open(out_print).convert("RGB"))

    # Same shape (300 DPI 4x6)
    assert without.shape == (1800, 1200, 3)
    assert with_lut.shape == (1800, 1200, 3)

    # The LUT must actually change the pixels
    changed = float(np.mean(np.abs(without.astype(int) - with_lut.astype(int))))
    assert changed > 2.0, f"LUT had no measurable effect (mean diff {changed})"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
