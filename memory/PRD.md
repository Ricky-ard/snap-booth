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

## Implemented (through Feb 2026)
- Backend REST + guest ZIP + QR PNG + LAN IP detection
- 12 filter presets, 5 templates, seeded demo event
- Kiosk: idle → template → filter (live CSS/WebGL LUT preview) → countdown
  (5–1, shutter sound, white flash) → capture → still-preview (2s) →
  review/retake → processing → QR + copies + print again + done
- Guest gallery mobile page with lead-gate toggle + ZIP download + native share
- Admin: Dashboard, Events (CRUD + activate), Templates (visual slot editor,
  numeric x/y/w/h + drag-and-drop + snap-to-grid), Filters (enable/disable +
  preview matches), Hardware (camera/printer/bridge/LAN status + print queue),
  Gallery (reprint / open QR / ZIP / delete)
- Booth Bridge stub: camera + printer endpoints, ready for real driver swap
- 300 DPI print rendering at exact paper size (measured: 4x6=1200x1800,
  2x6=600x1800, square=1500x1500)
- English + Bahasa Indonesia i18n toggle
- Sound: WebAudio beeps, shutter, success chime
- Hidden triple-tap corner + PIN exit gesture
- .cube 3D LUT support (WebGL preview + OpenCV backend trilinear parity)
- Boomerang / GIF capture (imageio + imageio-ffmpeg)
- Offline PWA service worker + background cloud sync worker
- **Persistent kiosk live feed** — MediaStream acquired once via Zustand,
  <video> mounted continuously behind countdown / still-preview / review as
  transparent z-10 overlays (iteration_5 verified: 0 detach events, 138
  countdown samples + 57 still-preview samples all mounted, readyState=4,
  visibility=visible, gUM called exactly once per session)
- **Stale-closure capture bug** — RESOLVED and verified at runtime by
  testing_agent iteration_5. sessionRef + countdownIv refs, non-bare catches,
  ctx.filter-before-drawImage, finalize precheck guard, template-auto in
  useEffect all confirmed working.

## Known bugs (surfaced by iteration_5, NOT yet fixed)
- **HIGH** — Retake cascade on multi-shot templates. `retake(n)` calls
  `runCountdown(n)` and captureShot's tail unconditionally recurses into
  slot n+1. Reproduced deterministically: "Retake #2" on the 3-photo strip
  fires /sessions/photo for slot 1 then slot 2. Fix: pass a retake flag to
  captureShot so it goes back to review after one shot.
- **HIGH** — Countdown intermittently skips a tick (e.g. renders 5,4,2,1).
  Root cause: `AnimatePresence mode="wait"` around a spring exit whose settle
  time (~1000ms+) exceeds the 1s setInterval. Fix: drop `mode="wait"` or give
  the exit an explicit ≤200ms tween.
- **LOW** — Delivery print preview <img> has no max-height, tall 2x6 strips
  overflow the viewport. Add `max-h-[80vh] w-auto object-contain`.
- **LOW** — Backend defence-in-depth: `POST /api/sessions/{id}/finalize`
  should 400 on `raw_photos == []` instead of composing an empty print.
- **INFO** — Filter preview parity gap: paramsToCss covers brightness,
  contrast, saturate, and a rough blur; it does NOT map temperature (backend
  additive R/B channel shift), highlights, shadows, fade, grain, vignette.
  LUT-based presets ARE at parity (WebGL trilinear ≈ OpenCV trilinear).

## Deferred (P1/P2)
- Green-screen / AI background-removal HOOK (per capture, pluggable
  pre-composite step) — user wants a strict BackgroundDriver interface with a
  byte-identical passthrough default, event-level toggle, and per-photo call
  between filter step and template compositing.
- Overlay PNG upload UI in the template editor (backend already supports it)
- Real driver swaps in booth-bridge (gphoto2 / pycups / win32print)

## Next
- Await user confirmation on retake cascade + tick-skip fixes before touching
  Kiosk.jsx again (user asked to report and stop, not to write new features).
- Then implement the P1 background-removal driver interface.
