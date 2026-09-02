# Booth Bridge

Local companion agent for **SnapBooth**. It runs on the same laptop that runs the
kiosk and speaks to the physical DSLR + photo printer that a browser cannot
reach.

The web app auto-discovers the bridge at `http://127.0.0.1:8787`. If the bridge
is not running, SnapBooth falls back to browser webcam + mock printing — the
guest journey still works end-to-end.

## Endpoints

    GET  /camera/status
    GET  /camera/liveview        (MJPEG)
    POST /camera/capture         -> { file_path, jpeg_base64 }
    GET  /camera/settings
    POST /camera/settings        { iso, aperture, shutter, wb }

    GET  /printer/list
    GET  /printer/status
    POST /printer/print          { file_path, copies, paper_size }
    GET  /printer/queue
    POST /printer/queue/{id}/cancel

## Run locally

```bash
cd booth-bridge
pip install fastapi uvicorn
python main.py            # binds to 127.0.0.1:8787
```

Windows one-liner: `start.bat`
macOS/Linux one-liner: `./start.sh`

## Real hardware (TODO markers in `main.py`)

- **Camera** — swap the stub with `python-gphoto2` on macOS/Linux, or the
  digiCamControl HTTP API on Windows.
- **Printer** — swap the stub with `pycups` on macOS/Linux, or `win32print` +
  ShellExecute("print", …) on Windows. Print at exact paper size, no scaling,
  no margins.

Target printers: DNP DS-RX1HS / DS620, Citizen CX-02, Canon Selphy CP1500,
Epson dye-sub.
