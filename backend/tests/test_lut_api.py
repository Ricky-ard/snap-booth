"""API-level tests for the .cube 3D LUT feature (upload / serve / delete /
end-to-end print integration). Uses the public REACT_APP_BACKEND_URL."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pytest
import requests
from PIL import Image

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from lut import identity_cube, parse_cube_file  # noqa: E402
from conftest import make_jpeg_b64  # noqa: E402

PRESET = "warm"
N = 17


def _teal_orange_cube(size: int = 17) -> str:
    lines = [f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for b in range(size):
        for g in range(size):
            for r in range(size):
                fr = r / (size - 1); fg = g / (size - 1); fb = b / (size - 1)
                L = 0.299 * fr + 0.587 * fg + 0.114 * fb
                lines.append("%.6f %.6f %.6f" % (
                    min(1.0, fr + 0.35 * (L - 0.5)), fg, max(0.0, fb - 0.35 * (L - 0.5))))
    return "\n".join(lines)


@pytest.fixture(scope="module")
def cube_text():
    return _teal_orange_cube(N)


@pytest.fixture(scope="module", autouse=True)
def cleanup_lut(api, request):
    """Ensure no LUT is left on the seeded preset after the module runs."""
    yield
    s = requests.Session()
    r = s.post(f"{api}/auth/login", json={"password": "snapbooth"})
    if r.status_code == 200:
        s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
        s.delete(f"{api}/presets/{PRESET}/lut")


# ---------- end-to-end print integration ---------------------------------
def _run_session(api, anon, event_id, preset=PRESET, n_photos=4):
    st = anon.post(f"{api}/sessions/start", json={
        "event_id": event_id, "template_id": "tpl-4x6-quad", "preset_id": preset})
    assert st.status_code == 200, st.text[:300]
    sid = st.json()["id"]
    colors = [(200, 120, 60), (60, 140, 200), (120, 200, 120), (180, 180, 60)]
    for i in range(n_photos):
        r = anon.post(f"{api}/sessions/photo", json={
            "session_id": sid, "slot_index": i,
            "image_base64": make_jpeg_b64(colors[i % 4], (900, 1200))})
        assert r.status_code == 200, r.text[:200]
    fin = anon.post(f"{api}/sessions/{sid}/finalize", json={})
    assert fin.status_code == 200, fin.text[:400]
    d = fin.json()
    pp = d.get("print_path") or d.get("printPath")
    assert pp, d
    img = requests.get(f"{api}/files/{pp}")
    assert img.status_code == 200, img.status_code
    im = Image.open(io.BytesIO(img.content))
    return sid, im


# ---------- upload ---------------------------------------------------------
class TestLutFeature:
    def test_upload_requires_admin(self, api, anon, cube_text):
        r = requests.post(f"{api}/presets/{PRESET}/lut",
                          files={"file": ("t.cube", cube_text, "text/plain")})
        assert r.status_code in (401, 403), r.text[:200]

    def test_upload_valid_cube(self, api, admin_client, cube_text):
        r = admin_client.post(f"{api}/presets/{PRESET}/lut",
                              files={"file": ("TEST_teal.cube", cube_text, "text/plain")},
                              headers={"Content-Type": None})
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("lut_size") == N
        assert isinstance(d.get("lut_path"), str) and d["lut_path"].endswith(".cube")
        assert "_id" not in d

        # persistence: preset list must carry lut_path/lut_size
        presets = admin_client.get(f"{api}/presets").json()
        p = next(x for x in presets if x["id"] == PRESET)
        assert p["lut_size"] == N
        assert p["lut_path"] == d["lut_path"]

    def test_upload_wrong_extension_400(self, api, admin_client):
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), (1, 2, 3)).save(buf, "PNG")
        r = admin_client.post(f"{api}/presets/{PRESET}/lut",
                              files={"file": ("photo.png", buf.getvalue(), "image/png")},
                              headers={"Content-Type": None})
        assert r.status_code == 400, r.text[:200]

    def test_upload_unparseable_cube_400(self, api, admin_client):
        r = admin_client.post(f"{api}/presets/{PRESET}/lut",
                              files={"file": ("bogus.cube", "this is not a lut\nhello world\n",
                                              "text/plain")},
                              headers={"Content-Type": None})
        assert r.status_code == 400, r.text[:200]

    def test_upload_truncated_cube_400(self, api, admin_client):
        bad = "LUT_3D_SIZE 17\n0.0 0.0 0.0\n0.1 0.1 0.1\n"
        r = admin_client.post(f"{api}/presets/{PRESET}/lut",
                              files={"file": ("short.cube", bad, "text/plain")},
                              headers={"Content-Type": None})
        assert r.status_code == 400, r.text[:200]


    # ---------- strip PNG serving -----------------------------------------
    def test_strip_png_public_and_layout(self, api, cube_text):
        # Re-attach (previous class may have left it attached; be explicit)
        s = requests.Session()
        s.headers.update({"Authorization": ""})
        login = requests.post(f"{api}/auth/login", json={"password": "snapbooth"})
        tok = login.json()["token"]
        up = requests.post(f"{api}/presets/{PRESET}/lut",
                           files={"file": ("TEST_teal.cube", cube_text, "text/plain")},
                           headers={"Authorization": f"Bearer {tok}"})
        assert up.status_code == 200, up.text[:200]

        r = requests.get(f"{api}/presets/{PRESET}/lut.png")  # no auth
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type") == "image/png"
        assert r.headers.get("X-Lut-Size") == str(N)
        # Origin sets "public, max-age=600"; the preview edge proxy may rewrite
        # Cache-Control to no-store, so accept either but require the header.
        assert r.headers.get("Cache-Control"), "missing Cache-Control header"

        img = np.array(Image.open(io.BytesIO(r.content)).convert("RGB"))
        assert img.shape == (N, N * N, 3), img.shape

        lut, _, _, size = parse_cube_file(cube_text)
        assert size == N
        for (rr, gg, bb) in [(0, 0, 0), (3, 11, 7), (N // 2, N // 2, N // 2), (N - 1, N - 1, N - 1)]:
            expected = np.clip(lut[rr, gg, bb] * 255.0, 0, 255).astype(int)
            actual = img[gg, bb * N + rr].astype(int)
            assert np.all(np.abs(actual - expected) <= 1), \
                f"strip mismatch r={rr} g={gg} b={bb}: {actual} vs {expected}"

    def test_strip_png_404_for_preset_without_lut(self, api):
        r = requests.get(f"{api}/presets/original/lut.png")
        assert r.status_code == 404, r.status_code

    def test_strip_png_404_unknown_preset(self, api):
        r = requests.get(f"{api}/presets/does-not-exist/lut.png")
        assert r.status_code == 404


    # ---------- delete ----------------------------------------------------
    def test_delete_requires_admin(self, api):
        r = requests.delete(f"{api}/presets/{PRESET}/lut")
        assert r.status_code in (401, 403), r.status_code

    def test_delete_clears_fields(self, api, admin_client, cube_text):
        admin_client.post(f"{api}/presets/{PRESET}/lut",
                          files={"file": ("TEST_teal.cube", cube_text, "text/plain")},
                          headers={"Content-Type": None})
        r = admin_client.delete(f"{api}/presets/{PRESET}/lut")
        assert r.status_code == 200, r.text[:200]
        presets = admin_client.get(f"{api}/presets").json()
        p = next(x for x in presets if x["id"] == PRESET)
        assert "lut_path" not in p and "lut_size" not in p, p
        assert requests.get(f"{api}/presets/{PRESET}/lut.png").status_code == 404




    def test_print_differs_with_lut(self, api, anon, admin_client, active_event, cube_text):
        eid = active_event["event"]["id"]

        # Baseline: ensure no LUT
        admin_client.delete(f"{api}/presets/{PRESET}/lut")
        _, base_img = _run_session(api, anon, eid)
        assert base_img.size == (1200, 1800)
        assert tuple(round(x) for x in (base_img.info.get("dpi") or (0, 0))) == (300, 300), base_img.info
        base = np.array(base_img.convert("RGB")).astype(int)

        # With LUT attached
        up = admin_client.post(f"{api}/presets/{PRESET}/lut",
                               files={"file": ("TEST_teal.cube", cube_text, "text/plain")},
                               headers={"Content-Type": None})
        assert up.status_code == 200, up.text[:200]
        _, lut_img = _run_session(api, anon, eid)
        assert lut_img.size == (1200, 1800)
        assert tuple(round(x) for x in (lut_img.info.get("dpi") or (0, 0))) == (300, 300)
        withlut = np.array(lut_img.convert("RGB")).astype(int)

        mean_diff = float(np.abs(base - withlut).mean())
        assert mean_diff > 2.0, f"LUT had no measurable effect on print (mean {mean_diff:.2f})"

        # Removing the LUT restores the baseline render
        admin_client.delete(f"{api}/presets/{PRESET}/lut")
        _, restored_img = _run_session(api, anon, eid)
        restored = np.array(restored_img.convert("RGB")).astype(int)
        assert float(np.abs(base - restored).mean()) < 1.0


    # ---------- identity LUT must not change the print --------------------
    def test_zz_identity_lut_print_is_visually_unchanged(self, api, anon, admin_client, active_event):
        eid = active_event["event"]["id"]
        admin_client.delete(f"{api}/presets/{PRESET}/lut")
        _, base_img = _run_session(api, anon, eid)
        base = np.array(base_img.convert("RGB")).astype(int)

        up = admin_client.post(f"{api}/presets/{PRESET}/lut",
                               files={"file": ("TEST_identity.cube", identity_cube(17), "text/plain")},
                               headers={"Content-Type": None})
        assert up.status_code == 200, up.text[:200]
        _, id_img = _run_session(api, anon, eid)
        ident = np.array(id_img.convert("RGB")).astype(int)
        mean_diff = float(np.abs(base - ident).mean())
        assert mean_diff < 1.5, f"identity LUT changed the print (mean {mean_diff:.2f})"
        admin_client.delete(f"{api}/presets/{PRESET}/lut")
