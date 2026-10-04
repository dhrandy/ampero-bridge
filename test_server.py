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


def test_health_is_minimal_and_detail_needs_the_key(monkeypatch):
    srv, base = start(monkeypatch)
    monkeypatch.setattr(usb, "seen", lambda: {"libusb_devices": 3, "dev_nodes": 5})
    assert call(base, "/health", key="") == (200, {"ok": True})
    assert call(base, "/api/health", key="")[0] == 401
    code, body = call(base, "/api/health")
    assert code == 200 and body["pedal_connected"] is True and body["usb_seen"] == {"libusb_devices": 3, "dev_nodes": 5}
    monkeypatch.setattr(usb, "describe", lambda: {"present": False, "visible_devices": [{"id": "1d6b:0002", "bus": 1, "address": 1}]})
    assert call(base, "/api/usb")[1]["visible_devices"][0]["id"] == "1d6b:0002"
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


def test_odd_input_is_a_clean_400_not_a_500_with_internals(monkeypatch):
    srv, base = start(monkeypatch)
    for path, body in [("/api/param", {"slot": {"a": 1}, "model_code": 4, "param": 1, "value": 1}),
                       ("/api/patch/select", {"index": 1e400}),
                       ("/api/patch/select", {"index": True}),
                       ("/api/patch/save", {"index": 1, "name": "\u00e9", "confirm": "SAVE P1-2"})]:
        code, out = call(base, path, body)
        assert code == 400, (path, body, out)
        assert "Error" not in out["error"] or out["kind"] == "ProtocolError"
    assert Fake.sent == []
    srv.shutdown()


def test_unexpected_error_is_a_generic_500(monkeypatch):
    srv, base = start(monkeypatch)
    monkeypatch.setattr(usb, "describe", lambda: 1 / 0)
    code, out = call(base, "/api/usb")
    assert code == 500 and out == {"error": "internal error", "kind": "InternalError"}
    srv.shutdown()


def test_bad_content_length_is_400(monkeypatch):
    import http.client
    srv, base = start(monkeypatch)
    for cl in ("-1", "abc"):
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
        c.putrequest("POST", "/api/block")
        c.putheader("X-Api-Key", "k")
        c.putheader("Content-Length", cl)
        c.endheaders()
        r = c.getresponse()
        assert r.status == 400
        c.close()
    srv.shutdown()


def test_server_header_hides_versions(monkeypatch):
    srv, base = start(monkeypatch)
    with urllib.request.urlopen(base + "/health", timeout=5) as r:
        assert r.headers["Server"] == "ampero-bridge"
    srv.shutdown()


def test_model_only_proven_codes_unless_overridden(monkeypatch):
    srv, base = start(monkeypatch)
    assert call(base, "/api/model", {"slot": "rvb", "code": 4})[0] == 200
    assert call(base, "/api/model", {"slot": "fx2", "code": 9})[0] == 200
    sent = len(Fake.sent)
    assert call(base, "/api/model", {"slot": "rvb", "code": 5})[0] == 400
    assert call(base, "/api/model", {"slot": "fx2", "code": 15})[0] == 400
    assert call(base, "/api/model", {"slot": 2, "code": 4})[0] == 400
    assert len(Fake.sent) == sent
    monkeypatch.setattr(server, "ALLOW_UNPROVEN", True)
    assert call(base, "/api/model", {"slot": "rvb", "code": 5})[0] == 200
    srv.shutdown()


def test_weak_or_placeholder_key_will_not_start(monkeypatch):
    import pytest
    for bad in ("short", "change-me-to-a-long-random-string"):
        monkeypatch.setattr(server, "API_KEY", bad)
        with pytest.raises(SystemExit):
            server.main()


def test_too_many_connections_get_503(monkeypatch):
    import socket
    srv, base = start(monkeypatch)
    srv._slots = threading.BoundedSemaphore(1)
    held = socket.create_connection(("127.0.0.1", srv.server_address[1]))   # takes the only slot, sends nothing
    import time
    time.sleep(0.3)
    s2 = socket.create_connection(("127.0.0.1", srv.server_address[1]), timeout=5)
    assert s2.recv(100).startswith(b"HTTP/1.0 503")
    held.close(); s2.close()
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


def test_read_current_patch(monkeypatch):
    srv, base = start(monkeypatch)
    Fake.replies = dump()
    code, out = call(base, "/api/patch/current")
    assert code == 200 and out["name"] == "WADE" and out["label"] == "P26-1"
    code, out = call(base, "/api/patch/current")      # pedal says nothing
    assert code == 504
    srv.shutdown()


def test_read_by_index_only_when_it_is_the_selected_patch(monkeypatch):
    srv, base = start(monkeypatch)
    Fake.replies = dump()
    assert call(base, "/api/patch/75")[1]["name"] == "WADE"
    Fake.replies = dump()                              # pedal still on 75, asked for 74
    code, out = call(base, "/api/patch/74")
    assert code == 409 and out["current_index"] == 75 and out["asked_index"] == 74
    assert out["current_name"] == "WADE"
    srv.shutdown()


def _wait_backup(base, secs=5):
    import time
    end = time.time() + secs
    while time.time() < end:
        out = call(base, "/api/backups")[1]
        if not out["running"] and out["last"]:
            return out
        time.sleep(0.02)
    raise AssertionError("backup did not finish")


def _fake_pedal(monkeypatch, bad=()):
    state = {"idx": 75, "sent": []}

    def send_midi(msg, name):
        if msg[0] & 0xF0 == 0xC0:
            state["idx"] = msg[1]
        state["sent"].append(name)

    def read():
        if state["idx"] in bad:
            return {"index": 0, "label": "x", "name": "WRONG", "record_hex": ""}
        i = state["idx"]
        return {"index": i, "label": am.patch_label(i), "name": f"P{i}", "record_hex": f"{i:02x}"}

    monkeypatch.setattr(server, "send_midi", send_midi)
    monkeypatch.setattr(server, "read_current_patch", read)
    monkeypatch.setattr(server, "SETTLE", 0)
    return state


def test_backup_writes_one_file_with_every_patch_and_restores_selection(monkeypatch, tmp_path):
    srv, base = start(monkeypatch)
    monkeypatch.setattr(server, "BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr(server, "BACKUP_SLOTS", 5)
    state = _fake_pedal(monkeypatch)
    assert call(base, "/api/backups", {})[1]["started"] is True
    out = _wait_backup(base)
    assert out["last"]["ok"] and out["last"]["patches"] == 5 and out["last"]["errors"] == 0
    name = out["last"]["file"]
    assert out["files"] == [name]
    doc = json.loads((tmp_path / name).read_text())
    assert [p["index"] for p in doc["patches"]] == [0, 1, 2, 3, 4]
    assert doc["index"][2] == {"index": 2, "label": am.patch_label(2), "name": "P2"}
    assert doc["selected_before"]["index"] == 75
    assert state["idx"] == 75                       # selection put back
    assert not any("save" in n for n in state["sent"])   # reads and selects only
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]
    # download
    req = urllib.request.Request(base + "/api/backups/" + name, headers={"X-Api-Key": "k"})
    assert json.loads(urllib.request.urlopen(req).read())["patches"][0]["name"] == "P0"
    srv.shutdown()


def test_backup_keeps_going_when_one_slot_fails(monkeypatch, tmp_path):
    srv, base = start(monkeypatch)
    monkeypatch.setattr(server, "BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr(server, "BACKUP_SLOTS", 4)
    _fake_pedal(monkeypatch, bad={2})
    call(base, "/api/backups", {})
    out = _wait_backup(base)
    assert out["last"]["patches"] == 3 and out["last"]["errors"] == 1
    doc = json.loads((tmp_path / out["last"]["file"]).read_text())
    assert doc["errors"][0]["index"] == 2
    srv.shutdown()


def test_backup_needs_key_and_rejects_bad_file_names(monkeypatch, tmp_path):
    srv, base = start(monkeypatch)
    monkeypatch.setattr(server, "BACKUP_DIR", str(tmp_path))
    for path in ("/api/backups", "/api/backups/ampero-backup-20260101-000000.json"):
        try:
            urllib.request.urlopen(base + path)
            raise AssertionError("expected 401")
        except HTTPError as e:
            assert e.code == 401
    for bad in ("../../etc/passwd", "x.json", "ampero-backup-1.json"):
        req = urllib.request.Request(base + "/api/backups/" + bad, headers={"X-Api-Key": "k"})
        try:
            urllib.request.urlopen(req)
            raise AssertionError("expected 404")
        except HTTPError as e:
            assert e.code == 404
    srv.shutdown()


def test_writes_are_refused_while_a_backup_runs_and_bad_folder_is_503(monkeypatch, tmp_path):
    srv, base = start(monkeypatch)
    monkeypatch.setattr(server.backup, "running", True)
    code, out = call(base, "/api/patch/select", {"index": 1})
    assert code == 409 and Fake.sent == []
    assert call(base, "/api/backups", {})[0] == 409          # already running
    monkeypatch.setattr(server.backup, "running", False)
    monkeypatch.setattr(server, "BACKUP_DIR", str(tmp_path / "f" / "x"))
    (tmp_path / "f").write_text("a file, not a folder")
    code, out = call(base, "/api/backups", {})
    assert code == 503 and "backup folder" in out["error"]
    srv.shutdown()
