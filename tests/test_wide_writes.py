"""New raw encodings: all records here are synthetic, not new pedal captures."""
import pytest

import ampero_mini as am
import fakepedal as fp
import paramrules as pr
import records


@pytest.mark.parametrize('value', [0, 1, 127, 128, 280, 1801, 1981, 3920, 3980, 16383])
def test_param_frame_carries_high_then_low_seven_bits(value):
    _, body = am.parse_frame(am.param_set('dly', 3, 2, value))
    assert list(body[-2:]) == [value >> 7, value & 127]


@pytest.mark.parametrize('value', [-1, 16384])
def test_encoder_rejects_outside_fourteen_bits(value):
    with pytest.raises(am.ProtocolError):
        am.param_set('dly', 3, 2, value)


@pytest.mark.parametrize('slot,code,p,lo,hi', [
    ('dly', 3, 2, 0, 3980), ('dly', 9, 2, 0, 280), ('dly', 6, 2, 0, 1980),
    ('fx3', 75, 0, 0, 3920), ('cab', 34, 4, 0, 100),
    ('cab', 34, 5, 0, 1981), ('cab', 34, 6, 0, 1801), ('fx2', 13, 3, 0, 100)])
def test_boundaries_and_record_ownership(monkeypatch, slot, code, p, lo, hi):
    monkeypatch.setattr(pr, 'VERIFY_ENABLED', True)
    for v in (lo, hi):
        assert pr.validate_verify(slot, code, p, v, read_sync=lambda q: 0) == v
        rec = bytearray(fp.make_record(0, 'DEMO', {slot: (True, code, [])}))
        before = bytes(rec)
        fp.store_param(rec, slot, code, p, v)
        assert records.block_fields(bytes(rec), slot)['params'][p] == v
        for other, off in records.BLOCK_OFFSETS.items():
            if other != slot:
                assert rec[off:off+33] == before[off:off+33]
    for v in (-1, hi + 1):
        with pytest.raises(pr.ValueRejected):
            pr.validate_verify(slot, code, p, v, read_sync=lambda q: 0)


def test_delay_time_does_not_overwrite_feedback_and_cuts_do_not_overwrite_z():
    buf = bytearray(fp.make_record(0, 'DEMO', {'dly': (True, 3, [30, 40, 430]),
                                               'cab': (True, 34, [0, 50, 50, 50, 75, 0, 1801])}))
    fp.store_param(buf, 'dly', 3, 2, 3980)
    fp.store_param(buf, 'cab', 34, 5, 1981)
    assert records.block_fields(bytes(buf), 'dly')['params'][1:3] == [40, 3980]
    assert records.block_fields(bytes(buf), 'cab')['params'][4:7] == [75, 1981, 1801]


def test_synced_analog_time_divisions_require_current_sync(monkeypatch):
    monkeypatch.setattr(pr, 'VERIFY_ENABLED', True)
    assert pr.rules_view('dly', 3)['params']['2']['synced_values'] == [i * 398 for i in range(11)]
    for i in range(11):
        assert pr.validate_verify('dly', 3, 2, i * 398, read_sync=lambda q: 1) == i * 398
    with pytest.raises(pr.ValueRejected):
        pr.validate_verify('dly', 3, 2, 3980)
    with pytest.raises(pr.ValueRejected):
        pr.validate('dly', 3, 2, 100, unverified_ok=True, read_sync=lambda q: 1)
