"""Cloud sync worker — uploads finished sessions to a remote backup when the
internet is reachable.

Design:
    - `CloudSyncDriver` abstract interface — `upload(session, files)` returns the
      public cloud URL of the uploaded print (or None on failure).
    - Two shipped drivers:
        * `LoggingCloudDriver`  — writes an "outbox.jsonl" record to storage
          and marks the session cloud_url = f"local://outbox/{sid}". Useful for
          demos and tests without any external service.
        * `HttpCloudDriver`     — POSTs a multipart form with the session's
          artefacts to `SYNC_ENDPOINT_URL` with a `SYNC_API_KEY` bearer token.
          Fires only when SYNC_ENDPOINT_URL is set in the environment.
    - Background loop scans MongoDB for `synced_to_cloud=false` sessions every
      `SYNC_INTERVAL` seconds (default 30) and only when reachability probe
      succeeds. Exponential backoff on failure.

Wire-up in server.py:
    from cloud_sync import start_sync_worker
    @app.on_event("startup") ... start_sync_worker(app, db)
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import socket
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("snapbooth.sync")

SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL", "30"))
SYNC_ENDPOINT_URL = os.environ.get("SYNC_ENDPOINT_URL", "")
SYNC_API_KEY = os.environ.get("SYNC_API_KEY", "")
STORAGE = Path(os.environ.get("SNAPBOOTH_STORAGE", "/app/storage"))


def _now_iso() -> str: return datetime.now(timezone.utc).isoformat()


def internet_reachable(timeout: float = 2.0) -> bool:
    """Cheap connectivity probe — DNS resolution + TCP handshake to Cloudflare."""
    try:
        sock = socket.create_connection(("1.1.1.1", 53), timeout=timeout)
        sock.close()
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# Drivers
# --------------------------------------------------------------------------
class CloudSyncDriver(ABC):
    name: str = "base"

    @abstractmethod
    async def upload(self, session: dict) -> Optional[str]:
        """Return the public cloud URL of the uploaded print, or None on failure."""


class LoggingCloudDriver(CloudSyncDriver):
    """Writes a JSONL outbox line per session. Useful for offline demos."""
    name = "logging"

    def __init__(self, outbox_path: Path | None = None):
        self.outbox = outbox_path or (STORAGE / "cloud_outbox.jsonl")
        self.outbox.parent.mkdir(parents=True, exist_ok=True)

    async def upload(self, session: dict) -> Optional[str]:
        rec = {
            "session_id": session["_id"],
            "event_id": session.get("event_id"),
            "qr_token": session.get("qr_token"),
            "print_path": session.get("print_path"),
            "gif_path": session.get("gif_path"),
            "mp4_path": session.get("mp4_path"),
            "uploaded_at": _now_iso(),
        }
        await asyncio.to_thread(
            self._append, rec,
        )
        return f"local://outbox/{session['_id']}"

    def _append(self, rec: dict):
        with open(self.outbox, "a") as f:
            f.write(json.dumps(rec) + "\n")


class HttpCloudDriver(CloudSyncDriver):
    """POSTs artefacts as multipart form-data to SYNC_ENDPOINT_URL.

    The remote service is expected to store them and return
        { "url": "https://.../g/{token}", ... }
    which we save on the session as `cloud_url` so the guest-gallery QR points
    to the public URL when it's available (and the LAN URL otherwise).
    """
    name = "http"

    def __init__(self, endpoint: str, api_key: str = "", timeout: float = 60):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def upload(self, session: dict) -> Optional[str]:
        import httpx
        files = {}
        for k in ("print_path", "web_path", "gif_path", "mp4_path"):
            rel = session.get(k)
            if not rel: continue
            fp = STORAGE / rel
            if fp.exists():
                files[k.replace("_path", "")] = (fp.name, fp.read_bytes())
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = {
            "session_id": session["_id"],
            "qr_token": session.get("qr_token", ""),
            "event_id": session.get("event_id", ""),
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                r = await c.post(self.endpoint, data=data, files=files, headers=headers)
                if r.status_code >= 400:
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
                body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                return body.get("url") or f"remote://{self.endpoint}/{session['_id']}"
        except Exception as e:
            log.warning("http cloud upload failed for %s: %s", session["_id"], e)
            return None


def _default_driver() -> CloudSyncDriver:
    endpoint = os.environ.get("SYNC_ENDPOINT_URL", "")
    api_key = os.environ.get("SYNC_API_KEY", "")
    if endpoint:
        return HttpCloudDriver(endpoint, api_key)
    return LoggingCloudDriver()


# --------------------------------------------------------------------------
# Worker loop
# --------------------------------------------------------------------------
class CloudSyncWorker:
    def __init__(self, db, driver: CloudSyncDriver | None = None):
        self.db = db
        self.driver = driver or _default_driver()
        self._task: asyncio.Task | None = None
        self._trigger = asyncio.Event()
        self._backoff = 1
        self.stats = {"last_run": None, "last_success": None, "failed": 0, "synced": 0}

    def running(self) -> bool: return self._task is not None and not self._task.done()

    def start(self):
        if self.running(): return
        self._task = asyncio.create_task(self._loop(), name="cloud-sync")
        log.info("cloud sync worker started (driver=%s)", self.driver.name)

    def stop(self):
        if self._task: self._task.cancel()
        self._task = None

    def trigger(self):
        self._trigger.set()

    async def _loop(self):
        while True:
            try:
                await asyncio.wait_for(self._trigger.wait(), timeout=SYNC_INTERVAL)
            except asyncio.TimeoutError:
                pass
            self._trigger.clear()
            self.stats["last_run"] = _now_iso()
            try:
                await self._drain_once()
                self._backoff = 1
            except Exception as e:
                log.exception("sync drain failed")
                self._backoff = min(self._backoff * 2, 300)
                await asyncio.sleep(self._backoff)

    async def _drain_once(self):
        if not await asyncio.to_thread(internet_reachable):
            return
        cursor = self.db.sessions.find({
            "status": "ready",
            "synced_to_cloud": {"$ne": True},
        }).sort("completed_at", 1).limit(20)
        async for sess in cursor:
            try:
                url = await self.driver.upload(sess)
                if url:
                    await self.db.sessions.update_one({"_id": sess["_id"]}, {"$set": {
                        "synced_to_cloud": True,
                        "cloud_url": url,
                        "synced_at": _now_iso(),
                    }})
                    self.stats["synced"] += 1
                    self.stats["last_success"] = _now_iso()
                else:
                    await self.db.sessions.update_one({"_id": sess["_id"]}, {"$inc": {
                        "sync_attempts": 1,
                    }, "$set": {"last_sync_error": "upload returned no url",
                                "last_sync_error_at": _now_iso()}})
                    self.stats["failed"] += 1
            except Exception as e:
                await self.db.sessions.update_one({"_id": sess["_id"]}, {"$inc": {
                    "sync_attempts": 1,
                }, "$set": {"last_sync_error": str(e)[:200],
                            "last_sync_error_at": _now_iso()}})
                self.stats["failed"] += 1


_worker: CloudSyncWorker | None = None


def start_sync_worker(db) -> CloudSyncWorker:
    global _worker
    if _worker and _worker.running(): return _worker
    _worker = CloudSyncWorker(db)
    _worker.start()
    return _worker


def get_worker() -> CloudSyncWorker | None:
    return _worker
