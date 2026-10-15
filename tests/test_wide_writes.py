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


def test_oct14_verified_rules_and_remaining_sync_gate():
    for slot, code, p, values in [
        ('fx3', 75, 0, (0, 100, 920, 3920)),
        ('fx1', 77, 3, (65, 0, 100, 50)),
        ('fx1', 77, 4, (2, 0)), ('fx2', 13, 4, (2, 0)),
    ]:
        assert pr.rule_for(slot, code, p)['trust'] == pr.PROVEN
        for value in values:
            assert pr.validate(slot, code, p, value) == value
    for code in range(17):
        model = pr.rules_view('dly', code)
        p = next(int(p) for p, rule in model['params'].items() if rule['name'] == 'Time')
        rule = pr.rule_for('dly', code, p)
        assert rule['trust'] == pr.PROVEN
        for value in (100, rule['hi']):
            assert pr.validate('dly', code, p, value, read_sync=lambda q: 0) == value
        if code != 3 and rule.get('sync_param') is not None:
            for value in (0, 398, rule['hi']):
                with pytest.raises(pr.ValueRejected):
                    pr.validate('dly', code, p, value, read_sync=lambda q: 1)
    for value in (398, 1592, 3980, 0):
        assert pr.validate('dly', 3, 2, value, read_sync=lambda q: 1) == value


def test_oct14_map_keeps_partial_proof_caveats():
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).parents[1] / 'docs/param-map.json').read_text())
    blocks = data['blocks']
    for slot, code in [('fx1', '77'), ('fx2', '13')]:
        mode = blocks[slot]['models'][code]['params']['4']
        assert mode['written'] == [0, 2]
        assert 'no-op' in mode['note']
    for p in ('4', '5', '6'):
        cab = blocks['cab']['models']['ALL']['params'][p]
        assert cab['verified_models'] == [0, 13, 25, 49, 112, 144, 153]
        assert 'assumed identical' in cab['note']
    assert blocks['dly']['models']['3']['params']['2']['synced_written'] == [0, 398, 1592, 3980]
