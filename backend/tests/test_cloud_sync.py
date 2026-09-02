"""Cloud sync worker tests — driver behaviour and worker loop mechanics.

We avoid pytest-asyncio (the project's pytest.ini forbids modifying addopts)
by wrapping async code with `asyncio.run` inside plain sync test functions.
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from cloud_sync import (  # noqa: E402
    LoggingCloudDriver, HttpCloudDriver, CloudSyncWorker,
    _default_driver,
)


class _AsyncCursor:
    def __init__(self, items): self._items = list(items)
    def sort(self, *a, **kw): return self
    def limit(self, n): self._items = self._items[:n]; return self
    def __aiter__(self):
        self._i = iter(self._items); return self
    async def __anext__(self):
        try: return next(self._i)
        except StopIteration: raise StopAsyncIteration


class _FakeSessions:
    def __init__(self, docs): self.docs = list(docs)
    def find(self, filt=None):
        pending = [d for d in self.docs
                   if d.get("status") == "ready" and not d.get("synced_to_cloud")]
        return _AsyncCursor(pending)
    async def count_documents(self, filt): return len(self.docs)
    async def update_one(self, filt, update):
        sid = filt["_id"]
        for d in self.docs:
            if d["_id"] == sid:
                for k, v in (update.get("$set") or {}).items(): d[k] = v
                for k, v in (update.get("$inc") or {}).items(): d[k] = d.get(k, 0) + v
                for k in (update.get("$unset") or {}): d.pop(k, None)


class _FakeDB:
    def __init__(self, docs): self.sessions = _FakeSessions(docs)


# ---------- driver: LoggingCloudDriver -----------------------------------
def test_logging_driver_writes_outbox(tmp_path):
    d = LoggingCloudDriver(outbox_path=tmp_path / "outbox.jsonl")
    url = asyncio.run(d.upload({"_id": "sess-1", "event_id": "ev-1",
                                "qr_token": "abc", "print_path": "x/y/print.png"}))
    assert url == "local://outbox/sess-1"
    rec = json.loads((tmp_path / "outbox.jsonl").read_text().strip())
    assert rec["session_id"] == "sess-1" and rec["qr_token"] == "abc"


# ---------- driver: HttpCloudDriver failure path -------------------------
def test_http_driver_returns_none_on_connection_error():
    # 127.0.0.1:1 is nearly guaranteed to refuse connections
    d = HttpCloudDriver("http://127.0.0.1:1/upload", timeout=0.5)
    url = asyncio.run(d.upload({"_id": "s", "qr_token": "t"}))
    assert url is None


# ---------- worker drain marks sessions synced ---------------------------
def test_worker_drain_marks_synced(monkeypatch, tmp_path):
    docs = [
        {"_id": "s1", "status": "ready", "event_id": "e", "qr_token": "a",
         "print_path": "p1.png"},
        {"_id": "s2", "status": "ready", "event_id": "e", "qr_token": "b",
         "print_path": "p2.png"},
    ]
    db = _FakeDB(docs)
    monkeypatch.setattr("cloud_sync.internet_reachable", lambda timeout=2.0: True)
    driver = LoggingCloudDriver(outbox_path=tmp_path / "outbox.jsonl")
    w = CloudSyncWorker(db, driver=driver)
    asyncio.run(w._drain_once())
    assert all(d["synced_to_cloud"] for d in docs)
    assert all(d["cloud_url"].startswith("local://outbox/") for d in docs)
    assert w.stats["synced"] == 2


def test_worker_skips_when_offline(monkeypatch):
    docs = [{"_id": "s1", "status": "ready", "event_id": "e", "qr_token": "a"}]
    db = _FakeDB(docs)
    monkeypatch.setattr("cloud_sync.internet_reachable", lambda timeout=2.0: False)
    w = CloudSyncWorker(db, driver=LoggingCloudDriver())
    asyncio.run(w._drain_once())
    assert docs[0].get("synced_to_cloud") is not True
    assert w.stats["synced"] == 0


def test_worker_records_error_on_failed_driver(monkeypatch):
    class _NullDriver(LoggingCloudDriver):
        async def upload(self, session): return None
    docs = [{"_id": "s1", "status": "ready", "event_id": "e", "qr_token": "a"}]
    db = _FakeDB(docs)
    monkeypatch.setattr("cloud_sync.internet_reachable", lambda timeout=2.0: True)
    w = CloudSyncWorker(db, driver=_NullDriver())
    asyncio.run(w._drain_once())
    assert docs[0].get("synced_to_cloud") is not True
    assert docs[0].get("sync_attempts") == 1
    assert "upload returned" in docs[0].get("last_sync_error", "")
    assert w.stats["failed"] == 1


# ---------- default driver picks env-configured HTTP when set ------------
def test_default_driver_switches_on_env(monkeypatch):
    monkeypatch.delenv("SYNC_ENDPOINT_URL", raising=False)
    assert _default_driver().name == "logging"
    monkeypatch.setenv("SYNC_ENDPOINT_URL", "https://example.com/hook")
    assert _default_driver().name == "http"
