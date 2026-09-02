"""gphoto2 camera driver — macOS / Linux.

Uses python-gphoto2 (libgphoto2 bindings). Auto-detects the first attached
DSLR / mirrorless. Supports:

    - status()          -> connected, model, battery, mode
    - capture()         -> triggers shutter, downloads JPEG, returns base64
    - get/set_settings  -> iso, aperture, shutter, wb (white balance)
    - liveview()        -> streams the camera's live view JPEG frames

Threading: python-gphoto2 is NOT asyncio-friendly. All blocking ops are
scheduled on a threadpool.
"""
from __future__ import annotations
import asyncio
import base64
import io
import logging
import os
import tempfile
import threading
import time
from typing import AsyncIterator

from .base import CameraDriver

log = logging.getLogger("booth-bridge.gphoto2")

# python-gphoto2 config keys map (SI names -> libgphoto2 widget names)
_SETTING_KEYS = {
    "iso": ["iso", "eos-iso", "iso-speed"],
    "aperture": ["aperture", "f-number"],
    "shutter": ["shutterspeed", "shutter-speed"],
    "wb": ["whitebalance", "white-balance"],
}


class Gphoto2CameraDriver(CameraDriver):
    name = "gphoto2"

    def __init__(self):
        self._gp = None
        self._camera = None
        self._lock = threading.Lock()

    def probe(self) -> bool:
        try:
            import gphoto2 as gp  # noqa
            self._gp = gp
        except Exception:
            return False
        try:
            self._connect()
            return self._camera is not None
        except Exception as e:
            log.info("gphoto2 no camera: %s", e)
            return False

    # ---- helpers -----------------------------------------------------
    def _connect(self):
        gp = self._gp
        with self._lock:
            if self._camera is not None: return
            camera = gp.Camera()
            camera.init()
            self._camera = camera

    def _reconnect(self):
        with self._lock:
            try:
                if self._camera is not None:
                    self._camera.exit()
            except Exception: pass
            self._camera = None
        self._connect()

    def _find_config(self, camera, keys):
        cfg = camera.get_config()
        for key in keys:
            try:
                widget = cfg.get_child_by_name(key)
                return cfg, widget
            except Exception:
                continue
        raise KeyError(f"none of {keys} on camera")

    # ---- public API --------------------------------------------------
    def status(self) -> dict:
        if self._camera is None:
            return {"connected": False, "model": None, "battery": None, "mode": None}
        try:
            summary = str(self._camera.get_summary()) if self._camera else ""
            # crude field extraction
            model = None
            for line in summary.splitlines():
                if "Model" in line and ":" in line:
                    model = line.split(":", 1)[1].strip(); break
            battery = None
            try:
                _, widget = self._find_config(self._camera, ["batterylevel", "battery-level"])
                battery = widget.get_value()
            except Exception: pass
            return {"connected": True, "model": model or "gphoto2 device",
                    "battery": battery, "mode": None}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def capture(self) -> dict:
        return await asyncio.to_thread(self._capture_sync)

    def _capture_sync(self) -> dict:
        gp = self._gp
        with self._lock:
            file_path = self._camera.capture(gp.GP_CAPTURE_IMAGE)
            camera_file = self._camera.file_get(
                file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL)
            data = memoryview(camera_file.get_data_and_size()).tobytes()
        # save to a temp file so the caller can reference by path if needed
        tmp = os.path.join(tempfile.gettempdir(), f"snapbooth_{int(time.time()*1000)}_{file_path.name}")
        with open(tmp, "wb") as f: f.write(data)
        return {"file_path": tmp, "jpeg_base64": base64.b64encode(data).decode()}

    def get_settings(self) -> dict:
        if self._camera is None: return {}
        out = {}
        for si, keys in _SETTING_KEYS.items():
            try:
                _, w = self._find_config(self._camera, keys)
                out[si] = w.get_value()
            except Exception:
                out[si] = None
        return out

    def set_settings(self, **kw) -> dict:
        if self._camera is None: raise RuntimeError("camera not connected")
        for si, value in kw.items():
            keys = _SETTING_KEYS.get(si)
            if not keys: continue
            with self._lock:
                cfg, w = self._find_config(self._camera, keys)
                w.set_value(str(value))
                self._camera.set_config(cfg)
        return self.get_settings()

    async def liveview(self) -> AsyncIterator[bytes]:
        gp = self._gp
        try:
            while True:
                jpeg = await asyncio.to_thread(self._liveview_frame)
                if jpeg: yield jpeg
                await asyncio.sleep(1 / 30)  # ~30fps target
        except GeneratorExit:
            return

    def _liveview_frame(self) -> bytes:
        gp = self._gp
        with self._lock:
            try:
                cam_file = self._camera.capture_preview()
                data = memoryview(cam_file.get_data_and_size()).tobytes()
                return data
            except Exception as e:
                log.debug("liveview frame failed: %s", e)
                return b""

    def close(self):
        with self._lock:
            try:
                if self._camera is not None:
                    self._camera.exit()
            except Exception: pass
            self._camera = None
