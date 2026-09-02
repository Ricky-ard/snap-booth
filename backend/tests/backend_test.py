"""SnapBooth backend API regression tests.

Covers: health, seed data, auth (JWT cookie + Bearer + PIN), events/templates/presets CRUD,
full kiosk session flow, print composition dimensions/DPI, print jobs, hardware status,
stats, public guest gallery, file serving, retake replacement.
"""
import io
import time

import pytest
import requests
from PIL import Image

from conftest import API, ADMIN_PASSWORD, KIOSK_PIN, make_jpeg_b64


# ---------------- Health / seed ----------------
class TestHealth:
    def test_root(self, anon):
        r = anon.get(f"{API}/")
        assert r.status_code == 200
        d = r.json()
        assert d["app"] == "SnapBooth"
        assert isinstance(d["lan_ip"], str) and d["lan_ip"]

    def test_active_event_seeded(self, anon):
        r = anon.get(f"{API}/events/active")
        assert r.status_code == 200
        d = r.json()
        assert d["event"]["active"] is True
        assert "id" in d["event"] and "_id" not in d["event"]
        assert len(d["templates"]) == 5, [t["id"] for t in d["templates"]]
        ids = {t["id"] for t in d["templates"]}
        assert ids == {"tpl-classic-strip", "tpl-strip-double", "tpl-4x6-single",
                       "tpl-4x6-quad", "tpl-square-social"}
        assert len(d["presets"]) == 12
        for p in d["presets"]:
            assert isinstance(p["params"], dict) and "brightness" in p["params"]
        assert d["lan_ip"]


# ---------------- Auth ----------------
class TestAuth:
    def test_login_success_sets_cookie(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"password": ADMIN_PASSWORD})
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True and isinstance(d["token"], str) and len(d["token"]) > 20
        assert d["expires_days"] == 30
        assert "sb_token" in s.cookies.get_dict(), s.cookies.get_dict()
        # cookie-only auth works
        me = s.get(f"{API}/auth/me")
        assert me.status_code == 200 and me.json()["role"] == "admin"

    def test_login_wrong_password(self, anon):
        r = anon.post(f"{API}/auth/login", json={"password": "wrongpass"})
        assert r.status_code == 401

    def test_me_with_bearer_only(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200 and r.json()["ok"] is True

    def test_me_unauthenticated(self, anon):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_invalid_token(self):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": "Bearer garbage.token.xyz"})
        assert r.status_code == 401

    def test_verify_pin_ok(self, anon):
        r = requests.post(f"{API}/auth/verify-pin", json={"pin": KIOSK_PIN})
        assert r.status_code == 200 and r.json()["ok"] is True

    def test_verify_pin_wrong(self):
        r = requests.post(f"{API}/auth/verify-pin", json={"pin": "0000"})
        assert r.status_code == 401

    def test_auth_init_already_initialized(self):
        r = requests.post(f"{API}/auth/init", json={"password": "hacker", "pin": "9999"})
        assert r.status_code == 400


# ---------------- Protected endpoints require auth ----------------
@pytest.mark.parametrize("method,path", [
    ("get", "/events"), ("post", "/events"), ("get", "/templates"),
    ("post", "/templates"), ("get", "/presets"), ("get", "/stats"),
    ("get", "/print/queue"), ("get", "/sessions"),
])
def test_admin_endpoints_require_auth(method, path):
    r = getattr(requests, method)(f"{API}{path}", json={})
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}"


# ---------------- Events CRUD ----------------
class TestEvents:
    created = []

    def test_list_events(self, admin_client):
        r = admin_client.get(f"{API}/events")
        assert r.status_code == 200 and isinstance(r.json(), list)
        assert all("_id" not in e for e in r.json())

    def test_create_update_activate_delete(self, admin_client):
        payload = {"name": "TEST_Event", "client": "TEST_Client", "color": "#123456",
                   "headline": "TEST headline", "qr_expiry_days": 7}
        r = admin_client.post(f"{API}/events", json=payload)
        assert r.status_code == 200, r.text[:300]
        ev = r.json()
        eid = ev["id"]
        TestEvents.created.append(eid)
        assert ev["name"] == "TEST_Event" and ev["active"] is False
        assert len(ev["template_ids"]) >= 5

        # update
        up = admin_client.put(f"{API}/events/{eid}", json={"name": "TEST_Event_Updated"})
        assert up.status_code == 200 and up.json()["name"] == "TEST_Event_Updated"
        lst = admin_client.get(f"{API}/events").json()
        assert any(e["id"] == eid and e["name"] == "TEST_Event_Updated" for e in lst)

        # remember previously active event to restore
        prev_active = next((e["id"] for e in lst if e.get("active")), None)

        act = admin_client.post(f"{API}/events/{eid}/activate")
        assert act.status_code == 200
        lst2 = admin_client.get(f"{API}/events").json()
        actives = [e["id"] for e in lst2 if e.get("active")]
        assert actives == [eid], actives

        # restore
        if prev_active:
            assert admin_client.post(f"{API}/events/{prev_active}/activate").status_code == 200

        d = admin_client.delete(f"{API}/events/{eid}")
        assert d.status_code == 200
        lst3 = admin_client.get(f"{API}/events").json()
        assert all(e["id"] != eid for e in lst3)
        TestEvents.created.remove(eid)

    @classmethod
    def teardown_class(cls):
        pass


# ---------------- Templates CRUD ----------------
class TestTemplates:
    def test_list_seeded(self, admin_client):
        r = admin_client.get(f"{API}/templates")
        assert r.status_code == 200
        ids = {t["id"] for t in r.json()}
        for t in ["tpl-classic-strip", "tpl-strip-double", "tpl-4x6-single",
                  "tpl-4x6-quad", "tpl-square-social"]:
            assert t in ids

    def test_crud(self, admin_client):
        payload = {"name": "TEST_Template", "paper": {"size": "4x6", "dpi": 300},
                   "canvas": {"width_px": 1200, "height_px": 1800}, "photo_count": 1,
                   "background_color": "#000000",
                   "photo_slots": [{"x": 0, "y": 0, "width": 1200, "height": 1800}]}
        r = admin_client.post(f"{API}/templates", json=payload)
        assert r.status_code == 200
        tid = r.json()["id"]
        assert r.json()["name"] == "TEST_Template"

        up = admin_client.put(f"{API}/templates/{tid}", json={"name": "TEST_Template2"})
        assert up.status_code == 200 and up.json()["name"] == "TEST_Template2"

        got = [t for t in admin_client.get(f"{API}/templates").json() if t["id"] == tid]
        assert got and got[0]["name"] == "TEST_Template2"

        assert admin_client.delete(f"{API}/templates/{tid}").status_code == 200
        assert all(t["id"] != tid for t in admin_client.get(f"{API}/templates").json())


# ---------------- Presets ----------------
class TestPresets:
    def test_list_12_enabled(self, admin_client):
        r = admin_client.get(f"{API}/presets")
        assert r.status_code == 200
        ps = r.json()
        assert len(ps) == 12
        assert all(p["enabled"] for p in ps)
        assert [p["order"] for p in ps] == sorted(p["order"] for p in ps)
        assert "warm" in {p["id"] for p in ps}

    def test_toggle_enabled(self, admin_client):
        r = admin_client.put(f"{API}/presets/polaroid", json={"enabled": False})
        assert r.status_code == 200 and r.json()["enabled"] is False
        assert all(p["id"] != "polaroid"
                   for p in requests.get(f"{API}/events/active").json()["presets"])
        r2 = admin_client.put(f"{API}/presets/polaroid", json={"enabled": True})
        assert r2.status_code == 200 and r2.json()["enabled"] is True


# ---------------- Full session flow ----------------
@pytest.fixture(scope="module")
def finalized_session(active_event, anon):
    eid = active_event["event"]["id"]
    r = anon.post(f"{API}/sessions/start", json={
        "event_id": eid, "template_id": "tpl-4x6-quad", "preset_id": "warm"})
    assert r.status_code == 200, r.text[:300]
    s = r.json()
    sid = s["id"]
    for i, color in enumerate([(200, 30, 30), (30, 200, 30), (30, 30, 200), (220, 220, 30)]):
        pr = anon.post(f"{API}/sessions/photo", json={
            "session_id": sid, "slot_index": i, "image_base64": make_jpeg_b64(color)})
        assert pr.status_code == 200, pr.text[:300]
    fin = anon.post(f"{API}/sessions/{sid}/finalize", json={})
    assert fin.status_code == 200, fin.text[:400]
    return {"session_id": sid, "event_id": eid, "start": s, "finalize": fin.json()}


class TestSessionFlow:
    def test_start_has_qr_token(self, finalized_session):
        s = finalized_session["start"]
        assert s["status"] == "capturing" and s["photo_paths"] == []
        assert isinstance(s["qr_token"], str) and len(s["qr_token"]) >= 8

    def test_finalize_response(self, finalized_session):
        f = finalized_session["finalize"]
        assert f["ok"] is True
        assert f["qr_token"] == finalized_session["start"]["qr_token"]
        assert f["guest_url"].endswith(f"/g/{f['qr_token']}")
        assert f["print_path"].endswith("print.png")

    def test_session_doc(self, anon, finalized_session):
        r = anon.get(f"{API}/sessions/{finalized_session['session_id']}")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ready"
        assert len([p for p in d["photo_paths"] if p]) == 4
        assert d["print_path"] and d["web_path"] and d["qr_expires_at"]
        assert "_id" not in d

    def test_print_file_dimensions_and_dpi(self, anon, finalized_session):
        rel = finalized_session["finalize"]["print_path"]
        r = anon.get(f"{API}/files/{rel}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        img = Image.open(io.BytesIO(r.content))
        assert img.size == (1200, 1800), img.size
        # PNG pHYs stores pixels-per-meter as int, so 300 DPI reads back as 299.9994
        dpi = img.info.get("dpi")
        assert dpi and all(abs(v - 300) < 0.01 for v in dpi), dpi

    def test_web_file_served(self, anon, finalized_session):
        sid = finalized_session["session_id"]
        rel = anon.get(f"{API}/sessions/{sid}").json()["web_path"]
        r = anon.get(f"{API}/files/{rel}")
        assert r.status_code == 200
        assert Image.open(io.BytesIO(r.content)).format == "JPEG"

    def test_missing_file_404(self, anon):
        assert anon.get(f"{API}/files/nope/nope/print.png").status_code == 404

    def test_photo_unknown_session_404(self, anon):
        r = anon.post(f"{API}/sessions/photo", json={
            "session_id": "does-not-exist", "slot_index": 0,
            "image_base64": make_jpeg_b64()})
        assert r.status_code == 404

    def test_session_not_found(self, anon):
        assert anon.get(f"{API}/sessions/does-not-exist").status_code == 404


@pytest.mark.parametrize("tpl,expected", [
    ("tpl-classic-strip", (600, 1800)),
    ("tpl-strip-double", (1200, 1800)),
    ("tpl-4x6-single", (1200, 1800)),
    ("tpl-square-social", (1500, 1500)),
])
def test_print_dimensions_per_template(anon, active_event, tpl, expected):
    eid = active_event["event"]["id"]
    s = anon.post(f"{API}/sessions/start", json={
        "event_id": eid, "template_id": tpl, "preset_id": "bw"}).json()
    for i in range(3):
        assert anon.post(f"{API}/sessions/photo", json={
            "session_id": s["id"], "slot_index": i,
            "image_base64": make_jpeg_b64((10 + i * 40, 90, 160))}).status_code == 200
    f = anon.post(f"{API}/sessions/{s['id']}/finalize", json={})
    assert f.status_code == 200, f.text[:300]
    r = anon.get(f"{API}/files/{f.json()['print_path']}")
    assert r.status_code == 200
    img = Image.open(io.BytesIO(r.content))
    assert img.size == expected, f"{tpl}: {img.size}"
    dpi = img.info.get("dpi")
    assert dpi and all(abs(v - 300) < 0.01 for v in dpi), dpi


# ---------------- Retake (slot replace, not append) ----------------
def test_retake_replaces_slot(anon, active_event):
    eid = active_event["event"]["id"]
    s = anon.post(f"{API}/sessions/start", json={
        "event_id": eid, "template_id": "tpl-4x6-single", "preset_id": "original"}).json()
    r1 = anon.post(f"{API}/sessions/photo", json={
        "session_id": s["id"], "slot_index": 0, "image_base64": make_jpeg_b64((255, 0, 0))})
    r2 = anon.post(f"{API}/sessions/photo", json={
        "session_id": s["id"], "slot_index": 0, "image_base64": make_jpeg_b64((0, 0, 255))})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["path"] != r2.json()["path"]
    doc = anon.get(f"{API}/sessions/{s['id']}").json()
    assert len(doc["photo_paths"]) == 1, doc["photo_paths"]
    assert doc["photo_paths"][0] == r2.json()["path"]


# ---------------- Print jobs ----------------
def test_print_job_lifecycle(anon, admin_client, finalized_session):
    sid = finalized_session["session_id"]
    r = anon.post(f"{API}/print/{sid}?copies=2")
    assert r.status_code == 200, r.text[:300]
    job = r.json()
    assert job["driver"] == "mock" and job["copies"] == 2
    assert job["state"] == "queued" and "_id" not in job
    jid = job["id"]

    state = None
    for _ in range(15):
        time.sleep(1)
        q = admin_client.get(f"{API}/print/queue")
        assert q.status_code == 200
        found = [j for j in q.json() if j["id"] == jid]
        assert found, "job missing from queue"
        state = found[0]["state"]
        if state == "done":
            break
    assert state == "done", f"final state={state}"

    sess = anon.get(f"{API}/sessions/{sid}").json()
    assert sess["copies_printed"] >= 2


def test_print_unfinalized_session_400(anon, active_event):
    s = anon.post(f"{API}/sessions/start", json={
        "event_id": active_event["event"]["id"],
        "template_id": "tpl-4x6-single", "preset_id": "original"}).json()
    r = anon.post(f"{API}/print/{s['id']}")
    assert r.status_code == 400


# ---------------- Hardware / stats ----------------
def test_hardware_status_public(anon):
    r = requests.get(f"{API}/hardware/status")
    assert r.status_code == 200
    d = r.json()
    assert d["bridge"]["connected"] is False
    assert d["camera_source"] == "webcam"
    assert d["printer_driver"] == "mock"
    assert isinstance(d["storage_free_gb"], (int, float)) and d["storage_free_gb"] > 0
    assert d["lan_ip"]


def test_stats_admin(admin_client):
    r = admin_client.get(f"{API}/stats")
    assert r.status_code == 200
    d = r.json()
    for k in ["total_sessions", "today_sessions", "prints_today",
              "photos_captured", "avg_session_seconds"]:
        assert k in d
    assert d["total_sessions"] >= 1 and d["photos_captured"] >= 4


# ---------------- Guest gallery (public) ----------------
class TestGuestGallery:
    def test_gallery_public(self, finalized_session):
        token = finalized_session["finalize"]["qr_token"]
        r = requests.get(f"{API}/g/{token}")
        assert r.status_code == 200
        d = r.json()
        assert d["event"]["name"]
        assert d["session"]["print_path"] and d["session"]["web_path"]
        assert len([p for p in d["session"]["raw_photos"] if p]) == 4
        assert d["session"]["completed_at"]

    def test_gallery_bad_token(self):
        assert requests.get(f"{API}/g/nosuchtoken").status_code == 404

    def test_zip(self, finalized_session):
        token = finalized_session["finalize"]["qr_token"]
        r = requests.get(f"{API}/g/{token}/zip")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        import zipfile
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        assert "print.png" in names and "web.jpg" in names
        assert len([n for n in names if n.startswith("raw_")]) == 4

    def test_lead(self, finalized_session):
        token = finalized_session["finalize"]["qr_token"]
        r = requests.post(f"{API}/g/{token}/lead",
                          json={"name": "TEST_Guest", "email": "test_guest@example.com"})
        assert r.status_code == 200 and r.json()["ok"] is True

    def test_lead_bad_token(self):
        r = requests.post(f"{API}/g/nosuchtoken/lead", json={"name": "x"})
        assert r.status_code == 404

    def test_qr_png(self, finalized_session):
        token = finalized_session["finalize"]["qr_token"]
        r = requests.get(f"{API}/qr/{token}.png")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        img = Image.open(io.BytesIO(r.content))
        assert img.size[0] > 50


# ---------------- Expired QR token ----------------
def test_expired_qr_returns_410(anon, admin_client, active_event):
    """Create an event with qr_expiry_days=0 so qr_expires_at is (essentially) now."""
    ev = admin_client.post(f"{API}/events", json={
        "name": "TEST_Expiry", "qr_expiry_days": -1}).json()
    eid = ev["id"]
    try:
        s = anon.post(f"{API}/sessions/start", json={
            "event_id": eid, "template_id": "tpl-4x6-single",
            "preset_id": "original"}).json()
        assert anon.post(f"{API}/sessions/photo", json={
            "session_id": s["id"], "slot_index": 0,
            "image_base64": make_jpeg_b64()}).status_code == 200
        f = anon.post(f"{API}/sessions/{s['id']}/finalize", json={})
        assert f.status_code == 200
        token = f.json()["qr_token"]
        r = requests.get(f"{API}/g/{token}")
        assert r.status_code == 410, f"expected 410, got {r.status_code}"
        admin_client.delete(f"{API}/sessions/{s['id']}")
    finally:
        admin_client.delete(f"{API}/events/{eid}")


# ---------------- Cleanup ----------------
@pytest.fixture(scope="module", autouse=True)
def cleanup(request):
    yield
    try:
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"password": ADMIN_PASSWORD})
        for e in s.get(f"{API}/events").json():
            if str(e.get("name", "")).startswith("TEST_"):
                s.delete(f"{API}/events/{e['id']}")
        for t in s.get(f"{API}/templates").json():
            if str(t.get("name", "")).startswith("TEST_"):
                s.delete(f"{API}/templates/{t['id']}")
    except Exception:
        pass
