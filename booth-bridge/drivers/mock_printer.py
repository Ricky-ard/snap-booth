"""Mock printer driver — always available.

Logs jobs to memory and marks them "done" after a short delay. Used when
neither CUPS nor the Windows spooler is available, or when the operator wants
to rehearse without paper.
"""
from __future__ import annotations
import asyncio
import time
import uuid
from typing import Optional

from .base import PrinterDriver


class MockPrinterDriver(PrinterDriver):
    name = "mock"

    def __init__(self):
        self._selected: Optional[str] = "Mock Dye-Sub"
        self._jobs: dict = {}
        self._media_remaining = 400

    def list(self) -> list: return ["Mock Dye-Sub", "PDF (preview)"]
    def status(self) -> dict:
        pending = sum(1 for j in self._jobs.values() if j["state"] in ("queued", "printing"))
        return {"name": self._selected, "state": "ready",
                "jobs_pending": pending, "media_remaining": self._media_remaining}

    def select(self, name: str) -> None: self._selected = name

    async def enqueue(self, file_path, copies, paper_size) -> dict:
        jid = str(uuid.uuid4())
        job = {"id": jid, "file_path": file_path, "copies": copies,
               "paper_size": paper_size, "state": "queued", "created": time.time(),
               "printer": self._selected, "error": None}
        self._jobs[jid] = job
        asyncio.create_task(self._run(jid))
        return job

    async def _run(self, jid: str):
        job = self._jobs[jid]
        job["state"] = "printing"
        await asyncio.sleep(2.0)
        job["state"] = "done"
        job["finished"] = time.time()
        self._media_remaining = max(0, self._media_remaining - job["copies"])

    def queue(self) -> list:
        return sorted(self._jobs.values(), key=lambda j: j["created"], reverse=True)[:100]

    def cancel(self, jid: str) -> bool:
        job = self._jobs.get(jid)
        if not job or job["state"] not in ("queued", "printing"): return False
        job["state"] = "cancelled"
        return True
