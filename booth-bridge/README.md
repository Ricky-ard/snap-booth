# Booth Bridge — SnapBooth companion agent

Real cameras (DSLR / mirrorless) and real photo printers cannot be reached
from a web browser. Booth Bridge is a tiny local agent that runs alongside
the SnapBooth kiosk on the same laptop and exposes them over HTTP on
`http://127.0.0.1:8787`.

If the bridge is not running, SnapBooth automatically falls back to the
browser webcam + a mock printer driver — the guest journey still works
end-to-end. Start the bridge when you're ready to plug in the real hardware.

---

## One-click start

**macOS**
```bash
./start.command       # or double-click Finder → Booth Bridge → start.command
```

**Linux**
```bash
./start.sh
```

**Windows**
```
start.bat             # or double-click in Explorer
```

The first run installs dependencies into `.venv/`. Subsequent runs launch in
about a second.

---

## What talks to what

```
   ┌────────────────────────┐        ┌──────────────────────────┐
   │  SnapBooth backend     │        │  Kiosk / Admin browser   │
   │  (FastAPI @ :8001)     │◀──────▶│  (React @ :3000)         │
   └────────────┬───────────┘        └──────────────┬───────────┘
                │                                    │
                │           HTTP + MJPEG              │
                ▼                                    ▼
              ┌──────────────────────────────────────────┐
              │       Booth Bridge  @ 127.0.0.1:8787     │
              ├──────────────┬───────────────────────────┤
              │  Camera      │  gphoto2  |  digiCamCtrl  │
              │  driver      │           |  webcam       │
              ├──────────────┼───────────────────────────┤
              │  Printer     │  CUPS (mac/Linux)         │
              │  driver      │  win32print (Windows)     │
              │              │  mock (always)            │
              └──────────────┴───────────────────────────┘
```

---

## Camera drivers

Auto-selected in this order (override with `--camera` or `BRIDGE_CAMERA`):

### gphoto2 — macOS + Linux

Works with virtually every Canon / Nikon / Sony / Fuji / Panasonic body.

```bash
# macOS
brew install libgphoto2

# Debian / Ubuntu
sudo apt install libgphoto2-dev

# Python bindings
pip install gphoto2
```

Plug the camera in via USB, put it in **PC / PTP mode**, unmount any
Files/Photos app that grabbed the device, then start the bridge. Live view
and shutter work out of the box on all mainstream Canon / Nikon DSLRs.

### digiCamControl — Windows

1. Install digiCamControl from <https://digicamcontrol.com>.
2. Open it, go to **File → Settings → Webserver**, tick **Enable web server**,
   port `5513`.
3. Plug the camera in, verify it appears in the digiCamControl toolbar.
4. Start Booth Bridge — it will speak to `http://127.0.0.1:5513`.

If digiCamControl runs on a different port or host, set the environment
variable `DIGICAM_URL=http://127.0.0.1:5513`.

### webcam — cross-platform fallback

Uses OpenCV against the default camera (index 0). Requires
`pip install opencv-python`. Handy for demos, rehearsals, and machines
without a DSLR attached.

Force a driver:
```bash
python main.py --camera gphoto2       # or digicam / webcam
```

---

## Printer drivers

Auto-selected per OS (override with `--printer` or `BRIDGE_PRINTER`):

### CUPS — macOS + Linux

Uses the `lp` command that ships with every Mac / desktop Linux. Prints
silently at the paper size you specify, with **no OS dialog and no scaling**:

```
lp -d "DNP_DS-RX1HS" -n 1 -o media=Custom.101.6x152.4mm \
      -o fit-to-page=false -o position=center /path/print.png
```

Install `pycups` (`pip install pycups`) if you want richer status queries.

### Windows spooler

Uses `pywin32` (`pip install pywin32`) → `ShellExecute("printto", …)`. Set
the printer's paper size + **borderless** in Windows printer preferences once
and every job comes out at exact paper dimensions with no scaling.

### mock

Always present. Logs jobs to memory, marks them `done` after two seconds,
decrements a virtual media counter. This is what SnapBooth talks to when no
real printer is connected.

Target printers we've verified live: **DNP DS-RX1HS, DNP DS620, Citizen
CX-02, Canon Selphy CP1500, Epson SureLab dye-sub.**

---

## API

```
GET  /health                    { ok, camera_driver, printer_driver, ... }

GET  /camera/status             { connected, model, battery, mode, driver }
GET  /camera/liveview           multipart/x-mixed-replace MJPEG stream
POST /camera/capture            { file_path, jpeg_base64 }
GET  /camera/settings           { iso, aperture, shutter, wb }
POST /camera/settings           { iso, aperture, shutter, wb }

GET  /printer/list              { system, printers: [name, ...] }
GET  /printer/status            { name, state, jobs_pending, media_remaining }
POST /printer/select            { name }
POST /printer/print             { file_path, copies, paper_size }  -> job
GET  /printer/queue             [ job, ... ]
POST /printer/queue/{id}/cancel { ok }
```

Paper sizes accepted by `POST /printer/print`:
`2x6`, `2x6_double`, `4x6`, `6x8`, `square` (mapped to exact mm dimensions
inside the driver).

---

## Troubleshooting

- **`gphoto2 no camera` at startup** — another app (Photos, Image Capture,
  Preview, Files) already grabbed the USB device. Quit it, or run
  `killall PTPCamera` on macOS.
- **digiCamControl connects but capture fails** — make sure the camera is set
  to **manual focus** or has autofocus lock, and that the memory card is not
  full. digiCamControl surfaces the exact error in its main window.
- **Windows prints are cropped** — the Windows spooler respects the printer's
  paper preferences. Open **Devices & Printers → your printer → Printing
  preferences** and set the exact paper size + borderless mode once.
- **CUPS output is scaled** — always pass `-o fit-to-page=false` (Booth Bridge
  does this) and confirm the printer's default media matches the print file.

---

## Files

    booth-bridge/
    ├── main.py                 FastAPI entrypoint on 127.0.0.1:8787
    ├── requirements.txt
    ├── start.sh                Linux one-click
    ├── start.command           macOS one-click (double-click in Finder)
    ├── start.bat               Windows one-click
    └── drivers/
        ├── base.py             CameraDriver + PrinterDriver ABCs
        ├── gphoto2_driver.py   DSLR via libgphoto2  (macOS / Linux)
        ├── digicam_driver.py   DSLR via digiCamControl HTTP  (Windows)
        ├── webcam_driver.py    OpenCV fallback  (all OSes)
        ├── cups_printer.py     Silent print via `lp`  (macOS / Linux)
        ├── windows_printer.py  Silent print via win32print  (Windows)
        └── mock_printer.py     In-memory driver used when nothing else is available
