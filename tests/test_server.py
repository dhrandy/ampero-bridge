import json
import os
import threading
import urllib.request
from urllib.error import HTTPError

import tempfile  # noqa: E402

os.environ["API_KEY"] = "k"
os.environ["AMPERO_DATA_DIR"] = tempfile.mkdtemp()

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


def test_known_patches_fill_from_reads_and_survive_a_restart(monkeypatch, tmp_path):
    srv, base = start(monkeypatch)
    monkeypatch.setattr(server, "known", server.Known(str(tmp_path)))
    assert call(base, "/api/patches/known")[1] == {"count": 0, "persistent": True, "patches": []}
    Fake.replies = dump("DEXTER", 0x4C)
    assert call(base, "/api/patch/current")[0] == 200
    Fake.replies = dump("CHERUB", 0x4E)
    call(base, "/api/patch/current")
    out = call(base, "/api/patches/known")[1]
    assert out["count"] == 2 and out["persistent"] is True
    assert [(p["index"], p["name"], p["label"]) for p in out["patches"]] == [
        (76, "DEXTER", "P26-2"), (78, "CHERUB", "P27-1")]
    assert out["patches"][0]["seen"]
    # a fresh process reads the file back
    assert [p["name"] for p in server.Known(str(tmp_path)).listing()["patches"]] == ["DEXTER", "CHERUB"]
    srv.shutdown()


def test_known_patches_need_the_key_and_ask_the_pedal_nothing(monkeypatch, tmp_path):
    srv, base = start(monkeypatch)
    monkeypatch.setattr(server, "known", server.Known(str(tmp_path)))
    try:
        urllib.request.urlopen(base + "/api/patches/known")
        raise AssertionError("expected 401")
    except HTTPError as e:
        assert e.code == 401
    Fake.present = False                      # pedal unplugged: the cache still answers
    assert call(base, "/api/patches/known")[0] == 200
    assert Fake.sent == []
    srv.shutdown()


def test_known_patches_rename_is_picked_up_and_save_is_remembered(monkeypatch, tmp_path):
    srv, base = start(monkeypatch)
    monkeypatch.setattr(server, "known", server.Known(str(tmp_path)))
    Fake.replies = dump("OLD", 0x4B)
    call(base, "/api/patch/current")
    Fake.replies = dump("NEW", 0x4B)
    call(base, "/api/patch/current")
    assert [p["name"] for p in call(base, "/api/patches/known")[1]["patches"]] == ["NEW"]
    call(base, "/api/patch/save", {"index": 75, "name": "SAVED", "confirm": "SAVE P26-1"})
    p = call(base, "/api/patches/known")[1]["patches"][0]
    assert p["name"] == "SAVED" and p["source"] == "save"
    srv.shutdown()


def test_unwritable_or_broken_store_never_breaks_a_pedal_read(monkeypatch, tmp_path):
    srv, base = start(monkeypatch)
    blocker = tmp_path / "f"
    blocker.write_text("a file, not a folder")
    monkeypatch.setattr(server, "known", server.Known(str(blocker / "data")))
    Fake.replies = dump("WADE", 0x4B)
    code, out = call(base, "/api/patch/current")
    assert code == 200 and out["name"] == "WADE"
    listing = call(base, "/api/patches/known")[1]
    assert listing["persistent"] is False and listing["patches"][0]["name"] == "WADE"
    (tmp_path / "known-patches.json").write_text("{not json")
    assert server.Known(str(tmp_path)).listing()["count"] == 0     # broken file ignored
    srv.shutdown()


def test_history_endpoint_needs_key_and_reads_no_pedal(monkeypatch):
    srv, base = start(monkeypatch)
    h = server.History(600, 50)
    monkeypatch.setattr(server, "history", h)
    h.add({"index": 76, "label": "P26-2", "name": "X", "record_hex": "0102"}, now=50)
    assert call(base, "/api/history", key="")[0] == 401
    code, out = call(base, "/api/history")
    assert code == 200 and out["states"][0]["name"] == "X" and out["entries"] == 1
    assert call(base, "/api/history?hex=0")[1]["states"][0].get("record_hex") is None
    assert call(base, "/api/history?since=1e12")[1]["states"] == []
    assert call(base, "/api/history?since=abc")[0] == 400
    assert call(base, "/api/health")[1]["history"]["entries"] == 1
    assert Fake.sent == []
    srv.shutdown()


def test_models_endpoint_needs_key_and_reads_no_pedal(monkeypatch):
    srv, base = start(monkeypatch)
    monkeypatch.setattr(server, "_models_cache", None)
    assert call(base, "/api/models", key="")[0] == 401
    code, out = call(base, "/api/models")
    assert code == 200 and out["status"] == "beta" and len(out["blocks"]) == 9
    assert sum(b["count"] for b in out["blocks"]) == sum(len(b["models"]) for b in out["blocks"]) > 300
    code, amp = call(base, "/api/models?block=amp")
    assert code == 200 and [b["block"] for b in amp["blocks"]] == ["AMP"] and amp["counts"] == {"AMP": 60}
    marshell = [m for m in amp["blocks"][0]["models"] if m["name"] == "Marshell 50"][0]
    assert marshell["code"] == 55 and marshell["status"] == "pedal-proven" and "Marshall" in marshell["based_on"]
    code, hit = call(base, "/api/models?q=tube%20screamer")
    assert code == 200 and {m["name"] for b in hit["blocks"] for m in b["models"]} == {"Green Drive"}
    assert call(base, "/api/models?block=nope")[0] == 400
    assert Fake.sent == []
    srv.shutdown()


def test_models_endpoint_is_404_when_the_library_is_not_bundled(monkeypatch):
    srv, base = start(monkeypatch)
    monkeypatch.setattr(server, "_models_cache", None)
    monkeypatch.setattr(server, "MODELS_FILES", ["/nonexistent/models.json"])
    assert call(base, "/api/models")[0] == 404
    srv.shutdown()


def test_every_proven_model_code_matches_the_library():
    data = server.load_models()
    proven = {(b["block"].lower(), m["code"]) for b in data["blocks"] for m in b["models"] if m["status"] == "pedal-proven"}
    for slot, codes in server.PROVEN_MODELS.items():
        for c in codes:
            assert (slot, c) in proven, (slot, c)


def test_midi_cc_only_the_arrow_ccs(monkeypatch):
    srv, base = start(monkeypatch)
    code, out = call(base, "/api/midi/cc", {"cc": 22})
    assert code == 200 and out["cc"] == 22 and out["value"] == 127
    assert Fake.sent == [("midi", bytes([0xB0, 22, 127]))]
    assert call(base, "/api/midi/cc", {"cc": 25, "value": 0})[0] == 200
    assert Fake.sent[1] == ("midi", bytes([0xB0, 25, 0]))
    srv.shutdown()


def test_midi_cc_refuses_everything_else(monkeypatch):
    srv, base = start(monkeypatch)
    for body in ({"cc": 21}, {"cc": 48}, {"cc": 77}, {"cc": 26}, {"cc": True}, {}, {"cc": 22, "value": 200},
                 {"cc": "x"}, {"cc": 22, "value": -1}):
        assert call(base, "/api/midi/cc", body)[0] == 400, body
    assert call(base, "/api/midi/cc", {"cc": 22}, key="wrong")[0] == 401
    assert Fake.sent == []
    srv.shutdown()
