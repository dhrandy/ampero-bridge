import pytest

import ampero_mini as am
import fakepedal as fp
import records
import server


def rec(**blocks):
    return fp.make_record(5, "T", blocks)


def test_block_fields_read_model_and_two_byte_params():
    r = rec(dly=(True, 9, [25, 15, 300, 1]))
    f = records.block_fields(r, "dly")
    assert f["on"] and f["code"] == 9 and f["params"][:4] == [25, 15, 300, 1]
    assert len(f["params"]) == records.PARAM_SLOTS
    assert records.name_of(r) == "T" and records.level_of(r) == 60


def test_same_records_have_no_differences():
    r = rec(amp=(True, 55, [1, 2, 3]))
    assert records.diffs(r, r, level=True) == []


def test_different_model_skips_the_knobs_until_the_model_is_written():
    a, b = rec(dly=(True, 9, [1, 2, 3, 4])), rec(dly=(True, 4, [9, 9, 9, 9]))
    ds = records.diffs(a, b, ["dly"])
    assert [d["field"] for d in ds] == ["model"]
    c = rec(dly=(True, 9, [9, 9, 9, 9]))
    ds = records.diffs(a, c, ["dly"])
    assert [(d["field"], d["index"]) for d in ds] == [("param", 0), ("param", 1), ("param", 2), ("param", 3)]
    assert ds[0]["model_code"] == 9


def test_only_asked_slots_and_level_are_compared():
    a, b = rec(amp=(True, 1, [5]), dly=(True, 9, [5])), rec(amp=(False, 1, [5]), dly=(True, 9, [6]))
    assert [d["slot"] for d in records.diffs(a, b, ["amp"])] == ["amp"]
    low = fp.make_record(5, "T", level=10)
    assert records.diffs(a, low, [], level=False) == []
    assert records.diffs(a, low, [], level=True)[0]["field"] == "level"


@pytest.mark.parametrize("d, ok", [
    ({"slot": "dly", "field": "power", "want": True}, True),
    ({"slot": "nr", "field": "power", "want": True}, True),
    ({"slot": "patch", "field": "level", "want": 99}, True),
    ({"slot": "patch", "field": "level", "want": 120}, False),
    ({"slot": "dly", "field": "model", "want": 9}, True),
    ({"slot": "dly", "field": "model", "want": 40}, False),
    ({"slot": "fx3", "field": "model", "want": 2}, True),
    ({"slot": "fx3", "field": "model", "want": 20}, False),
    ({"slot": "nr", "field": "model", "want": 1}, True),
    ({"slot": "nr", "field": "model", "want": 2}, False),
    ({"slot": "nr", "field": "param", "index": 0, "want": 5}, True),
    ({"slot": "dly", "field": "param", "index": 2, "want": 127}, True),
    ({"slot": "dly", "field": "param", "index": 2, "want": 128}, False),
    ({"slot": "cab", "field": "param", "index": 3, "want": 50}, True),
    ({"slot": "cab", "field": "param", "index": 4, "want": 50}, False),
])
def test_what_the_bridge_may_write(d, ok):
    assert (records.why_not(d, server.PROVEN_MODELS, False) is None) is ok


def test_unproven_models_pass_only_when_allowed():
    d = {"slot": "dly", "field": "model", "want": 40}
    assert records.why_not(d, server.PROVEN_MODELS, True) is None


def test_backup_file_round_trip_and_checks():
    p = {"index": 5, "label": "P2-3", "name": "T", "record_hex": rec().hex()}
    b = records.make_backup([p], [])
    assert records.load_backup(b)[5] == rec()
    assert records.load_backup(p)[5] == rec(), "a single patch dump is accepted"
    with pytest.raises(am.ProtocolError):
        records.load_backup({**b, "version": 2})
    with pytest.raises(am.ProtocolError):
        records.load_backup({**b, "patches": [{**p, "index": True}]})
