"""OpenCV webcam fallback camera driver — cross-platform.

Used when neither gphoto2 nor digiCamControl finds a DSLR. Also handy for
development on machines without a camera attached (`disabled=True` returns a
'connected: false' stub that keeps the API surface intact).
"""
from __future__ import annotations
import asyncio
import base64
import logging
import os
import tempfile
import time
from typing import AsyncIterator

from .base import CameraDriver

log = logging.getLogger("booth-bridge.webcam")


class WebcamCameraDriver(CameraDriver):
    name = "webcam"

    def __init__(self, index: int = 0, disabled: bool = False):
        self.index = index
        self.disabled = disabled
        self._cap = None
        self._settings = {"iso": None, "aperture": None, "shutter": None, "wb": None}

    def probe(self) -> bool:
        if self.disabled: return False
        try:
            import cv2  # noqa
            cap = cv2.VideoCapture(self.index)
            ok = cap.isOpened()
            if ok:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                self._cap = cap
            else:
                cap.release()
            return ok
        except Exception as e:
            log.info("opencv webcam probe failed: %s", e)
            return False

    def status(self) -> dict:
        if self.disabled:
            return {"connected": False, "model": "none", "battery": None, "mode": None,
                    "hint": "no DSLR detected and no local webcam — falling back to browser getUserMedia"}
        return {"connected": self._cap is not None, "model": f"webcam#{self.index}",
                "battery": None, "mode": "auto"}

    async def capture(self) -> dict:
        return await asyncio.to_thread(self._capture_sync)

    def _capture_sync(self) -> dict:
        import cv2
        if self._cap is None: raise RuntimeError("webcam not available")
        for _ in range(3):  # discard 2 stale frames
            ok, _ = self._cap.read()
        ok, frame = self._cap.read()
        if not ok: raise RuntimeError("frame grab failed")
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        data = bytes(buf)
        tmp = os.path.join(tempfile.gettempdir(), f"snapbooth_{int(time.time()*1000)}.jpg")
        with open(tmp, "wb") as f: f.write(data)
        return {"file_path": tmp, "jpeg_base64": base64.b64encode(data).decode()}

    def get_settings(self) -> dict: return self._settings
    def set_settings(self, **kw) -> dict:
        self._settings.update({k: v for k, v in kw.items() if k in self._settings})
        return self._settings

    async def liveview(self) -> AsyncIterator[bytes]:
        import cv2
        while True:
            if self._cap is None: await asyncio.sleep(0.5); continue
            ok, frame = await asyncio.to_thread(self._cap.read)
            if not ok: await asyncio.sleep(0.1); continue
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ok: yield bytes(buf)
            await asyncio.sleep(1 / 30)

    def close(self):
        try:
            if self._cap is not None: self._cap.release()
        except Exception: pass
