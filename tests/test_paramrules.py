import json
import os
import tempfile

os.environ["API_KEY"] = "k"
os.environ["AMPERO_DATA_DIR"] = tempfile.mkdtemp()

import pytest  # noqa: E402

import ampero_mini as am  # noqa: E402
import paramrules as pr  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def bad(slot, code, param, value, reason, **kw):
    with pytest.raises(pr.ValueRejected) as e:
        pr.validate(slot, code, param, value, **kw)
    assert e.value.extra["reason"] == reason, e.value.extra
    return e.value


def test_every_param_in_the_map_has_a_rule_and_no_rule_exceeds_seven_bits():
    with open(os.path.join(HERE, "..", "docs", "param-map.json")) as f:
        m = json.load(f)
    for slot, block in m["blocks"].items():
        for code, model in block["models"].items():
            for p in model["params"]:
                rule = pr.rule_for(slot, 0 if code == "ALL" else int(code), int(p))
                assert rule is not None, (slot, code, p)
                if rule["kind"] == "range":
                    assert 0 <= rule["lo"] <= rule["hi"] <= pr.MAX_RAW
                if rule["kind"] == "enum":
                    assert rule["allowed"] and max(rule["allowed"]) <= pr.MAX_RAW


def test_magic_t_treble_only_takes_0_1_2():
    for slot, code in (("fx1", 77), ("fx2", 13)):
        for v in (0, 1, 2):
            assert pr.validate(slot, code, 3, v) == v
        for v in (3, 50, 65, 100):
            bad(slot, code, 3, v, "not_in_enum")


def test_classic_ps_range_stops_at_5():
    assert pr.validate("fx1", 45, 0, 5) == 5
    bad("fx1", 45, 0, 6, "not_in_enum")
    bad("fx2", 93, 0, 6, "not_in_enum")


def test_out_of_range_and_negative_values_are_refused():
    assert pr.validate("fx1", 0, 0, 100) == 100          # Comprosso sustain, 0-100
    bad("fx1", 0, 0, 101, "out_of_range")
    bad("fx1", 0, 0, -1, "out_of_range")


def test_slapback_time_stays_in_seven_bits():
    assert pr.validate("dly", 9, 2, 110) == 110
    bad("dly", 9, 2, 128, "out_of_range")


def test_wide_params_are_capped_and_not_proven():
    # 2290 Time is raw 0-3980: only the part a 7-bit frame can carry, and only on request.
    bad("dly", 16, 2, 100, "unverified")
    assert pr.validate("dly", 16, 2, 100, unverified_ok=True) == 100
    bad("dly", 16, 2, 480, "out_of_range", unverified_ok=True)
    bad("fx3", 75, 0, 1000, "out_of_range", unverified_ok=True)   # Sweller attack raw is 14-bit


def test_shimmer_range_is_raw_and_unverified():
    bad("rvb", 9, 3, 30, "unverified")
    assert pr.validate("rvb", 9, 3, 30, unverified_ok=True) == 30
    bad("rvb", 9, 3, 101, "out_of_range", unverified_ok=True)


def test_cab_packed_fields_are_blocked_and_basic_ones_are_not():
    assert pr.validate("cab", 34, 1, 50) == 50
    bad("cab", 34, 1, 101, "out_of_range")
    for p in (4, 5, 6):
        bad("cab", 34, p, 10, "blocked_param", unverified_ok=True)


def test_unknown_things_are_refused():
    bad("fx1", 0, 9, 1, "unknown_param")
    bad("fx1", 9999, 0, 1, "unknown_param")
    with pytest.raises(pr.ValueRejected):
        pr.validate("nope", 0, 0, 1)


def test_every_value_the_map_says_was_written_still_passes():
    """Guards against over-blocking: values recorded as live-written must not be refused."""
    with open(os.path.join(HERE, "..", "docs", "param-map.json")) as f:
        m = json.load(f)
    checked = 0
    for slot, block in m["blocks"].items():
        for code, model in block["models"].items():
            for p, entry in model["params"].items():
                if entry["status"] != "write-verified":
                    continue
                for v in entry.get("written") or []:
                    if not isinstance(v, int) or v > pr.MAX_RAW:
                        continue
                    rule = pr.rule_for(slot, 0 if code == "ALL" else int(code), int(p))
                    if rule["kind"] == "blocked":
                        continue
                    pr.validate(slot, 0 if code == "ALL" else int(code), int(p), v, unverified_ok=True)
                    checked += 1
    assert checked > 500


def test_rules_view_lists_a_model():
    out = pr.rules_view("fx1", 77)
    assert out["model"] == "Magic T" and out["params"]["3"]["allowed"] == [0, 1, 2]
    with pytest.raises(LookupError):
        pr.rules_view("fx1", 9999)
    with pytest.raises(am.ProtocolError):
        pr.rules_view("nope", 1)
