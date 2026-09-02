"""Abstract driver interfaces."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any


class CameraDriver(ABC):
    name: str = "base"

    @abstractmethod
    def probe(self) -> bool: ...
    @abstractmethod
    def status(self) -> dict: ...
    @abstractmethod
    async def capture(self) -> dict: ...
    @abstractmethod
    def get_settings(self) -> dict: ...
    @abstractmethod
    def set_settings(self, **kw) -> dict: ...
    @abstractmethod
    def liveview(self) -> AsyncIterator[bytes]: ...
    def close(self) -> None: pass


class PrinterDriver(ABC):
    name: str = "base"

    @abstractmethod
    def list(self) -> list: ...
    @abstractmethod
    def status(self) -> dict: ...
    @abstractmethod
    def select(self, name: str) -> None: ...
    @abstractmethod
    async def enqueue(self, file_path: str, copies: int, paper_size: str | None) -> dict: ...
    @abstractmethod
    def queue(self) -> list: ...
    @abstractmethod
    def cancel(self, job_id: str) -> bool: ...
    def close(self) -> None: pass
