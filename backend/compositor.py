"""Image compositor + filter engine.

The math here MUST match the frontend WebGL / CSS filter preview so the print
matches what the guest saw. Filter params live in a shared JSON schema.
"""
from __future__ import annotations
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw, ImageFont
from typing import Dict, List, Any, Optional
import numpy as np

from lut import apply_lut_trilinear, parse_cube_file


# ---- Paper sizes ----------------------------------------------------------
# 300 DPI exact pixel dimensions (verified constants)
PAPER_SIZES = {
    "2x6": (600, 1800),           # single strip
    "2x6_double": (1200, 1800),   # two strips on 4x6 sheet, centered cut line
    "4x6": (1200, 1800),
    "6x8": (1800, 2400),
    "square": (1500, 1500),       # 5x5 @ 300dpi
}


# ---- Built-in filter presets (JSON parameter object per spec) -------------
def _p(**kw) -> Dict[str, float]:
    base = {
        "brightness": 0, "contrast": 0, "saturation": 0,
        "temperature": 0, "tint": 0, "exposure": 0,
        "highlights": 0, "shadows": 0, "vibrance": 0,
        "grain": 0, "vignette": 0, "fade": 0, "sharpen": 0,
        "skinSmooth": 0,
    }
    base.update(kw)
    return base

PRESETS: Dict[str, Dict[str, Any]] = {
    "original":     {"name": "Original",       "params": _p()},
    "bw":           {"name": "B&W Classic",    "params": _p(saturation=-100, contrast=10)},
    "warm":         {"name": "Warm Film",      "params": _p(temperature=25, saturation=8, fade=10)},
    "cool":         {"name": "Cool Film",      "params": _p(temperature=-25, contrast=5)},
    "vintage":      {"name": "Vintage Fade",   "params": _p(fade=25, saturation=-15, temperature=10, grain=15)},
    "highcontrast": {"name": "High Contrast",  "params": _p(contrast=30, saturation=10)},
    "softglam":     {"name": "Soft Glam",      "params": _p(skinSmooth=25, temperature=8, brightness=5, fade=8)},
    "sepia":        {"name": "Sepia",          "params": _p(saturation=-100, temperature=30, brightness=-3)},
    "teal_orange":  {"name": "Cinematic",      "params": _p(temperature=-8, tint=-8, saturation=15, contrast=15)},
    "airy":         {"name": "Bright Airy",    "params": _p(brightness=12, fade=15, saturation=-5)},
    "moody":        {"name": "Moody Dark",     "params": _p(brightness=-8, contrast=20, shadows=-20, saturation=-10)},
    "polaroid":     {"name": "Polaroid",       "params": _p(fade=20, temperature=15, saturation=-8, vignette=15)},
}


# ---- Filter application on a Pillow image ---------------------------------
def apply_filter_pil(img: Image.Image, params: Dict[str, float],
                     lut: Optional[np.ndarray] = None,
                     lut_domain: Optional[tuple] = None) -> Image.Image:
    p = {**_p(), **(params or {})}
    im = img.convert("RGB")

    # Brightness / Exposure combined
    ev = 1.0 + (p["brightness"] + p["exposure"]) / 100.0
    if ev != 1.0:
        im = ImageEnhance.Brightness(im).enhance(max(0.05, ev))

    # Contrast
    if p["contrast"]:
        im = ImageEnhance.Contrast(im).enhance(1.0 + p["contrast"] / 100.0)

    # Saturation
    if p["saturation"]:
        im = ImageEnhance.Color(im).enhance(max(0, 1.0 + p["saturation"] / 100.0))

    arr = np.asarray(im).astype(np.float32)

    # Temperature (R up / B down = warmer) & Tint (G shift)
    if p["temperature"]:
        t = p["temperature"] / 100.0
        arr[..., 0] += 25 * t
        arr[..., 2] -= 25 * t
    if p["tint"]:
        arr[..., 1] += 20 * (p["tint"] / 100.0)

    # Highlights / Shadows (simple curve)
    if p["highlights"] or p["shadows"]:
        L = arr.mean(axis=-1, keepdims=True) / 255.0
        hi_mask = np.clip((L - 0.5) * 2, 0, 1)
        sh_mask = np.clip((0.5 - L) * 2, 0, 1)
        arr += hi_mask * (p["highlights"])
        arr += sh_mask * (p["shadows"])

    # Fade (lift blacks)
    if p["fade"]:
        f = p["fade"] / 100.0
        arr = arr * (1 - 0.15 * f) + (255 * 0.15 * f)

    arr = np.clip(arr, 0, 255)

    # Sepia after channel ops
    if PRESETS.get("sepia", {}).get("params") and params.get("temperature", 0) == 30 and params.get("saturation", 0) == -100:
        # already handled by sat/temp path, no extra
        pass

    im = Image.fromarray(arr.astype(np.uint8))

    # Skin smooth = mild gaussian blur mixed back
    if p["skinSmooth"]:
        blurred = im.filter(ImageFilter.GaussianBlur(radius=2))
        mix = p["skinSmooth"] / 100.0
        im = Image.blend(im, blurred, min(0.5, mix))

    # Sharpen
    if p["sharpen"]:
        im = ImageEnhance.Sharpness(im).enhance(1.0 + p["sharpen"] / 100.0)

    # Grain
    if p["grain"]:
        noise = np.random.randint(-20, 20, size=(im.height, im.width, 1)) * (p["grain"] / 100.0)
        a = np.asarray(im).astype(np.float32) + noise
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    # Vignette
    if p["vignette"]:
        vg = _vignette_mask(im.size, strength=p["vignette"] / 100.0)
        a = np.asarray(im).astype(np.float32) * vg[..., None]
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    # 3D LUT — applied AFTER the parametric adjustments so a LUT can act as a
    # final color grade on top of exposure/contrast/etc. This matches the
    # WebGL preview pipeline in /app/frontend/src/lib/webglLut.js.
    if lut is not None:
        dmin, dmax = (None, None) if not lut_domain else lut_domain
        arr = apply_lut_trilinear(np.asarray(im), lut, dmin, dmax)
        im = Image.fromarray(arr)

    return im


def _vignette_mask(size, strength: float) -> np.ndarray:
    w, h = size
    y = np.linspace(-1, 1, h)[:, None]
    x = np.linspace(-1, 1, w)[None, :]
    r = np.sqrt(x * x + y * y)
    mask = 1 - np.clip(r * strength * 0.9, 0, 0.85)
    return mask.astype(np.float32)


# ---- Compositor -----------------------------------------------------------
def _cover_fit(im: Image.Image, w: int, h: int) -> Image.Image:
    """object-fit: cover — center-crop to fill exactly w x h."""
    src_ratio = im.width / im.height
    dst_ratio = w / h
    if src_ratio > dst_ratio:
        # source wider — crop sides
        new_w = int(im.height * dst_ratio)
        left = (im.width - new_w) // 2
        im = im.crop((left, 0, left + new_w, im.height))
    else:
        new_h = int(im.width / dst_ratio)
        top = (im.height - new_h) // 2
        im = im.crop((0, top, im.width, top + new_h))
    return im.resize((w, h), Image.LANCZOS)


def _rounded_mask(size, radius: int) -> Image.Image:
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return m


def _fetch_image(src: str) -> Image.Image | None:
    """Load an image from a local path, storage-relative path, or data URL."""
    if not src:
        return None
    try:
        if src.startswith("data:"):
            import base64, io
            b64 = src.split(",", 1)[1]
            return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
        from pathlib import Path
        import os as _os
        p = Path(src)
        if not p.is_absolute():
            # Try storage-relative
            root = Path(_os.environ.get("SNAPBOOTH_STORAGE", "/app/storage"))
            candidate = root / src
            if candidate.exists():
                p = candidate
        if p.exists():
            return Image.open(p).convert("RGBA")
    except Exception:
        return None
    return None


def compose_print(template: Dict[str, Any], photo_paths: List[str],
                  preset: Dict[str, float], out_print: str, out_web: str,
                  lut: Optional[np.ndarray] = None,
                  lut_domain: Optional[tuple] = None) -> None:
    """Compose the print-ready file at exact paper size / 300 DPI.

    template.canvas may not be provided; fall back to paper size in pixels.
    """
    paper = template.get("paper") or {}
    paper_key = paper.get("size", "4x6")
    cw, ch = PAPER_SIZES.get(paper_key, PAPER_SIZES["4x6"])

    canvas = Image.new("RGB", (cw, ch), template.get("background_color", "#ffffff"))

    # Background image (behind photos)
    bg = _fetch_image(template.get("background_image"))
    if bg:
        bg = bg.resize((cw, ch), Image.LANCZOS)
        canvas.paste(bg, (0, 0), bg)

    slots = template.get("photo_slots", [])

    # If duplicateOnSheet + single strip layout, replicate slots on right side
    if template.get("duplicate_on_sheet"):
        strip_w = cw // 2
        extra = []
        for s in slots:
            copy = {**s, "x": s["x"] + strip_w}
            extra.append(copy)
        slots = slots + extra

    for i, slot in enumerate(slots):
        # Map slot photo — for duplicated slots (i >= original count), wrap
        photo_idx = i % max(1, len(photo_paths))
        if photo_idx >= len(photo_paths) or not photo_paths[photo_idx]:
            continue
        try:
            src = Image.open(photo_paths[photo_idx]).convert("RGB")
        except Exception:
            continue
        src = apply_filter_pil(src, preset or {}, lut=lut, lut_domain=lut_domain)
        sx, sy = int(slot["x"]), int(slot["y"])
        sw, sh = int(slot["width"]), int(slot["height"])
        fitted = _cover_fit(src, sw, sh)
        radius = int(slot.get("corner_radius", 0))
        if radius > 0:
            mask = _rounded_mask((sw, sh), radius)
            canvas.paste(fitted, (sx, sy), mask)
        else:
            canvas.paste(fitted, (sx, sy))

    # Overlay image (frame / logo on top)
    ov = _fetch_image(template.get("overlay_image"))
    if ov:
        ov = ov.resize((cw, ch), Image.LANCZOS)
        canvas.paste(ov, (0, 0), ov)

    # Optional text layers
    for layer in template.get("text_layers", []) or []:
        try:
            draw = ImageDraw.Draw(canvas)
            font = ImageFont.load_default()
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(layer.get("font_size", 40)))
            except Exception:
                pass
            draw.text((int(layer["x"]), int(layer["y"])), layer.get("text", ""),
                      fill=layer.get("color", "#111"), font=font)
        except Exception:
            pass

    # Cut line for duplicate strip layouts
    if template.get("duplicate_on_sheet"):
        d = ImageDraw.Draw(canvas)
        d.line([(cw // 2, 0), (cw // 2, ch)], fill=(200, 200, 200), width=2)

    # Save print at 300 DPI
    canvas.save(out_print, "PNG", dpi=(300, 300))
    # Save web version (max 1600 long side, JPEG)
    web = canvas.copy()
    long_side = max(web.size)
    if long_side > 1600:
        scale = 1600 / long_side
        web = web.resize((int(web.size[0] * scale), int(web.size[1] * scale)), Image.LANCZOS)
    web.save(out_web, "JPEG", quality=88)
