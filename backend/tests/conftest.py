import os
import base64
import io

import pytest
import requests
from dotenv import dotenv_values
from PIL import Image

frontend_env = dotenv_values("/app/frontend/.env")
_base = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not _base:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = _base.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_PASSWORD = "snapbooth"
KIOSK_PIN = "1234"


def make_jpeg_b64(color=(255, 0, 0), size=(1200, 1600)) -> str:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


@pytest.fixture(scope="session")
def api():
    return API


@pytest.fixture(scope="session")
def anon():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_client():
    """Session authenticated via login (keeps cookie) + Bearer header."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("token")
    if not token:
        pytest.fail("login response missing token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def admin_token(admin_client):
    return admin_client.headers["Authorization"].split(" ", 1)[1]


@pytest.fixture(scope="session")
def active_event(anon):
    r = anon.get(f"{API}/events/active")
    assert r.status_code == 200, r.text[:300]
    return r.json()
