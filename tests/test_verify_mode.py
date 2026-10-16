"""Verify mode: off by default, strict path untouched, documented ranges only, synced Rate on divisions.

All records are synthetic. No test here talks to a real pedal.
"""
import json
import os
import tempfile
import threading
import urllib.request
from urllib.error import HTTPError

os.environ.setdefault("API_KEY", "k")
os.environ.setdefault("AMPERO_DATA_DIR", tempfile.mkdtemp())

import pytest  # noqa: E402

import ampero_mini as am  # noqa: E402
import fakepedal as fp  # noqa: E402
import paramrules as pr  # noqa: E402
import records  # noqa: E402
import server  # noqa: E402
import usbmidi as usb  # noqa: E402

KEY = os.environ["API_KEY"]
FX3 = records.BLOCK_OFFSETS["fx3"]


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "WRITE_GAP", 0.0)
    monkeypatch.setattr(server, "WRITE_SAVE_GAP", 0.0)
    monkeypatch.setattr(server, "PEDAL_SETTLE", 0.0)
    monkeypatch.setattr(server, "gate", server.WriteGate())
    monkeypatch.setattr(usb, "Pedal", fp.Pedal)
    monkeypatch.setattr(usb, "is_present", lambda: fp.Pedal.present)
    fp.Pedal.reset({0: fp.make_record(0, "DEMO", {
        "fx3": (True, 7, [50, 40, 30, 20, 0]),          # Jetter N: Rate p1, Sync p4
        "fx1": (True, 45, [2, 50, 100]),                # Classic PS
        "eq": (True, 4, [0] * 14)})})
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture
def verify_on(monkeypatch):
    monkeypatch.setattr(pr, "VERIFY_ENABLED", True)


def post(base, body):
    r = urllib.request.Request(base + "/api/param", data=json.dumps(body).encode(), headers={"X-Api-Key": KEY})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as e:
        return e.code, json.loads(e.read())


def set_sync(on):
    buf = bytearray(fp.Pedal.edit)
    buf[FX3 + 4 + 2 * 4] = 1 if on else 0
    fp.Pedal.edit = bytes(buf)


def reason(out):
    return out.get("detail", out).get("reason") if isinstance(out, dict) else None


def bad(*args, **kw):
    with pytest.raises(pr.ValueRejected) as e:
        pr.validate_verify(*args, **kw)
    return e.value.extra["reason"]


# --- off by default, strict untouched -------------------------------------------------------

def test_verify_mode_is_off_unless_the_env_var_is_set():
    assert pr.VERIFY_ENABLED is False
    assert bad("eq", 4, 14, 50) == "verify_mode_off"


def test_a_verify_write_is_refused_when_the_mode_is_off(bridge):
    code, out = post(bridge, {"slot": "eq", "model_code": 4, "param": 14, "value": 50, "verify": True})
    assert code == 422 and "off on this bridge" in json.dumps(out)
    assert all(kind != "sysex" for kind, _ in fp.Pedal.log)


def test_strict_rules_do_not_change_when_verify_mode_is_on(verify_on):
    for slot, code, p, v, why in (("eq", 4, 13, 12, "blocked_param"), ("eq", 4, 14, 50, "blocked_param"),
                                  ("fx1", 45, 1, 50, "blocked_param"), ("fx1", 45, 2, 50, "blocked_param"),
                                  ("fx1", 45, 0, 6, "not_in_enum"), ("rvb", 9, 3, 65, "unverified")):
        with pytest.raises(pr.ValueRejected) as e:
            pr.validate(slot, code, p, v)
        assert e.value.extra["reason"] == why, (slot, code, p)
    with pytest.raises(pr.ValueRejected) as e:
        pr.validate("fx3", 5, 1, 50)                                  # unverified still needs the flag
    assert e.value.extra["reason"] == "unverified"


def test_strict_endpoint_ignores_a_missing_verify_flag_even_with_the_mode_on(bridge, verify_on):
    assert post(bridge, {"slot": "eq", "model_code": 4, "param": 14, "value": 50})[0] == 422


def test_rules_view_is_unchanged_when_off_and_shows_verify_info_when_on(monkeypatch):
    assert "verify_range" not in pr.rules_view("eq", 4)["params"]["14"]
    assert pr.rules_view("eq", 4)["verify_mode"] is False
    monkeypatch.setattr(pr, "VERIFY_ENABLED", True)
    v = pr.rules_view("eq", 4)
    assert v["verify_mode"] is True and v["params"]["14"]["verify_range"] == {"min": 0, "max": 100}
    assert v["params"]["14"]["kind"] == "blocked"                      # the strict rule itself is the same
    assert pr.rules_view("fx3", 7)["params"]["1"]["sync_param"] == 4


# --- documented ranges only -----------------------------------------------------------------

@pytest.mark.parametrize("slot, code, p, lo, hi", [("fx1", 45, 1, 0, 100), ("fx1", 45, 2, 0, 100),
                                                    ("eq", 4, 13, 0, 24), ("eq", 4, 14, 0, 100)])
def test_documented_but_unswept_fields_take_only_their_documented_range(verify_on, slot, code, p, lo, hi):
    assert pr.validate_verify(slot, code, p, lo) == lo
    assert pr.validate_verify(slot, code, p, hi) == hi
    assert bad(slot, code, p, hi + 1) == "out_of_range"
    assert bad(slot, code, p, -1) == "out_of_range"


def test_enum_rules_still_apply(verify_on):
    assert bad("fx1", 45, 0, 6) == "not_in_enum"                      # Classic PS Range stops at 5
    assert pr.validate_verify("fx1", 77, 3, 65) == 65  # confirmed knob, not Mode


def test_new_fields_are_available_in_verify_mode_with_bounded_ranges(verify_on):
    for p, hi in ((4, 100), (5, 1981), (6, 1801)):
        assert pr.validate_verify("cab", 5, p, hi) == hi
        assert bad("cab", 5, p, hi + 1) == "out_of_range"
    assert pr.validate_verify("fx3", 75, 0, 3920) == 3920
    assert pr.validate_verify("dly", 3, 2, 3980, read_sync=lambda p: 0) == 3980
    assert bad("dly", 3, 2, 50, read_sync=lambda p: 1) == "not_a_division"
    assert pr.validate_verify("dly", 3, 2, 2388, read_sync=lambda p: 1) == 2388
    assert bad("dly", 3, 2, 50) == "sync_unknown"
    # Backmask shares the 0-3980 division grid with Sync on (hand capture 2026-10-16);
    # its 1980 ms maximum still binds with Sync off.
    assert bad("dly", 6, 2, 1980, read_sync=lambda p: 1) == "not_a_division"
    assert pr.validate_verify("dly", 6, 2, 3980, read_sync=lambda p: 1) == 3980
    assert pr.validate_verify("dly", 6, 2, 0, read_sync=lambda p: 1) == 0
    assert bad("dly", 6, 2, 2388, read_sync=lambda p: 0) == "over_unsynced_max"
    assert pr.validate_verify("dly", 6, 2, 1980, read_sync=lambda p: 0) == 1980
    # Models sharing Analog Eko's 0-3980 Time layout take the same division table.
    assert pr.validate_verify("dly", 8, 2, 796, read_sync=lambda p: 1) == 796
    assert pr.validate_verify("dly", 16, 2, 0, read_sync=lambda p: 1) == 0
    assert bad("dly", 8, 2, 50, read_sync=lambda p: 1) == "not_a_division"
    assert bad("dly", 16, 2, 3980) == "sync_unknown"


def test_no_range_means_no_write(verify_on):
    blocked = [k for k, r in pr.RULES.items() if r["kind"] == "blocked" and not r.get("verify_rule")]
    for slot, code, p in blocked:
        with pytest.raises(pr.ValueRejected):
            pr.validate_verify(slot, 0 if code == "ALL" else code, p, 1)


def test_unknown_param_slot_and_model_are_refused(verify_on):
    assert bad("fx3", 7, 99, 1) == "unknown_param"
    assert bad("tuner", 7, 1, 1) == "unknown_slot"
    assert bad("fx3", 9999, 1, 1) == "unknown_param"


# --- synced Rate ------------------------------------------------------------------------------

def test_sync_pairs_come_from_the_map(verify_on):
    pairs = {k: r["sync_param"] for k, r in pr.RULES.items() if r.get("sync_param") not in (None, pr.UNPAIRED)}
    assert len(pairs) >= 44
    assert pairs[("fx3", 7, 1)] == 4 and pairs[("fx3", 0, 1)] == 3
    assert pairs[("fx3", 8, 1)] == 5 and pairs[("fx3", 8, 4)] == 6      # Trem Jet: Flg and Trm each have their own
    for (slot, code, p), sp in pairs.items():
        rate, sync = pr.RULES[(slot, code, p)]["name"], pr.RULES[(slot, code, sp)]["name"]
        assert rate == "Time" or (rate.endswith("Rate") and sync == rate[:-4] + "Sync")


def test_a_rate_the_map_cannot_pair_is_refused(verify_on):
    unpaired = [k for k, r in pr.RULES.items() if r.get("sync_param") == pr.UNPAIRED]
    assert {pr.RULES[k]["model"] for k in unpaired} >= {"Sweep Eko", "2290 Mod"}
    for slot, code, p in unpaired:
        assert bad(slot, code, p, 10, read_sync=lambda q: 0) in ("sync_unknown", "wide_param")


def test_synced_rate_takes_only_division_steps(verify_on):
    assert pr.validate_verify("fx3", 7, 1, 70, read_sync=lambda p: 1) == 70
    assert bad("fx3", 7, 1, 25, read_sync=lambda p: 1) == "not_a_division"
    assert bad("fx3", 7, 1, 75, read_sync=lambda p: 1) == "not_a_division"


def test_unsynced_rate_is_a_free_knob(verify_on):
    assert pr.validate_verify("fx3", 7, 1, 25, read_sync=lambda p: 0) == 25
    assert bad("fx3", 7, 1, 101, read_sync=lambda p: 0) == "out_of_range"


def test_unreadable_sync_state_refuses_the_rate(verify_on):
    assert bad("fx3", 7, 1, 40, read_sync=lambda p: None) == "sync_unknown"
    assert bad("fx3", 7, 1, 40) == "sync_unknown"


# --- through the HTTP endpoint ------------------------------------------------------------------

def last_param_frames():
    """The param writes the fake pedal received (the log also holds the read requests)."""
    out = []
    for kind, f in fp.Pedal.log:
        parsed = am.parse_frame(f) if kind == "sysex" else None
        if parsed and parsed[1][:1] == b"\x10" and len(parsed[1]) > 3 and parsed[1][3] == 0x02:
            out.append(f)
    return out


def test_verify_write_goes_to_the_pedal_with_the_documented_value(bridge, verify_on):
    code, out = post(bridge, {"slot": "eq", "model_code": 4, "param": 14, "value": 50, "verify": True})
    assert code == 200 and out == {"ok": True, "verify": True}
    assert len(last_param_frames()) == 1


def test_verify_write_out_of_range_never_reaches_the_pedal(bridge, verify_on):
    code, _ = post(bridge, {"slot": "eq", "model_code": 4, "param": 13, "value": 25, "verify": True})
    assert code == 422 and last_param_frames() == []


def test_synced_rate_over_http(bridge, verify_on):
    set_sync(True)
    code, out = post(bridge, {"slot": "fx3", "model_code": 7, "param": 1, "value": 25, "verify": True})
    assert code == 422 and last_param_frames() == []
    assert post(bridge, {"slot": "fx3", "model_code": 7, "param": 1, "value": 30, "verify": True})[0] == 200
    set_sync(False)
    assert post(bridge, {"slot": "fx3", "model_code": 7, "param": 1, "value": 25, "verify": True})[0] == 200


def test_rate_write_is_refused_when_the_pedal_holds_a_different_model(bridge, verify_on):
    code, out = post(bridge, {"slot": "fx3", "model_code": 5, "param": 1, "value": 25, "verify": True})
    assert code == 422 and "model_mismatch" in json.dumps(out)
    assert last_param_frames() == []


def test_unproven_model_is_refused_even_with_the_unproven_override(bridge, verify_on, monkeypatch):
    monkeypatch.setattr(server, "ALLOW_UNPROVEN", True)
    code, out = post(bridge, {"slot": "fx3", "model_code": 40, "param": 1, "value": 25, "verify": True})
    assert code == 422 and "not proven" in json.dumps(out)


def test_verify_flag_must_be_literally_true(bridge, verify_on):
    for flag in ("true", 1, "yes"):
        code, _ = post(bridge, {"slot": "eq", "model_code": 4, "param": 14, "value": 50, "verify": flag})
        assert code == 422

@pytest.mark.parametrize('slot,code,p,value', [('dly', 3, 2, 3980), ('fx3', 75, 0, 3920),
    ('cab', 34, 5, 1981), ('cab', 34, 6, 1801), ('cab', 34, 4, 100), ('fx2', 13, 3, 100)])
def test_opt_in_endpoint_roundtrip_uses_new_field_layout(bridge, verify_on, slot, code, p, value):
    fp.Pedal.reset({0: fp.make_record(0, 'DEMO', {slot: (True, code, [0] * 7)})})
    status, out = post(bridge, {'slot': slot, 'model_code': code, 'param': p, 'value': value, 'verify': True})
    assert status == 200, out
    assert records.block_fields(fp.Pedal.edit, slot)['params'][p] == value
    assert fp.Pedal.store[0] != fp.Pedal.edit  # edit-buffer only, no save


def test_strict_synced_time_cannot_bypass_division_guard(bridge):
    fp.Pedal.reset({0: fp.make_record(0, 'DEMO', {'dly': (True, 3, [30, 40, 430, 1, 0])})})
    status, out = post(bridge, {'slot': 'dly', 'model_code': 3, 'param': 2, 'value': 100,
                               'unverified_ok': True})
    assert status == 422 and 'division' in json.dumps(out)
    assert records.block_fields(fp.Pedal.edit, 'dly')['params'][2] == 430
