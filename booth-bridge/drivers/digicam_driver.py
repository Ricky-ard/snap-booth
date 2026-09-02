"""digiCamControl camera driver — Windows.

digiCamControl (https://digicamcontrol.com/) is a free Windows app that talks
to almost every Canon / Nikon / Sony body. When its "Web Server" is enabled it
exposes a simple HTTP API at http://127.0.0.1:5513.

We speak that API here so SnapBooth doesn't have to know which physical camera
is attached.

Live view: digiCamControl serves a still JPEG at /liveview.jpg. We poll it
~30 times per second to build our own MJPEG stream for the browser.
"""
from __future__ import annotations
import asyncio
import base64
import logging
import os
import tempfile
import time
from typing import AsyncIterator

import httpx

from .base import CameraDriver

log = logging.getLogger("booth-bridge.digicam")

DCC_URL = os.environ.get("DIGICAM_URL", "http://127.0.0.1:5513")


class DigiCamControlDriver(CameraDriver):
    name = "digicam"

    def __init__(self, url: str = DCC_URL):
        self.url = url.rstrip("/")
        self._client = httpx.Client(timeout=10.0)

    # digiCamControl uses querystring commands like:
    #   /?slc=capture
    #   /?slc=set&param1=iso&param2=400
    #   /?slc=get&param1=lastcaptured
    #   /liveviewstart, /liveviewstop, /liveview.jpg
    def _cmd(self, slc: str, param1: str = "", param2: str = "") -> str:
        params = {"slc": slc}
        if param1: params["param1"] = param1
        if param2: params["param2"] = param2
        r = self._client.get(self.url + "/", params=params)
        r.raise_for_status()
        return r.text.strip()

    def probe(self) -> bool:
        try:
            self._client.get(self.url + "/", timeout=1.0)
            return True
        except Exception:
            return False

    def status(self) -> dict:
        try:
            model = self._cmd("get", "cameramodel") or "digiCamControl device"
            battery = self._cmd("get", "batterylevel") or None
            mode = self._cmd("get", "mode") or None
            return {"connected": True, "model": model, "battery": battery, "mode": mode}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def capture(self) -> dict:
        return await asyncio.to_thread(self._capture_sync)

    def _capture_sync(self) -> dict:
        self._cmd("capture")
        # digiCamControl saves to its Session folder; grab the path of the last file
        last = self._cmd("get", "lastcaptured")
        data = b""
        if last and os.path.exists(last):
            with open(last, "rb") as f: data = f.read()
        else:
            # fallback — read a still from the liveview endpoint
            r = self._client.get(self.url + "/liveview.jpg")
            r.raise_for_status()
            data = r.content
            last = os.path.join(tempfile.gettempdir(), f"snapbooth_{int(time.time()*1000)}.jpg")
            with open(last, "wb") as f: f.write(data)
        return {"file_path": last, "jpeg_base64": base64.b64encode(data).decode()}

    def get_settings(self) -> dict:
        out = {}
        for k in ("iso", "fnumber", "shutterspeed", "whitebalance"):
            try: out[k] = self._cmd("get", k)
            except Exception: out[k] = None
        # normalize to SI keys
        return {"iso": out.get("iso"), "aperture": out.get("fnumber"),
                "shutter": out.get("shutterspeed"), "wb": out.get("whitebalance")}

    def set_settings(self, **kw) -> dict:
        _map = {"iso": "iso", "aperture": "fnumber",
                "shutter": "shutterspeed", "wb": "whitebalance"}
        for si, value in kw.items():
            key = _map.get(si)
            if not key: continue
            try: self._cmd("set", key, str(value))
            except Exception as e: log.info("set %s failed: %s", key, e)
        return self.get_settings()

    async def liveview(self) -> AsyncIterator[bytes]:
        # start live view (idempotent)
        try: self._cmd("do", "startliveview")
        except Exception: pass
        try:
            async with httpx.AsyncClient(timeout=5.0) as ac:
                while True:
                    try:
                        r = await ac.get(self.url + "/liveview.jpg")
                        if r.status_code == 200 and r.content:
                            yield r.content
                    except Exception as e:
                        log.debug("liveview poll failed: %s", e)
                    await asyncio.sleep(1 / 30)
        finally:
            try: self._cmd("do", "stopliveview")
            except Exception: pass

    def close(self):
        try: self._client.close()
        except Exception: pass
