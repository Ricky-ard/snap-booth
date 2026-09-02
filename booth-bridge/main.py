"""Booth Bridge — local companion agent for SnapBooth.

This agent runs on the event laptop (macOS / Linux / Windows) and exposes a
small HTTP + WebSocket API on 127.0.0.1:8787 so the browser-based kiosk can
drive a real DSLR / mirrorless camera and a real photo printer that the
browser cannot reach.

Camera drivers (auto-detected in this order):
    1. gphoto2         — macOS / Linux, Canon / Sony / Nikon / Fuji via libgphoto2
    2. digiCamControl  — Windows, HTTP API on :5513
    3. webcam          — cross-platform OpenCV fallback (always works)

Printer drivers:
    1. cups            — macOS / Linux via `lp`  (pycups optional)
    2. windows         — Windows print spooler via win32print / ShellExecute
    3. mock            — logs jobs to memory; used when no printer is picked

Endpoints (spec section 6):

    GET  /health
    GET  /camera/status        -> { connected, model, battery, mode, driver }
    GET  /camera/liveview      -> MJPEG stream (multipart/x-mixed-replace)
    POST /camera/capture       -> { file_path, jpeg_base64 }
    GET  /camera/settings      -> { iso, aperture, shutter, wb }
    POST /camera/settings

    GET  /printer/list         -> system printers
    GET  /printer/status       -> { name, state, jobs_pending, media_remaining }
    POST /printer/print        -> { file_path, copies, paper_size } -> job id
    GET  /printer/queue
    POST /printer/queue/{id}/cancel
    POST /printer/select       -> { name }
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import platform
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from drivers import select_camera_driver, select_printer_driver
from drivers.base import CameraDriver, PrinterDriver

log = logging.getLogger("booth-bridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

STATE: dict = {"camera": None, "printer": None}  # populated on startup


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    forced_cam = os.environ.get("BRIDGE_CAMERA")  # gphoto2 | digicam | webcam
    forced_pr = os.environ.get("BRIDGE_PRINTER")  # cups | windows | mock
    STATE["camera"] = select_camera_driver(preferred=forced_cam)
    STATE["printer"] = select_printer_driver(preferred=forced_pr)
    log.info("Camera  driver: %s", STATE["camera"].name)
    log.info("Printer driver: %s", STATE["printer"].name)
    try:
        yield
    finally:
        try: STATE["camera"].close()
        except Exception: pass
        try: STATE["printer"].close()
        except Exception: pass


app = FastAPI(title="Booth Bridge", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def cam() -> CameraDriver: return STATE["camera"]
def pr() -> PrinterDriver: return STATE["printer"]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class CameraSettingsIn(BaseModel):
    iso: Optional[int] = None
    aperture: Optional[str] = None
    shutter: Optional[str] = None
    wb: Optional[str] = None


class PrintJobIn(BaseModel):
    file_path: str
    copies: int = 1
    paper_size: Optional[str] = "4x6"


class PrinterSelectIn(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {
        "ok": True,
        "platform": platform.system(),
        "python": sys.version.split()[0],
        "camera_driver": cam().name,
        "printer_driver": pr().name,
    }


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
@app.get("/camera/status")
async def camera_status():
    return {**cam().status(), "driver": cam().name}


@app.get("/camera/liveview")
async def camera_liveview():
    boundary = b"--boothbridge"
    async def gen():
        try:
            async for jpeg in cam().liveview():
                yield boundary + b"\r\nContent-Type: image/jpeg\r\nContent-Length: " \
                      + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"
        except asyncio.CancelledError:
            return
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=boothbridge")


@app.post("/camera/capture")
async def camera_capture():
    try:
        return await cam().capture()
    except Exception as e:
        log.exception("capture failed")
        raise HTTPException(500, f"capture failed: {e}")


@app.get("/camera/settings")
async def camera_settings_get():
    return cam().get_settings()


@app.post("/camera/settings")
async def camera_settings_set(payload: CameraSettingsIn):
    return cam().set_settings(**payload.model_dump(exclude_none=True))


# ---------------------------------------------------------------------------
# Printer
# ---------------------------------------------------------------------------
@app.get("/printer/list")
async def printer_list():
    return {"system": platform.system(), "printers": pr().list()}


@app.get("/printer/status")
async def printer_status():
    return pr().status()


@app.post("/printer/select")
async def printer_select(payload: PrinterSelectIn):
    pr().select(payload.name)
    return pr().status()


@app.post("/printer/print")
async def printer_print(payload: PrintJobIn):
    if not Path(payload.file_path).exists():
        raise HTTPException(400, f"file not found: {payload.file_path}")
    job = await pr().enqueue(payload.file_path, payload.copies, payload.paper_size)
    return job


@app.get("/printer/queue")
async def printer_queue():
    return pr().queue()


@app.post("/printer/queue/{jid}/cancel")
async def printer_cancel(jid: str):
    ok = pr().cancel(jid)
    if not ok:
        raise HTTPException(404, "job not found or not cancellable")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="SnapBooth Booth Bridge")
    ap.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8787, help="bind port (default 8787)")
    ap.add_argument("--camera", choices=["gphoto2", "digicam", "webcam"],
                    help="force a camera driver")
    ap.add_argument("--printer", choices=["cups", "windows", "mock"],
                    help="force a printer driver")
    args = ap.parse_args()
    if args.camera: os.environ["BRIDGE_CAMERA"] = args.camera
    if args.printer: os.environ["BRIDGE_PRINTER"] = args.printer

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
