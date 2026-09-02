"""Windows print spooler driver.

Uses pywin32 (win32print) to enumerate printers and to send raw files to the
default or selected printer. Prints silently — no OS dialog — via
ShellExecute("printto") which respects the printer's paper size settings.

For borderless dye-sub printers (DNP DS-RX1HS, Citizen CX-02, Canon Selphy
CP1500), configure the paper size in the printer preferences once and select
"borderless" so ShellExecute prints at exact paper dimensions with no scaling.
"""
from __future__ import annotations
import asyncio
import logging
import os
import time
import uuid
from typing import Optional

from .base import PrinterDriver

log = logging.getLogger("booth-bridge.windows-printer")


class WindowsPrinterDriver(PrinterDriver):
    name = "windows"

    def __init__(self):
        try:
            import win32print  # noqa
            import win32api    # noqa
            self._win32print = win32print
            self._win32api = win32api
        except Exception as e:
            raise RuntimeError(f"pywin32 not installed: {e}")
        self._selected: Optional[str] = self._win32print.GetDefaultPrinter()
        self._jobs: dict = {}

    def list(self) -> list:
        flags = self._win32print.PRINTER_ENUM_LOCAL | self._win32print.PRINTER_ENUM_CONNECTIONS
        try:
            return [p[2] for p in self._win32print.EnumPrinters(flags)]
        except Exception:
            return []

    def status(self) -> dict:
        pending = sum(1 for j in self._jobs.values() if j["state"] in ("queued", "printing"))
        info = {}
        try:
            h = self._win32print.OpenPrinter(self._selected)
            try:
                info = self._win32print.GetPrinter(h, 2) or {}
            finally:
                self._win32print.ClosePrinter(h)
        except Exception: pass
        return {"name": self._selected or "not selected",
                "state": "ready", "jobs_pending": pending,
                "media_remaining": None,
                "raw": {"status": info.get("Status") if isinstance(info, dict) else None}}

    def select(self, name: str) -> None:
        self._selected = name
        try: self._win32print.SetDefaultPrinter(name)
        except Exception: pass

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
            for _ in range(int(job["copies"])):
                await asyncio.to_thread(
                    self._win32api.ShellExecute, 0, "printto", job["file_path"],
                    f'"{self._selected}"', ".", 0,
                )
            job["state"] = "done"
        except Exception as e:
            job["state"] = "failed"; job["error"] = str(e)
        job["finished"] = time.time()

    def queue(self) -> list:
        return sorted(self._jobs.values(), key=lambda j: j["created"], reverse=True)[:100]

    def cancel(self, jid: str) -> bool:
        job = self._jobs.get(jid)
        if not job or job["state"] not in ("queued", "printing"): return False
        job["state"] = "cancelled"
        return True
