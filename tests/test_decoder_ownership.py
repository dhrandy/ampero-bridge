"""Read decoding of the fields the generic two-bytes-per-param layout gets wrong.

Every record here is built from public vendor defaults (published editor defaults and ranges), not
from any real preset. These tests only read bytes. They do not touch writes or the strict gate.
"""
import pytest

import fakepedal as fp
import paramrules
import records

DLY, FX3, CAB, EQ = (records.BLOCK_OFFSETS[k] for k in ("dly", "fx3", "cab", "eq"))


def blank(code_by_slot):
    rec = bytearray(records.RECORD_LEN)
    rec[0], rec[1] = 1, 5
    for slot, code in code_by_slot.items():
        off = records.BLOCK_OFFSETS[slot]
        rec[off], rec[off + 1], rec[off + 2] = 1, code >> 7, code & 0x7F
    return rec


# --- DLY Feedback and Time ---------------------------------------------------------------

@pytest.mark.parametrize("feedback, time_raw", [(50, 430), (20, 480), (40, 430), (50, 280), (50, 1592), (0, 0), (100, 4000)])
def test_dly_feedback_is_one_byte_and_time_owns_the_wide_bytes(feedback, time_raw):
    rec = blank({"dly": 0})
    rec[DLY + 6], rec[DLY + 7], rec[DLY + 8] = feedback, time_raw >> 7, time_raw & 0x7F
    p = records.block_fields(bytes(rec), "dly")["params"]
    assert p[1] == feedback
    assert p[2] == time_raw
    assert len(p) == records.PARAM_SLOTS


def test_dly_real_bytes_for_a_default_delay_read_in_range():
    # bytes 332..334 of a delay at its published defaults: Feedback 50, Time 430 (3 * 128 + 46)
    rec = blank({"dly": 0})
    rec[DLY + 6:DLY + 9] = bytes([0x32, 0x03, 0x2E])
    p = records.block_fields(bytes(rec), "dly")["params"]
    assert (p[1], p[2]) == (50, 430)
    assert 0 <= p[1] <= 100          # the old read gave 818 here


def test_dly_neighbours_are_not_disturbed():
    rec = blank({"dly": 0})
    rec[DLY + 4], rec[DLY + 5] = 40, 0
    rec[DLY + 6:DLY + 9] = bytes([50, 3, 46])
    rec[DLY + 10], rec[DLY + 11] = 1, 0
    p = records.block_fields(bytes(rec), "dly")["params"]
    assert p[0] == 40 and p[3] == 1


def test_every_delay_model_in_the_map_names_feedback_then_time():
    import json, os
    path = os.path.join(os.path.dirname(__file__), "..", "docs", "param-map.json")
    models = json.load(open(path))["blocks"]["dly"]["models"]
    assert len(models) >= 17
    for code, m in models.items():
        names = (m["params"]["1"]["name"], m["params"]["2"]["name"])
        assert names == ("Feedback", "Time"), (code, m["name"])


# --- Sweller Attack --------------------------------------------------------------------

def test_sweller_attack_is_14_bit_with_high_half_before_slot_zero():
    rec = blank({"fx3": records.SWELLER_FX3})
    raw = 920                                  # 1000 ms shown, raw = ms - 80
    rec[FX3 + 3], rec[FX3 + 4] = raw >> 7, raw & 0x7F
    assert (rec[FX3 + 3], rec[FX3 + 4]) == (7, 24)
    f = records.block_fields(bytes(rec), "fx3")
    assert f["code"] == 75 and f["params"][0] == raw   # the old read gave 24


def test_other_fx3_models_keep_the_generic_read():
    rec = blank({"fx3": 6})
    rec[FX3 + 3], rec[FX3 + 4], rec[FX3 + 5] = 7, 24, 3
    assert records.block_fields(bytes(rec), "fx3")["params"][0] == 24 | (3 << 8)


# --- CAB Position Z and the cuts ---------------------------------------------------------

def test_cab_z_is_its_own_byte_and_cuts_are_two_7bit_halves():
    rec = blank({"cab": 5})
    z, low, high = 100, 1981, 1801
    rec[CAB + 12] = z
    rec[CAB + 13], rec[CAB + 14] = low >> 7, low & 0x7F
    rec[CAB + 15], rec[CAB + 16] = high >> 7, high & 0x7F
    p = records.block_fields(bytes(rec), "cab")["params"]
    assert p[4] == z                 # not z + 128 * (low cut high half)
    assert p[5] == low and p[6] == high


def test_cab_z_does_not_move_when_the_low_cut_changes():
    a, b = blank({"cab": 5}), blank({"cab": 5})
    for rec, low in ((a, 0), (b, 1500)):
        rec[CAB + 12] = 50
        rec[CAB + 13], rec[CAB + 14] = low >> 7, low & 0x7F
    za = records.block_fields(bytes(a), "cab")["params"][4]
    zb = records.block_fields(bytes(b), "cab")["params"][4]
    assert za == zb == 50


def test_cab_rules_now_match_read_fields_but_bulk_copy_stays_gated():
    # New single writes are opt-in; bulk copy/restore remains unchanged.
    for p in (4, 5, 6):
        assert paramrules.OVERRIDES[("cab", "ALL", p)]["trust"] == paramrules.UNVERIFIED
    d = {"slot": "cab", "field": "param", "index": 4, "want": 50}
    assert records.why_not(d, {}, True) == "CAB position Z and the cuts are not writable yet"


# --- Para EQ Volume ----------------------------------------------------------------------

def test_para_eq_has_a_fifteenth_param_that_is_the_last_byte_of_its_block():
    rec = blank({"eq": records.PARA_EQ, "fx3": 6})
    rec[EQ + 32] = 50
    f = records.block_fields(bytes(rec), "eq")
    assert len(f["params"]) == 15 and f["params"][14] == 50
    assert EQ + 32 + 1 == records.BLOCK_OFFSETS["fx3"]      # the next byte is FX3's state byte


def test_para_eq_volume_does_not_read_the_next_blocks_state_byte():
    rec = blank({"eq": records.PARA_EQ, "fx3": 6})
    rec[EQ + 32] = 70
    assert rec[FX3] == 1
    assert records.block_fields(bytes(rec), "eq")["params"][14] == 70      # not 70 + 256


def test_other_eq_models_keep_fourteen_params():
    for code in (0, 1, 2, 3, 5, 6):
        rec = blank({"eq": code})
        assert len(records.block_fields(bytes(rec), "eq")["params"]) == records.PARAM_SLOTS


# --- nothing here loosens the gate -------------------------------------------------------

def test_slapback_range_is_documented_but_not_yet_write_verified():
    assert paramrules.OVERRIDES[("dly", 9, 2)]["hi"] == 280
    assert paramrules.OVERRIDES[("dly", 9, 2)]["trust"] == paramrules.UNVERIFIED


def test_diff_between_two_delays_now_compares_time_not_feedback():
    a = fp.make_record(1, "A", {"dly": (True, 0, [40, 50, 430, 0])})
    b = fp.make_record(1, "B", {"dly": (True, 0, [40, 50, 280, 0])})
    ds = records.diffs(a, b, ["dly"])
    assert [(d["index"], d["want"], d["have"]) for d in ds] == [(2, 430, 280)]
