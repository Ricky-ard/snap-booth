import base64, io, json, requests
from PIL import Image
from dotenv import dotenv_values

API = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"

def b64(color):
    im = Image.new("RGB", (1200, 1600), color)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

ev = requests.get(f"{API}/events/active").json()
eid = ev["event"]["id"]
s = requests.post(f"{API}/sessions/start", json={"event_id": eid, "template_id": "tpl-4x6-quad", "preset_id": "warm"}).json()
for i, c in enumerate([(220, 60, 60), (60, 200, 90), (70, 90, 230), (230, 210, 60)]):
    requests.post(f"{API}/sessions/photo", json={"session_id": s["id"], "slot_index": i, "image_base64": b64(c)})
f = requests.post(f"{API}/sessions/{s['id']}/finalize", json={}).json()
print(json.dumps({"session_id": s["id"], "token": f["qr_token"], "event_name": ev["event"]["name"]}))
