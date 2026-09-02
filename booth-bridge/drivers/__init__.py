"""Driver factory: pick the best available camera / printer driver for this OS."""
from __future__ import annotations
import logging
import platform
from typing import Optional

from .base import CameraDriver, PrinterDriver

log = logging.getLogger("booth-bridge.drivers")


def select_camera_driver(preferred: Optional[str] = None) -> CameraDriver:
    """Return the best available CameraDriver instance.

    Priority (unless overridden by `preferred`):
        gphoto2 (macOS/Linux) -> digicam (Windows) -> webcam
    """
    system = platform.system()

    def _try(name: str):
        try:
            if name == "gphoto2":
                from .gphoto2_driver import Gphoto2CameraDriver
                d = Gphoto2CameraDriver()
                if d.probe(): return d
            elif name == "digicam":
                from .digicam_driver import DigiCamControlDriver
                d = DigiCamControlDriver()
                if d.probe(): return d
            elif name == "webcam":
                from .webcam_driver import WebcamCameraDriver
                d = WebcamCameraDriver()
                if d.probe(): return d
        except Exception as e:
            log.info("camera driver %s unavailable: %s", name, e)
        return None

    if preferred:
        d = _try(preferred)
        if d: return d
        log.warning("preferred camera driver %s not available, falling back", preferred)

    order = ["gphoto2", "digicam", "webcam"] if system != "Windows" else ["digicam", "gphoto2", "webcam"]
    for name in order:
        d = _try(name)
        if d: return d

    # Final fallback — a stub that reports disconnected. Never raise on startup.
    from .webcam_driver import WebcamCameraDriver
    return WebcamCameraDriver(disabled=True)


def select_printer_driver(preferred: Optional[str] = None) -> PrinterDriver:
    system = platform.system()

    def _try(name: str):
        try:
            if name == "cups":
                from .cups_printer import CupsPrinterDriver
                return CupsPrinterDriver()
            elif name == "windows":
                from .windows_printer import WindowsPrinterDriver
                return WindowsPrinterDriver()
            elif name == "mock":
                from .mock_printer import MockPrinterDriver
                return MockPrinterDriver()
        except Exception as e:
            log.info("printer driver %s unavailable: %s", name, e)
        return None

    if preferred:
        d = _try(preferred)
        if d: return d

    if system == "Windows":
        d = _try("windows")
        if d: return d
    else:
        d = _try("cups")
        if d: return d
    return _try("mock")
