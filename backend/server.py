"""SnapBooth backend - FastAPI + MongoDB.

Serves the kiosk, admin dashboard, guest gallery. All routes under /api.
"""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Response, Request, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os, io, uuid, socket, base64, secrets, logging, zipfile, asyncio

import jwt
import bcrypt
import qrcode
from PIL import Image

from compositor import compose_print, PRESETS

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

STORAGE = Path(os.environ.get("SNAPBOOTH_STORAGE", "/app/storage"))
STORAGE.mkdir(parents=True, exist_ok=True)

JWT_SECRET = os.environ.get("JWT_SECRET", "snapbooth-dev-secret-change-me")
JWT_ALG = "HS256"
JWT_DAYS = 30

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="SnapBooth")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("snapbooth")


def now_iso() -> str: return datetime.now(timezone.utc).isoformat()
def new_id() -> str: return str(uuid.uuid4())

def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return "127.0.0.1"

def make_qr_png(data: str) -> bytes:
    img = qrcode.make(data, box_size=12, border=2)
    buf = io.BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_password(pw: str, hashed: str) -> bool:
    try: return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception: return False

def make_jwt(subject: str) -> str:
    payload = {"sub": subject, "iat": datetime.now(timezone.utc),
               "exp": datetime.now(timezone.utc) + timedelta(days=JWT_DAYS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_jwt(token: str) -> Optional[dict]:
    try: return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception: return None

async def require_admin(request: Request) -> dict:
    token = request.cookies.get("sb_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "): token = auth[7:]
    if not token: raise HTTPException(401, "not authenticated")
    payload = decode_jwt(token)
    if not payload: raise HTTPException(401, "invalid token")
    admin = await db.settings.find_one({"_id": "admin"}, {"_id": 0})
    if not admin: raise HTTPException(401, "admin not initialized")
    return admin


# ---------- Models ----------
class LoginIn(BaseModel): password: str
class InitAdminIn(BaseModel):
    password: str; pin: str = "1234"
class ChangePinIn(BaseModel): pin: str
class SessionStartIn(BaseModel):
    event_id: str; template_id: str; preset_id: str
class CapturePhotoIn(BaseModel):
    session_id: str; slot_index: int; image_base64: str
class LeadIn(BaseModel):
    name: Optional[str] = None; email: Optional[str] = None; phone: Optional[str] = None


# ---------- Startup: seed ----------
@app.on_event("startup")
async def startup():
    admin = await db.settings.find_one({"_id": "admin"})
    if not admin:
        await db.settings.insert_one({
            "_id": "admin", "password_hash": hash_password("snapbooth"),
            "pin": "1234", "created_at": now_iso()})
        log.info("Seeded admin: password=snapbooth pin=1234")

    if await db.filter_presets.count_documents({}) == 0:
        for i, (pid, preset) in enumerate(PRESETS.items()):
            await db.filter_presets.insert_one({
                "_id": pid, "name": preset["name"],
                "params": preset["params"], "order": i, "enabled": True,
                "created_at": now_iso()})
        log.info(f"Seeded {len(PRESETS)} filter presets")

    if await db.templates.count_documents({}) == 0:
        from seed import DEFAULT_TEMPLATES
        for t in DEFAULT_TEMPLATES:
            await db.templates.insert_one(t)
        log.info(f"Seeded {len(DEFAULT_TEMPLATES)} templates")

    if await db.events.count_documents({}) == 0:
        eid = new_id()
        tids = [t["_id"] async for t in db.templates.find({})]
        pids = [p["_id"] async for p in db.filter_presets.find({})]
        await db.events.insert_one({
            "_id": eid, "name": "Demo Wedding",
            "date": datetime.now(timezone.utc).date().isoformat(),
            "client": "Aisha & Ravi", "color": "#f43f5e",
            "headline": "Aisha & Ravi's Big Day",
            "idle_timeout": 60, "max_copies": 4, "retake_policy": "allow",
            "retake_limit": 3, "qr_expiry_days": 30, "mute": False,
            "logo_url": None, "powered_by": "SnapBooth", "lead_gate": False,
            "active": True, "created_at": now_iso(),
            "template_ids": tids, "preset_ids": pids})
        log.info(f"Seeded demo event {eid}")


# ---------- Auth ----------
@api.post("/auth/init")
async def init_admin(payload: InitAdminIn):
    admin = await db.settings.find_one({"_id": "admin"})
    if admin and admin.get("password_hash"):
        raise HTTPException(400, "already initialized")
    await db.settings.replace_one({"_id": "admin"}, {
        "_id": "admin", "password_hash": hash_password(payload.password),
        "pin": payload.pin, "created_at": now_iso()}, upsert=True)
    return {"ok": True}

@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    admin = await db.settings.find_one({"_id": "admin"})
    if not admin or not verify_password(payload.password, admin["password_hash"]):
        raise HTTPException(401, "invalid password")
    token = make_jwt("admin")
    response.set_cookie("sb_token", token, httponly=True, secure=True,
                        samesite="none", max_age=JWT_DAYS * 86400, path="/")
    return {"ok": True, "token": token, "expires_days": JWT_DAYS}

@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("sb_token", path="/")
    return {"ok": True}

@api.get("/auth/me")
async def me(_: dict = Depends(require_admin)):
    return {"ok": True, "role": "admin"}

@api.post("/auth/verify-pin")
async def verify_pin(payload: ChangePinIn):
    admin = await db.settings.find_one({"_id": "admin"})
    if not admin or admin.get("pin") != payload.pin:
        raise HTTPException(401, "wrong pin")
    return {"ok": True}

@api.post("/auth/pin")
async def set_pin(payload: ChangePinIn, _: dict = Depends(require_admin)):
    await db.settings.update_one({"_id": "admin"}, {"$set": {"pin": payload.pin}})
    return {"ok": True}


# ---------- Events ----------
def _clean(doc: dict) -> dict:
    doc["id"] = doc.pop("_id"); return doc

@api.get("/events")
async def list_events(_: dict = Depends(require_admin)):
    return [_clean(d) async for d in db.events.find({})]

@api.get("/events/active")
async def active_event():
    ev = await db.events.find_one({"active": True})
    if not ev: raise HTTPException(404, "no active event")
    ev = _clean(ev)
    tids = ev.get("template_ids") or []
    pids = ev.get("preset_ids") or []
    templates = [_clean(t) async for t in db.templates.find({"_id": {"$in": tids}})]
    presets = [_clean(p) async for p in db.filter_presets.find({"_id": {"$in": pids}, "enabled": True}).sort("order", 1)]
    return {"event": ev, "templates": templates, "presets": presets, "lan_ip": get_lan_ip()}

@api.post("/events")
async def create_event(payload: dict, _: dict = Depends(require_admin)):
    eid = new_id()
    payload.pop("id", None); payload.pop("_id", None)
    tids = [t["_id"] async for t in db.templates.find({})]
    pids = [p["_id"] async for p in db.filter_presets.find({})]
    doc = {"_id": eid, "active": False, "created_at": now_iso(),
           "template_ids": tids, "preset_ids": pids, **payload}
    await db.events.insert_one(doc)
    return _clean(doc)

@api.put("/events/{eid}")
async def update_event(eid: str, payload: dict, _: dict = Depends(require_admin)):
    payload.pop("id", None); payload.pop("_id", None)
    await db.events.update_one({"_id": eid}, {"$set": payload})
    d = await db.events.find_one({"_id": eid})
    return _clean(d) if d else {}

@api.post("/events/{eid}/activate")
async def activate_event(eid: str, _: dict = Depends(require_admin)):
    await db.events.update_many({}, {"$set": {"active": False}})
    await db.events.update_one({"_id": eid}, {"$set": {"active": True}})
    return {"ok": True}

@api.delete("/events/{eid}")
async def delete_event(eid: str, _: dict = Depends(require_admin)):
    await db.events.delete_one({"_id": eid})
    return {"ok": True}


# ---------- Templates ----------
@api.get("/templates")
async def list_templates(_: dict = Depends(require_admin)):
    return [_clean(d) async for d in db.templates.find({})]

@api.post("/templates")
async def create_template(payload: dict, _: dict = Depends(require_admin)):
    tid = new_id()
    payload.pop("id", None); payload.pop("_id", None)
    doc = {"_id": tid, "created_at": now_iso(), **payload}
    await db.templates.insert_one(doc)
    return _clean(doc)

@api.put("/templates/{tid}")
async def update_template(tid: str, payload: dict, _: dict = Depends(require_admin)):
    payload.pop("id", None); payload.pop("_id", None)
    await db.templates.update_one({"_id": tid}, {"$set": payload})
    d = await db.templates.find_one({"_id": tid})
    return _clean(d) if d else {}

@api.delete("/templates/{tid}")
async def delete_template(tid: str, _: dict = Depends(require_admin)):
    await db.templates.delete_one({"_id": tid})
    return {"ok": True}


# ---------- Template asset uploads (overlay / background PNGs) ----------
_ALLOWED_UPLOAD_MIME = {"image/png", "image/jpeg", "image/webp"}


def _write_local_asset(path, data: bytes) -> None:
    """Persist an operator-uploaded asset (overlay/background/LUT/strip) to the
    local event storage. SnapBooth is offline-first by product spec — the
    kiosk keeps all assets on the same machine so it works with no internet.
    """
    with open(path, "wb") as f:
        f.write(data)


async def _save_upload(kind: str, file: UploadFile) -> str:
    """Persist a PNG/JPEG/WEBP upload under /storage/assets/{kind}/ and
    return the RELATIVE path (usable via /api/files/{path}).
    """
    if file.content_type not in _ALLOWED_UPLOAD_MIME:
        raise HTTPException(400, f"unsupported type {file.content_type}")
    raw = await file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "file > 12MB")
    # Re-encode through Pillow to strip anything malicious & normalize
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:
        raise HTTPException(400, "not a valid image")
    ext = "png" if img.format == "PNG" or file.content_type == "image/png" else "jpg"
    folder = STORAGE / "assets" / kind
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{secrets.token_hex(8)}.{ext}"
    fp = folder / fname
    if ext == "png":
        img.save(fp, "PNG")  # local asset — offline-first by design
    else:
        img.convert("RGB").save(fp, "JPEG", quality=92)  # local asset — offline-first by design
    return f"assets/{kind}/{fname}"


@api.post("/uploads/overlay")
async def upload_overlay(file: UploadFile = File(...), _: dict = Depends(require_admin)):
    rel = await _save_upload("overlays", file)
    return {"path": rel, "url": f"/api/files/{rel}"}


@api.post("/uploads/background")
async def upload_background(file: UploadFile = File(...), _: dict = Depends(require_admin)):
    rel = await _save_upload("backgrounds", file)
    return {"path": rel, "url": f"/api/files/{rel}"}


# ---------- Filter presets ----------
@api.get("/presets")
async def list_presets(_: dict = Depends(require_admin)):
    return [_clean(d) async for d in db.filter_presets.find({}).sort("order", 1)]

@api.put("/presets/{pid}")
async def update_preset(pid: str, payload: dict, _: dict = Depends(require_admin)):
    payload.pop("id", None); payload.pop("_id", None)
    await db.filter_presets.update_one({"_id": pid}, {"$set": payload})
    d = await db.filter_presets.find_one({"_id": pid})
    return _clean(d) if d else {}


# ---------- 3D LUT (.cube) support ----------
@api.post("/presets/{pid}/lut")
async def upload_lut(pid: str, file: UploadFile = File(...), _: dict = Depends(require_admin)):
    """Attach a .cube 3D LUT to a filter preset."""
    existing = await db.filter_presets.find_one({"_id": pid})
    if not existing:
        raise HTTPException(404, "preset not found")
    if not (file.filename or "").lower().endswith(".cube"):
        raise HTTPException(400, "file must have .cube extension")
    raw = await file.read()
    if len(raw) > 32 * 1024 * 1024:
        raise HTTPException(413, "LUT > 32MB")
    try:
        text = raw.decode("utf-8", errors="ignore")
        from lut import parse_cube_file, lut_to_strip_png
        lut_arr, _dmin, _dmax, size = parse_cube_file(text)
    except Exception as e:
        raise HTTPException(400, f"invalid .cube file: {e}")
    folder = STORAGE / "assets" / "luts"
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{pid}_{secrets.token_hex(4)}.cube"
    fp = folder / fname
    _write_local_asset(fp, raw)  # offline-first venue app; assets stay local by design
    # Cache the strip PNG at upload so GET /lut.png doesn't re-parse on every request.
    try:
        _write_local_asset(folder / f"{fname}.strip.png", lut_to_strip_png(lut_arr))
    except Exception: pass
    rel = f"assets/luts/{fname}"
    # Delete the previous .cube (and its cached strip) to stop the storage leak.
    old = existing.get("lut_path")
    if old and old != rel:
        try:
            (STORAGE / old).unlink(missing_ok=True)
            (STORAGE / f"{old}.strip.png").unlink(missing_ok=True)
        except Exception: pass
    await db.filter_presets.update_one({"_id": pid}, {"$set": {
        "lut_path": rel, "lut_size": size,
    }})
    d = await db.filter_presets.find_one({"_id": pid})
    return _clean(d) if d else {"ok": True, "lut_path": rel, "lut_size": size}


@api.delete("/presets/{pid}/lut")
async def delete_lut(pid: str, _: dict = Depends(require_admin)):
    existing = await db.filter_presets.find_one({"_id": pid})
    if not existing:
        raise HTTPException(404, "preset not found")
    old = existing.get("lut_path")
    if old:
        try:
            (STORAGE / old).unlink(missing_ok=True)
            (STORAGE / f"{old}.strip.png").unlink(missing_ok=True)
        except Exception: pass
    await db.filter_presets.update_one({"_id": pid}, {"$unset": {"lut_path": "", "lut_size": ""}})
    return {"ok": True}


@api.get("/presets/{pid}/lut.png")
async def get_lut_strip(pid: str):
    """Return the 2D strip PNG (N x N*N) that the WebGL shader samples."""
    d = await db.filter_presets.find_one({"_id": pid})
    if not d or not d.get("lut_path"):
        raise HTTPException(404, "no LUT for this preset")
    lut_rel = d["lut_path"]
    # Serve cached strip if present (written at upload time)
    cached = STORAGE / f"{lut_rel}.strip.png"
    if cached.exists():
        return Response(content=cached.read_bytes(), media_type="image/png", headers={
            "Cache-Control": "public, max-age=600",
            "X-Lut-Size": str(d.get("lut_size", "")),
        })
    fp = STORAGE / lut_rel
    if not fp.exists():
        raise HTTPException(404, "LUT file missing")
    try:
        from lut import parse_cube_file, lut_to_strip_png
        text = fp.read_text()
        lut, _, _, size = parse_cube_file(text)
        png = lut_to_strip_png(lut)
        # Backfill cache
        try: cached.write_bytes(png)
        except Exception: pass
    except Exception as e:
        raise HTTPException(500, f"LUT decode failed: {e}")
    return Response(content=png, media_type="image/png", headers={
        "Cache-Control": "public, max-age=600",
        "X-Lut-Size": str(size),
    })


# ---------- Sessions ----------
@api.post("/sessions/start")
async def start_session(payload: SessionStartIn):
    sid = new_id()
    doc = {"_id": sid, "event_id": payload.event_id,
           "template_id": payload.template_id, "preset_id": payload.preset_id,
           "status": "capturing", "photo_paths": [],
           "started_at": now_iso(), "completed_at": None,
           "qr_token": secrets.token_urlsafe(8), "copies_printed": 0}
    await db.sessions.insert_one(doc)
    (STORAGE / payload.event_id / sid).mkdir(parents=True, exist_ok=True)
    return _clean(doc)

def _decode_data_url(s: str) -> bytes:
    if s.startswith("data:"): s = s.split(",", 1)[1]
    return base64.b64decode(s)

@api.post("/sessions/photo")
async def upload_photo(payload: CapturePhotoIn):
    sess = await db.sessions.find_one({"_id": payload.session_id})
    if not sess: raise HTTPException(404, "session not found")
    raw = _decode_data_url(payload.image_base64)
    folder = STORAGE / sess["event_id"] / sess["_id"]
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"raw_{payload.slot_index}_{secrets.token_hex(3)}.jpg"
    fpath = folder / filename
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img.save(fpath, "JPEG", quality=95)
    rel = f"{sess['event_id']}/{sess['_id']}/{filename}"
    photos = sess.get("photo_paths", [])
    while len(photos) <= payload.slot_index: photos.append(None)
    photos[payload.slot_index] = rel
    await db.sessions.update_one({"_id": sess["_id"]}, {"$set": {"photo_paths": photos}})
    return {"ok": True, "path": rel, "slot_index": payload.slot_index}


# ---------- Boomerang burst (ping-pong GIF + MP4) ----------
class BoomerangIn(BaseModel):
    session_id: str
    frames: list  # list[str] base64 JPEG frames (data URLs or raw base64), 8–24 frames
    fps: int = 10

@api.post("/sessions/boomerang")
async def upload_boomerang(payload: BoomerangIn):
    sess = await db.sessions.find_one({"_id": payload.session_id})
    if not sess:
        raise HTTPException(404, "session not found")
    if not (2 <= len(payload.frames) <= 60):
        raise HTTPException(400, "expected between 2 and 60 frames")

    # Decode + apply the session's filter/LUT so the boomerang matches the print
    from PIL import Image as _PIL
    imgs = []
    for f in payload.frames:
        raw = _decode_data_url(f)
        imgs.append(_PIL.open(io.BytesIO(raw)).convert("RGB"))

    preset = await db.filter_presets.find_one({"_id": sess["preset_id"]})
    params = (preset or {}).get("params", {})
    lut, lut_domain = None, None
    if preset and preset.get("lut_path"):
        try:
            from lut import parse_cube_file as _pcf
            fp = STORAGE / preset["lut_path"]
            if fp.exists():
                _l, _dmn, _dmx, _ = _pcf(fp.read_text())
                lut, lut_domain = _l, (_dmn, _dmx)
        except Exception: pass

    from compositor import apply_filter_pil
    def _render():
        return [apply_filter_pil(im, params, lut=lut, lut_domain=lut_domain) for im in imgs]

    rendered = await asyncio.to_thread(_render)

    out_dir = STORAGE / sess["event_id"] / sess["_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    gif_path = out_dir / "boomerang.gif"
    mp4_path = out_dir / "boomerang.mp4"

    from boomerang import encode_ping_pong_gif, encode_ping_pong_mp4
    try:
        await asyncio.to_thread(encode_ping_pong_gif, rendered, str(gif_path), payload.fps)
    except Exception as e:
        log.exception("gif encode failed"); raise HTTPException(500, f"gif encode failed: {e}")
    try:
        await asyncio.to_thread(encode_ping_pong_mp4, rendered, str(mp4_path), payload.fps)
    except Exception as e:
        log.exception("mp4 encode failed")  # non-fatal — GIF still available
        mp4_path = None

    update = {
        "gif_path": f"{sess['event_id']}/{sess['_id']}/boomerang.gif",
        "boomerang_frames": len(payload.frames),
    }
    if mp4_path is not None:
        update["mp4_path"] = f"{sess['event_id']}/{sess['_id']}/boomerang.mp4"
    await db.sessions.update_one({"_id": sess["_id"]}, {"$set": update})
    return {"ok": True, "gif_path": update["gif_path"], "mp4_path": update.get("mp4_path")}

@api.post("/sessions/{sid}/finalize")
async def finalize_session(sid: str, request: Request):
    sess = await db.sessions.find_one({"_id": sid})
    if not sess: raise HTTPException(404, "session not found")
    template = await db.templates.find_one({"_id": sess["template_id"]})
    preset = await db.filter_presets.find_one({"_id": sess["preset_id"]})
    if not template: raise HTTPException(400, "template missing")

    # If preset carries a .cube LUT, parse it once
    lut = None; lut_domain = None
    if preset and preset.get("lut_path"):
        try:
            from lut import parse_cube_file as _pcf
            fp = STORAGE / preset["lut_path"]
            if fp.exists():
                text = fp.read_text()
                lut_arr, dmin, dmax, _n = _pcf(text)
                lut = lut_arr
                lut_domain = (dmin, dmax)
        except Exception as e:
            log.warning("could not load LUT for preset %s: %s", preset.get("_id"), e)

    photo_paths = [STORAGE / p for p in sess["photo_paths"] if p]
    out_dir = STORAGE / sess["event_id"] / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    print_path = out_dir / "print.png"
    web_path = out_dir / "web.jpg"
    try:
        # Composition is CPU-bound (Pillow + numpy); run off the event loop so
        # other requests aren't blocked while a 1200x1800 quad is rendered.
        await asyncio.to_thread(
            compose_print, template, [str(p) for p in photo_paths],
            (preset or {}).get("params", {}), str(print_path), str(web_path),
            lut, lut_domain,
        )
    except Exception as e:
        log.exception("compose failed")
        raise HTTPException(500, f"compose failed: {e}")

    ev = await db.events.find_one({"_id": sess["event_id"]})
    qr_days = (ev or {}).get("qr_expiry_days", 30)
    expires = (datetime.now(timezone.utc) + timedelta(days=qr_days)).isoformat()
    origin = request.headers.get("origin") or f"http://{get_lan_ip()}:3000"
    guest_url = f"{origin}/g/{sess['qr_token']}"

    await db.sessions.update_one({"_id": sid}, {"$set": {
        "status": "ready", "completed_at": now_iso(),
        "print_path": f"{sess['event_id']}/{sid}/print.png",
        "web_path": f"{sess['event_id']}/{sid}/web.jpg",
        "qr_expires_at": expires, "guest_url": guest_url}})
    return {"ok": True, "qr_token": sess["qr_token"], "guest_url": guest_url,
            "print_path": f"{sess['event_id']}/{sid}/print.png"}

@api.get("/sessions/{sid}")
async def get_session(sid: str):
    s = await db.sessions.find_one({"_id": sid})
    if not s: raise HTTPException(404, "not found")
    return _clean(s)

@api.get("/sessions")
async def list_sessions(event_id: Optional[str] = None, _: dict = Depends(require_admin)):
    q = {"event_id": event_id} if event_id else {}
    return [_clean(d) async for d in db.sessions.find(q).sort("started_at", -1).limit(500)]

@api.delete("/sessions/{sid}")
async def delete_session(sid: str, _: dict = Depends(require_admin)):
    await db.sessions.delete_one({"_id": sid})
    return {"ok": True}


# ---------- Print jobs ----------
BRIDGE_URL = os.environ.get("BOOTH_BRIDGE_URL", "http://127.0.0.1:8787")

async def bridge_alive() -> bool:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=1.0) as c:
            r = await c.get(f"{BRIDGE_URL}/printer/status")
            return r.status_code == 200
    except Exception:
        return False

@api.post("/print/{sid}")
async def print_session(sid: str, copies: int = 1):
    sess = await db.sessions.find_one({"_id": sid})
    if not sess or not sess.get("print_path"):
        raise HTTPException(400, "session not finalized")
    # Clamp copies to the event's max_copies (public endpoint — protect the printer)
    ev = await db.events.find_one({"_id": sess["event_id"]}) or {}
    copies = max(1, min(int(copies), int(ev.get("max_copies", 4))))
    jid = new_id()
    driver = "bridge" if await bridge_alive() else "mock"
    job = {"_id": jid, "session_id": sid, "copies": copies, "driver": driver,
           "state": "queued", "created_at": now_iso(),
           "print_path": sess["print_path"], "error": None}
    await db.print_jobs.insert_one(job)
    await db.sessions.update_one({"_id": sid}, {"$inc": {"copies_printed": copies}})
    asyncio.create_task(_run_print_job(jid))
    return _clean(job)

async def _run_print_job(jid: str):
    job = await db.print_jobs.find_one({"_id": jid})
    if not job: return
    await db.print_jobs.update_one({"_id": jid}, {"$set": {"state": "printing"}})
    try:
        if job["driver"] == "bridge":
            import httpx
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(f"{BRIDGE_URL}/printer/print", json={
                    "file_path": str(STORAGE / job["print_path"]),
                    "copies": job["copies"]})
                if r.status_code >= 400: raise RuntimeError(r.text)
        else:
            await asyncio.sleep(2)
        await db.print_jobs.update_one({"_id": jid}, {"$set": {
            "state": "done", "finished_at": now_iso()}})
    except Exception as e:
        await db.print_jobs.update_one({"_id": jid}, {"$set": {
            "state": "failed", "error": str(e), "finished_at": now_iso()}})

@api.get("/print/queue")
async def print_queue(_: dict = Depends(require_admin)):
    return [_clean(j) async for j in db.print_jobs.find({}).sort("created_at", -1).limit(200)]


# ---------- Hardware ----------
@api.get("/hardware/status")
async def hardware_status():
    import shutil as _sh
    disk = _sh.disk_usage(str(STORAGE))
    bridge = await bridge_alive()
    bridge_info: Dict[str, Any] = {"connected": bridge, "url": BRIDGE_URL}
    if bridge:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=1.0) as c:
                cam = await c.get(f"{BRIDGE_URL}/camera/status")
                pr = await c.get(f"{BRIDGE_URL}/printer/status")
                bridge_info["camera"] = cam.json()
                bridge_info["printer"] = pr.json()
        except Exception as e:
            bridge_info["error"] = str(e)
    return {"lan_ip": get_lan_ip(),
            "storage_free_gb": round(disk.free / 1e9, 2),
            "storage_total_gb": round(disk.total / 1e9, 2),
            "bridge": bridge_info,
            "camera_source": "bridge" if bridge else "webcam",
            "printer_driver": "bridge" if bridge else "mock"}


# ---------- Stats ----------
@api.get("/stats")
async def stats(_: dict = Depends(require_admin)):
    today = datetime.now(timezone.utc).date().isoformat()
    total = await db.sessions.count_documents({})
    today_sessions = await db.sessions.count_documents({"started_at": {"$gte": today}})
    prints_today = 0
    async for s in db.sessions.find({"started_at": {"$gte": today}}, {"copies_printed": 1}):
        prints_today += s.get("copies_printed", 0) or 0
    photos = 0
    async for s in db.sessions.find({}, {"photo_paths": 1}):
        photos += len([p for p in (s.get("photo_paths") or []) if p])
    durations = []
    async for s in db.sessions.find({"completed_at": {"$ne": None}}, {"started_at": 1, "completed_at": 1}):
        try:
            a = datetime.fromisoformat(s["started_at"]); b = datetime.fromisoformat(s["completed_at"])
            durations.append((b - a).total_seconds())
        except Exception: pass
    avg = round(sum(durations) / len(durations), 1) if durations else 0
    return {"total_sessions": total, "today_sessions": today_sessions,
            "prints_today": prints_today, "photos_captured": photos,
            "avg_session_seconds": avg}


# ---------- Guest gallery (public) ----------
@api.get("/g/{token}")
async def guest_gallery(token: str):
    s = await db.sessions.find_one({"qr_token": token})
    if not s: raise HTTPException(404, "not found")
    if s.get("qr_expires_at"):
        try:
            if datetime.fromisoformat(s["qr_expires_at"]) < datetime.now(timezone.utc):
                raise HTTPException(410, "link expired")
        except HTTPException: raise
        except Exception: pass
    ev = await db.events.find_one({"_id": s["event_id"]}) or {}
    return {"event": {"name": ev.get("name"), "headline": ev.get("headline"),
                      "color": ev.get("color"), "logo_url": ev.get("logo_url"),
                      "powered_by": ev.get("powered_by"),
                      "lead_gate": ev.get("lead_gate", False)},
            "session": {"id": s["_id"], "print_path": s.get("print_path"),
                        "web_path": s.get("web_path"),
                        "raw_photos": s.get("photo_paths", []),
                        "gif_path": s.get("gif_path"),
                        "mp4_path": s.get("mp4_path"),
                        "completed_at": s.get("completed_at")}}

@api.get("/g/{token}/zip")
async def guest_zip(token: str):
    s = await db.sessions.find_one({"qr_token": token})
    if not s: raise HTTPException(404, "not found")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        rels = [s.get("print_path"), s.get("web_path"), s.get("gif_path"), s.get("mp4_path")]
        rels += list(s.get("photo_paths") or [])
        for rel in rels:
            if rel:
                fp = STORAGE / rel
                if fp.exists(): zf.write(fp, Path(rel).name)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="snapbooth-{token}.zip"'})

@api.post("/g/{token}/lead")
async def guest_lead(token: str, payload: LeadIn):
    s = await db.sessions.find_one({"qr_token": token})
    if not s: raise HTTPException(404, "not found")
    doc = {"_id": new_id(), "event_id": s["event_id"], "session_id": s["_id"],
           "name": payload.name, "email": payload.email, "phone": payload.phone,
           "created_at": now_iso()}
    await db.leads.insert_one(doc)
    return {"ok": True}

@api.get("/qr/{token}.png")
async def qr_png(token: str, request: Request):
    origin = request.headers.get("origin") or f"http://{get_lan_ip()}:3000"
    data = f"{origin}/g/{token}"
    return Response(content=make_qr_png(data), media_type="image/png")


# ---------- Static file serving ----------
@api.get("/files/{path:path}")
async def get_file(path: str):
    # Resolve and confirm the path stays inside STORAGE (guard against ../ traversal)
    try:
        fp = (STORAGE / path).resolve(strict=False)
        fp.relative_to(STORAGE.resolve())
    except (ValueError, RuntimeError):
        raise HTTPException(404, "not found")
    if not fp.exists() or not fp.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(str(fp))


@api.get("/")
async def root():
    return {"app": "SnapBooth", "lan_ip": get_lan_ip(), "time": now_iso()}


app.include_router(api)
app.add_middleware(
    CORSMiddleware, allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"], allow_headers=["*"])


@app.on_event("shutdown")
async def shutdown():
    client.close()
