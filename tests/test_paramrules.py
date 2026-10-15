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


def test_every_param_in_the_map_has_a_rule_and_ranges_fit_their_encoder():
    with open(os.path.join(HERE, "..", "docs", "param-map.json")) as f:
        m = json.load(f)
    for slot, block in m["blocks"].items():
        for code, model in block["models"].items():
            for p in model["params"]:
                rule = pr.rule_for(slot, 0 if code == "ALL" else int(code), int(p))
                assert rule is not None, (slot, code, p)
                if rule["kind"] == "range":
                    assert 0 <= rule["lo"] <= rule["hi"] <= (16383 if rule.get("encoding") == "14bit" else pr.MAX_RAW)
                if rule["kind"] == "enum":
                    assert rule["allowed"] and max(rule["allowed"]) <= (16383 if rule.get("encoding") == "14bit" else pr.MAX_RAW)


def test_magic_t_treble_fx2_is_proven_and_fx1_stays_unverified():
    for v in (0, 1, 2, 50, 65, 100):
        assert pr.validate("fx2", 13, 3, v) == v
        assert pr.validate("fx1", 77, 3, v, unverified_ok=True) == v
    bad("fx2", 13, 3, 101, "out_of_range")
    bad("fx1", 77, 3, 101, "out_of_range", unverified_ok=True)
    bad("fx1", 77, 3, 65, "unverified")


def test_classic_ps_range_stops_at_5():
    assert pr.validate("fx1", 45, 0, 5) == 5
    bad("fx1", 45, 0, 6, "not_in_enum")
    bad("fx2", 93, 0, 6, "not_in_enum")


def test_out_of_range_and_negative_values_are_refused():
    assert pr.validate("fx1", 0, 0, 100) == 100          # Comprosso sustain, 0-100
    bad("fx1", 0, 0, 101, "out_of_range")
    bad("fx1", 0, 0, -1, "out_of_range")


def test_wide_fields_use_only_captured_or_editor_documented_ranges():
    for slot, code, p, hi in (("dly", 9, 2, 280), ("fx3", 75, 0, 3920)):
        assert pr.validate(slot, code, p, hi, unverified_ok=True) == hi
        bad(slot, code, p, hi + 1, "out_of_range", unverified_ok=True)
        bad(slot, code, p, 100, "unverified")
    # FX2 Sweller Attack and Analog Eko Time were written live and read back exact on 2026-10-14.
    assert pr.validate("fx2", 126, 0, 3920) == 3920
    bad("fx2", 126, 0, 3921, "out_of_range")
    assert pr.validate("dly", 3, 2, 3980, read_sync=lambda p: 0) == 3980
    bad("dly", 3, 2, 3981, "out_of_range")
    bad("dly", 3, 2, 3980, "sync_unknown", unverified_ok=True)
    assert pr.validate("dly", 3, 2, 3980, read_sync=lambda p: 0) == 3980


def test_shimmer_range_is_raw_and_unverified():
    bad("rvb", 9, 3, 30, "unverified")
    assert pr.validate("rvb", 9, 3, 30, unverified_ok=True) == 30
    bad("rvb", 9, 3, 101, "out_of_range", unverified_ok=True)


def test_cab_fields_have_separate_bounded_rules():
    assert pr.validate("cab", 34, 1, 50) == 50
    for p, hi in ((4, 100), (5, 1981), (6, 1801)):
        # Write-verified live on 2026-10-14 (Z, Low Cut, High Cut incl. the off values), so no flag needed.
        assert pr.validate("cab", 34, p, hi) == hi
        bad("cab", 34, p, hi + 1, "out_of_range")


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
                    pr.validate(slot, 0 if code == "ALL" else int(code), int(p), v, unverified_ok=True, read_sync=lambda q: 0)
                    checked += 1
    assert checked > 500


def test_rules_view_lists_a_model():
    out = pr.rules_view("fx1", 77)
    assert out["model"] == "Magic T" and out["params"]["3"]["max"] == 100
    with pytest.raises(LookupError):
        pr.rules_view("fx1", 9999)
    with pytest.raises(am.ProtocolError):
        pr.rules_view("nope", 1)


def test_dockerfile_ships_the_editor_parameter_file():
    # The delay Time wide rule is built from this file; a missing copy silently left Time capped at 127.
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert "COPY docs/editor-parameters.json" in open(os.path.join(root, "Dockerfile")).read()
    assert pr.validate("dly", 3, 2, 3980, read_sync=lambda p: 0) == 3980
