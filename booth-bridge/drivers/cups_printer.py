"""CUPS printer driver — macOS / Linux.

Uses pycups if available, otherwise shells out to `lp` and `lpstat`, both of
which are part of CUPS on every mac and every desktop Linux.

Silent printing: `lp -o media=Custom.<w>x<h>mm -o fit-to-page=false ...` sends
the raw file with no OS dialog and no scaling.
"""
from __future__ import annotations
import asyncio
import logging
import shutil
import subprocess
import time
import uuid
from typing import Optional

from .base import PrinterDriver

log = logging.getLogger("booth-bridge.cups")

PAPER_MM = {
    "2x6": "50.8x152.4mm",
    "2x6_double": "101.6x152.4mm",
    "4x6": "101.6x152.4mm",
    "6x8": "152.4x203.2mm",
    "square": "127x127mm",
}


class CupsPrinterDriver(PrinterDriver):
    name = "cups"

    def __init__(self):
        if not shutil.which("lp"):
            raise RuntimeError("`lp` not on PATH — CUPS not installed")
        self._selected: Optional[str] = None
        self._jobs: dict = {}
        try:
            self._selected = self._default_printer()
        except Exception: pass

    def _default_printer(self) -> Optional[str]:
        try:
            out = subprocess.check_output(["lpstat", "-d"], text=True).strip()
            if "system default destination:" in out:
                return out.split(":", 1)[1].strip()
        except Exception: pass
        return None

    def list(self) -> list:
        try:
            out = subprocess.check_output(["lpstat", "-a"], text=True).strip()
            return [line.split(" ", 1)[0] for line in out.splitlines() if line]
        except Exception:
            return []

    def status(self) -> dict:
        pending = sum(1 for j in self._jobs.values() if j["state"] in ("queued", "printing"))
        return {"name": self._selected or "not selected", "state": "ready",
                "jobs_pending": pending, "media_remaining": None}

    def select(self, name: str) -> None:
        self._selected = name

    async def enqueue(self, file_path: str, copies: int, paper_size: str | None) -> dict:
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
        try:
            cmd = ["lp"]
            if self._selected: cmd += ["-d", self._selected]
            cmd += ["-n", str(job["copies"])]
            media = PAPER_MM.get(job.get("paper_size") or "", None)
            if media:
                cmd += ["-o", f"media=Custom.{media}"]
            cmd += ["-o", "fit-to-page=false", "-o", "position=center", job["file_path"]]
            r = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip() or f"lp exit {r.returncode}")
            job["cups_id"] = r.stdout.strip()
            job["state"] = "done"
        except Exception as e:
            job["state"] = "failed"; job["error"] = str(e)
        job["finished"] = time.time()

    def queue(self) -> list:
        return sorted(self._jobs.values(), key=lambda j: j["created"], reverse=True)[:100]

    def cancel(self, jid: str) -> bool:
        job = self._jobs.get(jid)
        if not job or job["state"] not in ("queued", "printing"): return False
        cups_id = job.get("cups_id")
        if cups_id:
            try: subprocess.run(["cancel", cups_id], check=False)
            except Exception: pass
        job["state"] = "cancelled"
        return True
