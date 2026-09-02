# SnapBooth PRD

## Problem
Production-ready LumaBooth-style photo booth for weddings, birthdays, corporate
activations. Three surfaces: guest kiosk, operator admin, public mobile gallery.
Must work offline on a venue LAN. Cloud sync is optional.

## Architecture
- Backend: FastAPI + MongoDB (motor), Pillow/OpenCV/numpy compositor
- Frontend: React + CRA + Tailwind + shadcn + framer-motion + zustand
- Booth Bridge: separate FastAPI agent on 127.0.0.1:8787 (mock DSLR + printer,
  swap markers for pycups/win32print/gphoto2 in `main.py`)
- Storage: `/app/storage/{eventId}/{sessionId}/`
- Auth: bcrypt password + 30-day JWT in httpOnly cookie + Bearer fallback
- Kiosk exit PIN separate from admin password; CLI reset command available

## Implemented (Feb 2026)
- Backend REST + guest ZIP + QR PNG + LAN IP detection
- 12 filter presets, 5 templates, seeded demo event
- Kiosk: idle → template → filter (live CSS filter preview) → countdown
  (5-1, shutter sound, white flash) → capture → review/retake → processing →
  QR + copies + print again + done
- Guest gallery mobile page with lead-gate toggle + ZIP download + native share
- Admin: Dashboard, Events (CRUD + activate), Templates (visual slot editor,
  numeric x/y/w/h + preview), Filters (enable/disable + preview matches),
  Hardware (camera/printer/bridge/LAN status + print queue), Gallery
  (reprint / open QR / ZIP / delete)
- Booth Bridge stub: camera + printer endpoints, ready for real driver swap
- 300 DPI print rendering at exact paper size, cover fit, cut line for
  duplicate strips, rounded slot masks
- English + Bahasa Indonesia i18n toggle
- Sound: WebAudio beeps, shutter, success chime
- Hidden triple-tap corner + PIN exit gesture

## Deferred (P1/P2)
- GIF / boomerang capture mode
- Overlay PNG upload UI (backend supports it)
- Cloud sync worker
- Green-screen bg removal hook (per capture, pluggable pre-composite step)
- .cube LUT support in preview & backend

## Next
- Testing subagent full journey validation
- Optional: real overlay PNG upload UI + drag/resize handles
