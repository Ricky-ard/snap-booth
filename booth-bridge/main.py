"""Booth Bridge — local companion agent.

Runs on the event laptop (NOT in the cloud). Talks to the DSLR (gphoto2 /
digiCamControl) and the printer (CUPS on macOS/Linux, spooler on Windows) and
exposes a small HTTP API on 127.0.0.1:8787 that the web app calls.

This file is a fully working mock/scaffold — endpoints return realistic
payloads so the SnapBooth UI can be developed against it. Real drivers are
stubbed with clearly marked TODO sections.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import asyncio, io, os, sys, time, platform

app = FastAPI(title="Booth Bridge")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATE = {
    "camera": {"connected": True, "model": "Mock DSLR (Canon-like)", "battery": 85, "mode": "Manual"},
    "printer": {"name": "Mock DNP DS-RX1HS", "state": "ready", "jobs_pending": 0, "media_remaining": 400},
    "jobs": [],  # {id, state, copies, path, created}
    "settings": {"iso": 400, "aperture": "f/4.0", "shutter": "1/125", "wb": "auto"},
}


class CameraSettings(BaseModel):
    iso: Optional[int] = None
    aperture: Optional[str] = None
    shutter: Optional[str] = None
    wb: Optional[str] = None


class PrintJobIn(BaseModel):
    file_path: str
    copies: int = 1
    paper_size: Optional[str] = "4x6"


# -------- Camera --------
@app.get("/camera/status")
async def camera_status():
    # TODO: replace with gphoto2 (macOS/Linux) or digiCamControl HTTP (Windows)
    return STATE["camera"]

@app.get("/camera/settings")
async def camera_settings_get():
    return STATE["settings"]

@app.post("/camera/settings")
async def camera_settings_set(payload: CameraSettings):
    for k, v in payload.model_dump(exclude_none=True).items():
        STATE["settings"][k] = v
    return STATE["settings"]

@app.post("/camera/capture")
async def camera_capture():
    # TODO: gphoto2.trigger_capture() or digiCamControl /?slc=capture
    # For now, return a placeholder 1x1 JPEG so callers can integrate flow.
    import base64
    stub = base64.b64encode(bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707"
        "070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c"
        "2837292c30313434341f27393d38323c2e333432ffdb0043010909090c0b0c180d0d1832"
        "1c1c211c32323232323232323232323232323232323232323232323232323232323232"
        "3232323232323232323232323232323232323232323232ffc0001108000100010301220"
        "0021101031101ffc4001f0000010501010101010100000000000000000102030405060"
        "708090a0bffc400b5100002010303020403050504040000017d01020300041105122131"
        "410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a252"
        "6272829"))
    return {"file_path": "/dev/null", "jpeg_base64": stub.decode()}


# -------- Live view (MJPEG stub) --------
async def _mjpeg():
    """Yields a periodic tiny JPEG so the UI can wire up a stream if needed."""
    while True:
        import base64
        b = base64.b64decode("/9j/4AAQSkZJRgABAQEAAAAAAAD//gA7Q1JFQVRPUjogZ2QtanBlZ/8AwABQAKAAAAA/9k=".encode())
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + b + b"\r\n")
        await asyncio.sleep(0.1)

@app.get("/camera/liveview")
async def liveview():
    return StreamingResponse(_mjpeg(), media_type="multipart/x-mixed-replace;boundary=frame")


# -------- Printer --------
@app.get("/printer/list")
async def printer_list():
    system = platform.system()
    # TODO: use pycups on macOS/Linux, win32print on Windows
    return {"system": system, "printers": [STATE["printer"]["name"], "PDF (Preview)"]}

@app.get("/printer/status")
async def printer_status():
    return STATE["printer"]

@app.post("/printer/print")
async def printer_print(payload: PrintJobIn):
    if not os.path.exists(payload.file_path):
        raise HTTPException(400, f"file not found: {payload.file_path}")
    jid = f"job-{int(time.time() * 1000)}"
    job = {"id": jid, "state": "queued", "copies": payload.copies,
           "file_path": payload.file_path, "created": time.time()}
    STATE["jobs"].append(job)
    STATE["printer"]["jobs_pending"] = sum(1 for j in STATE["jobs"] if j["state"] in ("queued", "printing"))
    asyncio.create_task(_process_job(jid))
    return {"job_id": jid, "state": "queued"}

async def _process_job(jid: str):
    # Simulate printing latency; on a real machine use pycups.printFile / ShellExecute "print"
    job = next((j for j in STATE["jobs"] if j["id"] == jid), None)
    if not job:
        return
    job["state"] = "printing"
    await asyncio.sleep(3)
    job["state"] = "done"
    STATE["printer"]["media_remaining"] = max(0, STATE["printer"]["media_remaining"] - job["copies"])
    STATE["printer"]["jobs_pending"] = sum(1 for j in STATE["jobs"] if j["state"] in ("queued", "printing"))

@app.get("/printer/queue")
async def printer_queue():
    return STATE["jobs"][-50:]

@app.post("/printer/queue/{jid}/cancel")
async def printer_cancel(jid: str):
    for j in STATE["jobs"]:
        if j["id"] == jid and j["state"] in ("queued", "printing"):
            j["state"] = "cancelled"
            return {"ok": True}
    raise HTTPException(404, "job not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8787)
