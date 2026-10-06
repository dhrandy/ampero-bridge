"""Favorites, block copy, backup, restore, .prst inspection and CORS, against the fake pedal."""
import base64
import json
import os
import struct
import tempfile
import threading
import time
import urllib.request
from urllib.error import HTTPError

os.environ.setdefault("API_KEY", "k")
os.environ.setdefault("AMPERO_DATA_DIR", tempfile.mkdtemp())

import pytest  # noqa: E402

import ampero_mini as am  # noqa: E402
import fakepedal as fp  # noqa: E402
import records  # noqa: E402
import server  # noqa: E402
import usbmidi as usb  # noqa: E402

KEY = os.environ["API_KEY"]


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "WRITE_GAP", 0.0)
    monkeypatch.setattr(server, "WRITE_SAVE_GAP", 0.0)
    monkeypatch.setattr(server, "PEDAL_SETTLE", 0.0)
    monkeypatch.setattr(server, "PATCH_COUNT", 4)
    monkeypatch.setattr(server, "gate", server.WriteGate())
    monkeypatch.setattr(server, "BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(server, "favorites", server.Favorites(str(tmp_path / "fav.json")))
    monkeypatch.setattr(server, "last_job", None)
    monkeypatch.setattr(usb, "Pedal", fp.Pedal)
    monkeypatch.setattr(usb, "is_present", lambda: fp.Pedal.present)
    fp.Pedal.reset(fp.sample_patches())
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def req(base, path, body=None, key=KEY, headers=None, method=None):
    h = {"X-Api-Key": key, **(headers or {})}
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    r = urllib.request.Request(base + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"{}"), resp.headers
    except HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), e.headers


def wait_job(base, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        _, job, _ = req(base, "/api/backup/status")
        if job["state"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


# --- favorites ---------------------------------------------------------------------------

def test_favorites_star_unstar_and_persist(bridge, tmp_path):
    assert req(bridge, "/api/favorites")[1] == {"patches": [], "models": [], "count": 0}
    s, out, _ = req(bridge, "/api/favorites", {"kind": "patch", "id": "P26-1"})
    assert s == 200 and out["patches"][0]["index"] == 75 and out["patches"][0]["label"] == "P26-1"
    req(bridge, "/api/favorites", {"kind": "model", "id": "amp:55"})
    req(bridge, "/api/favorites", {"kind": "patch", "id": 3})
    got = req(bridge, "/api/favorites")[1]
    assert [p["index"] for p in got["patches"]] == [3, 75] and got["models"][0]["id"] == "AMP:55"
    # a fresh Favorites object reads the same file: this is what survives a restart
    again = server.Favorites(str(tmp_path / "fav.json")).listing()
    assert again["count"] == 3
    out = req(bridge, "/api/favorites", {"kind": "patch", "id": 75, "starred": False})[1]
    assert [p["index"] for p in out["patches"]] == [3]


def test_favorites_starring_twice_keeps_one_and_bad_input_is_400(bridge):
    req(bridge, "/api/favorites", {"id": 5})
    out = req(bridge, "/api/favorites", {"id": 5})[1]
    assert out["count"] == 1
    for bad in ({"kind": "amp", "id": 1}, {"kind": "patch"}, {"kind": "patch", "id": 500},
                {"kind": "model", "id": "nope"}, {"kind": "model", "id": "AMP:x"}, {"id": 1, "starred": "yes"}):
        assert req(bridge, "/api/favorites", bad)[0] == 400, bad
    assert req(bridge, "/api/favorites", {"id": 1}, key="bad")[0] == 401
    assert req(bridge, "/api/favorites", key="bad")[0] == 401


def test_favorites_limit(bridge, monkeypatch):
    monkeypatch.setattr(server, "FAVORITES_MAX", 2)
    for i in (0, 1):
        assert req(bridge, "/api/favorites", {"id": i})[0] == 200
    assert req(bridge, "/api/favorites", {"id": 2})[0] == 400
    assert req(bridge, "/api/favorites", {"id": 1, "starred": False})[0] == 200


# --- block copy --------------------------------------------------------------------------

def test_copy_needs_confirm_and_touches_nothing_without_it(bridge):
    s, out, _ = req(bridge, "/api/block/copy", {"from": 0, "to": 1, "block": "dly"})
    assert s == 400 and "COPY DLY P1-1 TO P1-2" in out["error"]
    assert fp.Pedal.log == []


def test_copy_dry_run_reports_and_changes_nothing(bridge):
    s, out, _ = req(bridge, "/api/block/copy", {"from": 0, "to": 1, "block": "dly", "dry_run": True})
    assert s == 200 and out["dry_run"] is True
    fields = {(d["field"], d.get("index")) for d in out["would_write"]}
    assert ("power", None) in fields and ("param", 0) in fields and ("param", 2) in fields
    assert not any(kind == "sysex" and am.parse_frame(f)[1][0] == 0x10 and am.parse_frame(f)[1][3] in (1, 2)
                   for kind, f in fp.Pedal.log)
    assert fp.Pedal.store[1] == fp.sample_patches()[1]


def test_copy_block_onto_edit_buffer_not_saved(bridge):
    body = {"from": 0, "to": 1, "block": "dly", "confirm": "COPY DLY P1-1 TO P1-2"}
    s, out, _ = req(bridge, "/api/block/copy", body)
    assert s == 200 and out["ok"] is True and out["saved"] is False and out["written"] > 0
    assert out["stuck"] == [] and "POST /api/patch/save" in out["note"]
    live = records.block_fields(fp.Pedal.edit, "dly")
    assert live["on"] is True and live["params"][:4] == [25, 15, 110, 1]
    assert fp.Pedal.store[1] == fp.sample_patches()[1], "the stored patch must not change without a save"
    # the other blocks of the target were not touched
    now, before = fp.Pedal.edit, fp.sample_patches()[1]
    assert records.block_fields(now, "amp") == records.block_fields(before, "amp")
    assert records.block_fields(now, "rvb") == records.block_fields(before, "rvb")
    assert now[4:22] == before[4:22]


def test_copy_changes_model_first_then_knobs(bridge):
    body = {"from": 3, "to": 1, "block": "fx1", "confirm": "COPY FX1 P2-1 TO P1-2"}
    s, out, _ = req(bridge, "/api/block/copy", body)
    assert s == 200 and out["ok"], out
    sysex = [am.parse_frame(f)[1] for kind, f in fp.Pedal.log if kind == "sysex"]
    first_model = next(i for i, b in enumerate(sysex) if b[0] == 0x10 and b[3] == 1 and len(b) == 6)
    first_param = next(i for i, b in enumerate(sysex) if b[0] == 0x10 and b[3] == 2)
    assert first_model < first_param
    assert records.block_fields(fp.Pedal.edit, "fx1")["code"] == 137


def test_copy_refuses_unwritable_blocks_and_same_patch(bridge):
    for bad in ({"block": "tuner"}, {"to": 0}):
        body = {"from": 0, "to": 1, "block": "dly", "dry_run": True, **bad}
        assert req(bridge, "/api/block/copy", body)[0] == 400, bad


def test_copy_reports_what_it_cannot_write(bridge):
    # source delay time is 300 (more than the 127 a param write carries)
    patches = fp.sample_patches()
    patches[0] = fp.make_record(0, "LONG DELAY", {"dly": (True, 9, [25, 15, 300, 1])})
    fp.Pedal.reset(patches)
    s, out, _ = req(bridge, "/api/block/copy", {"from": 0, "to": 1, "block": "dly",
                                                 "confirm": "COPY DLY P1-1 TO P1-2"})
    assert s == 200 and out["ok"] is False
    assert [(d["index"], d["want"]) for d in out["stuck"]] == [(2, 300)]
    assert "above the 127" in out["stuck"][0]["reason"]


def test_copy_refuses_unproven_model(bridge):
    patches = fp.sample_patches()
    patches[0] = fp.make_record(0, "ODD", {"dly": (True, 99, [1, 2, 3, 4])})
    fp.Pedal.reset(patches)
    s, out, _ = req(bridge, "/api/block/copy", {"from": 0, "to": 1, "block": "dly", "dry_run": True})
    assert s == 200 and out["stuck"][0]["field"] == "model" and "not proven" in out["stuck"][0]["reason"]
    assert not any(d["field"] == "model" for d in out["would_write"])


def test_copy_when_pedal_missing_is_503(bridge):
    fp.Pedal.present = False
    s, out, _ = req(bridge, "/api/block/copy", {"from": 0, "to": 1, "block": "dly", "dry_run": True})
    assert s == 503


def test_copy_while_something_else_runs_is_409(bridge):
    assert server.workflow.acquire(blocking=False)
    try:
        s, out, _ = req(bridge, "/api/block/copy", {"from": 0, "to": 1, "block": "dly", "dry_run": True})
        assert s == 409 and "already running" in out["error"]
        assert req(bridge, "/api/backup", {})[0] == 409
    finally:
        server.workflow.release()


# --- backup and restore ------------------------------------------------------------------

def make_backup(bridge):
    s, job, _ = req(bridge, "/api/backup", {})
    assert s == 200 and job["kind"] == "backup" and job["total"] == 4
    job = wait_job(bridge)
    assert job["state"] == "done", job
    return job["result"]


def test_backup_walks_patches_writes_a_file_and_returns_to_the_start(bridge):
    fp.Pedal.cur, fp.Pedal.edit = 2, fp.Pedal.store[2]
    result = make_backup(bridge)
    assert result["patches"] == 4 and result["skipped"] == []
    assert fp.Pedal.cur == 2, "the pedal goes back to the patch it was on"
    lst = req(bridge, "/api/backups")[1]
    assert lst["count"] == 1 and lst["backups"][0]["name"] == result["name"]
    s, body, headers = req(bridge, "/api/backups/" + result["name"])
    assert s == 200 and "attachment" in headers["Content-Disposition"]
    assert body["format"] == records.BACKUP_FORMAT and len(body["patches"]) == 4
    assert body["patches"][1]["name"] == "CRUNCH RHYTHM"
    assert bytes.fromhex(body["patches"][3]["record_hex"]) == fp.sample_patches()[3]
    assert "pedal" in body and "WADE" not in json.dumps(body)


def test_backup_names_are_checked(bridge):
    for bad in ("../../etc/passwd", "x.json", "ampero-backup-1.json"):
        assert req(bridge, "/api/backups/" + bad.replace("/", "%2F"))[0] == 404
    assert req(bridge, "/api/backups/ampero-backup-20260101-000000.json")[0] == 404


def test_backup_of_chosen_patches_and_unreadable_ones_are_listed(bridge):
    s, job, _ = req(bridge, "/api/backup", {"patches": [1, "P1-1", 120]})
    assert s == 200 and job["total"] == 3
    result = wait_job(bridge)["result"]
    assert result["patches"] == 2
    assert [x["index"] for x in result["skipped"]] == [120]


def test_backup_fails_clearly_when_pedal_is_gone(bridge):
    fp.Pedal.present = False
    req(bridge, "/api/backup", {"patches": [0]})
    job = wait_job(bridge)
    assert job["state"] == "failed" or "nothing was saved" in (job["error"] or "")


def test_restore_dry_run_changes_nothing_and_says_what_differs(bridge):
    result = make_backup(bridge)
    backup = req(bridge, "/api/backups/" + result["name"])[1]
    # change patch 1 on the "pedal" after the backup
    fp.Pedal.store[1] = fp.make_record(1, "CRUNCH RHYTHM", {"amp": (True, 55, [99, 50, 55, 45, 60, 55])})
    before = dict(fp.Pedal.store)
    s, job, _ = req(bridge, "/api/restore", {"backup": backup})
    assert s == 200 and job["kind"] == "restore-check"
    res = wait_job(bridge)["result"]
    assert res["apply"] is False
    rows = {r["index"]: r for r in res["patches"]}
    assert rows[0]["status"] == "same" and rows[1]["status"] == "differs" and rows[3]["status"] == "same"
    assert any(d["field"] == "param" and d["slot"] == "amp" and d["want"] == 55 for d in rows[1]["would_write"])
    assert fp.Pedal.store == before
    assert not any(b[0] == 0x10 and b[1] == 0 for kind, f in fp.Pedal.log if kind == "sysex"
                   for b in [am.parse_frame(f)[1]]), "no save in a dry run"


def test_restore_needs_the_exact_confirmation(bridge):
    backup = req(bridge, "/api/backups/" + make_backup(bridge)["name"])[1]
    s, out, _ = req(bridge, "/api/restore", {"backup": backup, "apply": True, "patches": [1]})
    assert s == 400 and "RESTORE 1 PATCHES" in out["error"]
    s, out, _ = req(bridge, "/api/restore", {"backup": backup, "apply": True, "patches": [1], "confirm": "RESTORE 2 PATCHES"})
    assert s == 400


def test_restore_puts_a_changed_patch_back_and_saves_it(bridge):
    name = make_backup(bridge)["name"]
    original = fp.sample_patches()[1]
    fp.Pedal.store[1] = fp.make_record(1, "SOMETHING ELSE", {
        "amp": (True, 55, [99, 50, 55, 45, 60, 55]), "fx2": (False, 9, [35, 55, 50, 60, 55]),
        "dly": (True, 9, [10, 10, 90, 0]), "rvb": (True, 4, [15, 30, 50, 0])}, level=80)
    fp.Pedal.cur, fp.Pedal.edit = 0, fp.Pedal.store[0]
    s, _, _ = req(bridge, "/api/restore", {"name": name, "apply": True, "patches": ["P1-2"], "confirm": "RESTORE 1 PATCHES"})
    assert s == 200
    res = wait_job(bridge)["result"]
    row = res["patches"][0]
    assert row["status"] == "restored", row
    assert row["written"] > 0 and row["stuck"] == []
    restored = fp.Pedal.store[1]
    assert restored[4:22] == original[4:22], "the name is saved too"
    for slot in ("amp", "fx2", "dly", "rvb"):
        assert records.block_fields(restored, slot) == records.block_fields(original, slot), slot
    assert restored[records.LEVEL_OFFSET] == original[records.LEVEL_OFFSET]
    assert fp.Pedal.cur == 0, "back on the patch the pedal was on"


def test_restore_does_not_save_a_patch_it_could_not_fully_restore(bridge):
    name = make_backup(bridge)["name"]
    backup = json.loads(open(os.path.join(server.BACKUP_DIR, name)).read())
    # in the file, patch 1 has a delay time of 300, more than the 127 a param write carries
    changed = fp.make_record(1, "CRUNCH RHYTHM", {"amp": (True, 55, [55, 50, 55, 45, 60, 55]), "dly": (True, 9, [25, 15, 300, 1])})
    backup["patches"][1]["record_hex"] = changed.hex()
    body = {"backup": backup, "apply": True, "patches": [1], "confirm": "RESTORE 1 PATCHES"}
    req(bridge, "/api/restore", body)
    row = wait_job(bridge)["result"]["patches"][0]
    assert row["status"] == "not-saved"
    assert [d["slot"] for d in row["stuck"]] == ["dly"] and "above the 127" in row["stuck"][0]["reason"]
    assert fp.Pedal.store[1] == fp.sample_patches()[1]
    req(bridge, "/api/restore", {**body, "allow_partial": True})
    row = wait_job(bridge)["result"]["patches"][0]
    assert row["status"] == "saved-partial"
    assert records.block_fields(fp.Pedal.store[1], "dly")["on"] is True   # the part that could be written did go through


def test_restore_rejects_bad_files(bridge):
    good = fp.sample_patches()[0].hex()
    cases = [
        {"backup": "text"},
        {"backup": {"format": "something"}},
        {"backup": {"format": records.BACKUP_FORMAT, "version": 9, "patches": [{"index": 0, "record_hex": good}]}},
        {"backup": {"format": records.BACKUP_FORMAT, "version": 1, "patches": []}},
        {"backup": {"format": records.BACKUP_FORMAT, "version": 1, "patches": [{"index": 1, "record_hex": good}]}},
        {"backup": {"format": records.BACKUP_FORMAT, "version": 1, "patches": [{"index": 0, "record_hex": "zz"}]}},
        {"backup": {"format": records.BACKUP_FORMAT, "version": 1, "patches": [{"index": 0, "record_hex": good[:-2]}]}},
        {"backup": {"format": records.BACKUP_FORMAT, "version": 1, "patches": [{"index": 0, "record_hex": good}] * 2}},
        {},
    ]
    for body in cases:
        assert req(bridge, "/api/restore", body)[0] == 400, body
    assert req(bridge, "/api/restore", {"name": "ampero-backup-20260101-000000.json"})[0] == 404
    ok = {"backup": {"format": records.BACKUP_FORMAT, "version": 1, "patches": [{"index": 0, "record_hex": good}]}}
    assert req(bridge, "/api/restore", {**ok, "patches": [5]})[0] == 400, "asked for a patch the file does not have"


def test_restore_takes_a_single_patch_dump_from_api_patch_current(bridge):
    s, cur, _ = req(bridge, "/api/patch/current")
    assert s == 200
    s, job, _ = req(bridge, "/api/restore", {"backup": cur})
    assert s == 200 and job["total"] == 1
    assert wait_job(bridge)["result"]["patches"][0]["status"] == "same"


def test_restore_uploads_may_be_big_but_other_posts_may_not(bridge):
    pad = "x" * 10_000
    assert req(bridge, "/api/restore", {"backup": {"format": "no", "pad": pad}})[0] == 400
    s, out, _ = req(bridge, "/api/notes", {"patch": 1, "note": pad})
    assert s == 400 and "too large" in out["error"]


# --- .prst -------------------------------------------------------------------------------

def fake_prst(names):
    """A container laid out the way docs/prst.md describes. The patch bodies are filler."""
    blocks = []
    for pos, name in enumerate(names):
        body = b"MRAP" + struct.pack("<I", 40) + b"\x01" + bytes([pos]) + b"\0\0" + name.encode().ljust(16, b"\0") + bytes(24)
        blocks.append(body)
    head = b"TSRP" + struct.pack("<I", 0) + b"PM0\0\0" + b"\x01" + struct.pack("<H", len(names)) + bytes(16)
    offset = len(head) + 8 * len(names)
    table = b""
    for b in blocks:
        table += struct.pack("<II", offset, len(b))
        offset += len(b)
    return head + table + b"".join(blocks) + b"\x00\x00\x00"


def post_prst(base, raw, name="x.prst"):
    return req(base, "/api/import/prst", {"filename": name, "data": base64.b64encode(raw).decode()})


def test_prst_container_is_listed_but_never_importable(bridge):
    s, out, _ = post_prst(bridge, fake_prst(["First", "Second"]))
    assert s == 200 and out["container"] == "TSRP" and out["count"] == 2
    assert [p["name"] for p in out["patches"]] == ["First", "Second"]
    assert out["importable"] is False and "does not guess" in out["reason"]


def test_prst_bad_files_get_a_plain_reason(bridge):
    good = fake_prst(["A"])
    cases = {b"": "empty", b"hello world, not a preset file at all": "TSRP", good[:20]: "cut off",
             good[:36]: "cut off", good[:-20]: "outside the file"}
    for raw, word in cases.items():
        s, out, _ = post_prst(bridge, raw)
        assert s == 200 and out["importable"] is False and word in out["error"], (raw[:10], out)
    broken = bytearray(good)
    broken[broken.index(b"MRAP")] = ord("X")
    assert "MRAP" in post_prst(bridge, bytes(broken))[1]["error"]
    assert req(bridge, "/api/import/prst", {"data": "!!!"})[0] == 400


# --- CORS --------------------------------------------------------------------------------

def test_cors_is_off_unless_the_origin_is_listed(bridge, monkeypatch):
    origin = "https://example.github.io"
    s, _, h = req(bridge, "/api/favorites", headers={"Origin": origin})
    assert "Access-Control-Allow-Origin" not in h
    monkeypatch.setattr(server, "CORS_ORIGINS", {origin})
    s, _, h = req(bridge, "/api/favorites", headers={"Origin": origin})
    assert h["Access-Control-Allow-Origin"] == origin and h["Vary"] == "Origin"
    s, _, h = req(bridge, "/api/favorites", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in h
    s, _, h = req(bridge, "/api/favorites", key="bad", headers={"Origin": origin})
    assert s == 401 and h["Access-Control-Allow-Origin"] == origin, "browsers need to read the 401 too"


def test_preflight_answers_without_a_key(bridge, monkeypatch):
    origin = "https://example.github.io"
    monkeypatch.setattr(server, "CORS_ORIGINS", {origin})
    r = urllib.request.Request(bridge + "/api/favorites", method="OPTIONS",
                               headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                        "Access-Control-Request-Headers": "x-api-key,content-type"})
    with urllib.request.urlopen(r, timeout=5) as resp:
        assert resp.status == 204
        assert resp.headers["Access-Control-Allow-Origin"] == origin
        assert "X-Api-Key" in resp.headers["Access-Control-Allow-Headers"]
    r = urllib.request.Request(bridge + "/api/favorites", method="OPTIONS", headers={"Origin": "https://evil.example"})
    with urllib.request.urlopen(r, timeout=5) as resp:
        assert resp.status == 204 and "Access-Control-Allow-Origin" not in resp.headers
