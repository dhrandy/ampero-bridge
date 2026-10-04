import json
import os
import threading
import urllib.request
from urllib.error import HTTPError

os.environ["API_KEY"] = "k"

import ampero_mini as am  # noqa: E402
import server  # noqa: E402
import usbmidi as usb  # noqa: E402


def dump(name="WADE", idx=0x4B):
    rec = bytes([0x01, idx, 0x00, 0x3C]) + name.encode().ljust(18, b"\0") + bytes(20)
    nib = bytes(x for b in rec for x in (b >> 4, b & 15))
    out = []
    for n in range(5):
        body = bytes([0, 2, 0x14, 0, 1, idx, 0, n]) + (nib if n == 0 else b"\0\0")
        out.append(am.frame(am.KIND_DATA, body))
    return out


class Fake:
    sent = []
    present = True
    replies = []

    def __enter__(self):
        if not Fake.present:
            raise usb.PedalNotConnected("pedal not connected")
        return self

    def __exit__(self, *a):
        return False

    def drain(self):
        pass

    def send_midi(self, m):
        Fake.sent.append(("midi", m))

    def send_sysex(self, f):
        Fake.sent.append(("sysex", f))

    def send_sysex_batch(self, fs):
        Fake.sent.append(("batch", list(fs)))

    def collect(self, t, until=None):
        r, Fake.replies = Fake.replies, []
        return r


def start(monkeypatch):
    monkeypatch.setattr(usb, "Pedal", Fake)
    monkeypatch.setattr(usb, "is_present", lambda: Fake.present)
    Fake.sent, Fake.present, Fake.replies = [], True, []
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def call(base, path, body=None, key="k"):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"X-Api-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except HTTPError as e:
        return e.code, json.loads(e.read())


def test_health_open_and_api_needs_key(monkeypatch):
    srv, base = start(monkeypatch)
    assert call(base, "/health", key="")[0] == 200
    assert call(base, "/api/usb", key="wrong")[0] == 401
    srv.shutdown()


def test_select_block_param(monkeypatch):
    srv, base = start(monkeypatch)
    assert call(base, "/api/patch/select", {"index": 75})[1]["label"] == "P26-1"
    assert call(base, "/api/block", {"block": "rvb", "on": True})[0] == 200
    assert call(base, "/api/param", {"slot": "eq", "model_code": 4, "param": 3, "value": 30})[0] == 200
    assert Fake.sent[0] == ("midi", bytes([0xC0, 75]))
    assert Fake.sent[1] == ("midi", bytes([0xB0, 56, 127]))
    assert Fake.sent[2][0] == "sysex"
    srv.shutdown()


def test_bad_input_is_400_and_sends_nothing(monkeypatch):
    srv, base = start(monkeypatch)
    assert call(base, "/api/patch/select", {"index": 999})[0] == 400
    assert call(base, "/api/block", {"block": "nope", "on": True})[0] == 400
    assert call(base, "/api/param", {"slot": "eq"})[0] == 400
    assert Fake.sent == []
    srv.shutdown()


def test_save_needs_confirm_and_goes_out_as_one_batch(monkeypatch):
    srv, base = start(monkeypatch)
    assert call(base, "/api/patch/save", {"index": 75, "name": "WADE"})[0] == 400
    assert Fake.sent == []
    code, out = call(base, "/api/patch/save", {"index": 75, "name": "WADE", "confirm": "SAVE P26-1"})
    assert code == 200 and out["verified"] is False
    assert Fake.sent[0][0] == "batch" and len(Fake.sent[0][1]) == 2
    srv.shutdown()


def test_pedal_unplugged_is_503_not_a_hang(monkeypatch):
    srv, base = start(monkeypatch)
    Fake.present = False
    code, out = call(base, "/api/patch/select", {"index": 1})
    assert code == 503 and out["kind"] == "PedalNotConnected"
    Fake.present = True
    assert call(base, "/api/patch/select", {"index": 1})[0] == 200   # comes back on its own
    srv.shutdown()


def test_read_patch(monkeypatch):
    srv, base = start(monkeypatch)
    Fake.replies = dump()
    code, out = call(base, "/api/patch/75")
    assert code == 200 and out["name"] == "WADE" and out["label"] == "P26-1"
    code, out = call(base, "/api/patch/75")      # pedal says nothing
    assert code == 504
    srv.shutdown()
