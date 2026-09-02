"""Seed data for demo event."""
from compositor import PAPER_SIZES

# Slot coords are in PRINT PIXELS (300 DPI) matching paper size.

DEFAULT_TEMPLATES = [
    {
        "_id": "tpl-classic-strip",
        "name": "Classic 2x6 Strip",
        "paper": {"size": "2x6", "width_mm": 50.8, "height_mm": 152.4, "dpi": 300},
        "canvas": {"width_px": 600, "height_px": 1800},
        "photo_count": 3,
        "background_color": "#111827",
        "photo_slots": [
            {"x": 40, "y": 40,   "width": 520, "height": 400, "corner_radius": 24},
            {"x": 40, "y": 470,  "width": 520, "height": 400, "corner_radius": 24},
            {"x": 40, "y": 900,  "width": 520, "height": 400, "corner_radius": 24},
        ],
        "text_layers": [
            {"text": "SNAPBOOTH", "x": 130, "y": 1420, "font_size": 60, "color": "#f43f5e"},
            {"text": "MEMORIES", "x": 170, "y": 1500, "font_size": 40, "color": "#ffffff"},
        ],
        "duplicate_on_sheet": False,
    },
    {
        "_id": "tpl-strip-double",
        "name": "2x6 Duo (prints two strips)",
        "paper": {"size": "2x6_double", "width_mm": 101.6, "height_mm": 152.4, "dpi": 300},
        "canvas": {"width_px": 1200, "height_px": 1800},
        "photo_count": 3,
        "background_color": "#0f172a",
        "photo_slots": [
            {"x": 40, "y": 40,   "width": 520, "height": 400, "corner_radius": 20},
            {"x": 40, "y": 470,  "width": 520, "height": 400, "corner_radius": 20},
            {"x": 40, "y": 900,  "width": 520, "height": 400, "corner_radius": 20},
        ],
        "text_layers": [
            {"text": "SNAPBOOTH", "x": 130, "y": 1420, "font_size": 60, "color": "#f43f5e"},
        ],
        "duplicate_on_sheet": True,
    },
    {
        "_id": "tpl-4x6-single",
        "name": "4x6 Portrait",
        "paper": {"size": "4x6", "width_mm": 101.6, "height_mm": 152.4, "dpi": 300},
        "canvas": {"width_px": 1200, "height_px": 1800},
        "photo_count": 1,
        "background_color": "#1e293b",
        "photo_slots": [
            {"x": 60, "y": 60, "width": 1080, "height": 1500, "corner_radius": 32},
        ],
        "text_layers": [
            {"text": "SNAPBOOTH", "x": 400, "y": 1620, "font_size": 80, "color": "#f43f5e"},
        ],
        "duplicate_on_sheet": False,
    },
    {
        "_id": "tpl-4x6-quad",
        "name": "4x6 Quad Grid",
        "paper": {"size": "4x6", "width_mm": 101.6, "height_mm": 152.4, "dpi": 300},
        "canvas": {"width_px": 1200, "height_px": 1800},
        "photo_count": 4,
        "background_color": "#0f172a",
        "photo_slots": [
            {"x": 60,  "y": 60,   "width": 540, "height": 780, "corner_radius": 16},
            {"x": 600, "y": 60,   "width": 540, "height": 780, "corner_radius": 16},
            {"x": 60,  "y": 860,  "width": 540, "height": 780, "corner_radius": 16},
            {"x": 600, "y": 860,  "width": 540, "height": 780, "corner_radius": 16},
        ],
        "text_layers": [
            {"text": "SNAPBOOTH", "x": 430, "y": 1680, "font_size": 60, "color": "#f43f5e"},
        ],
        "duplicate_on_sheet": False,
    },
    {
        "_id": "tpl-square-social",
        "name": "Square Social 1:1",
        "paper": {"size": "square", "width_mm": 127, "height_mm": 127, "dpi": 300},
        "canvas": {"width_px": 1500, "height_px": 1500},
        "photo_count": 1,
        "background_color": "#f9fafb",
        "photo_slots": [
            {"x": 100, "y": 100, "width": 1300, "height": 1200, "corner_radius": 24},
        ],
        "text_layers": [
            {"text": "SNAPBOOTH", "x": 500, "y": 1360, "font_size": 60, "color": "#f43f5e"},
        ],
        "duplicate_on_sheet": False,
        "is_boomerang": True,
    },
]
