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
    ('fx3', 75, 0, 0, 3920), ('fx1', 142, 0, 0, 3920), ('dly', 16, 3, 0, 990),
    ('cab', 34, 4, 0, 100),
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


def test_oct14_verified_rules_and_sync_division_tables():
    for slot, code, p, values in [
        ('fx3', 75, 0, (0, 100, 920, 3920)),
        ('fx1', 77, 3, (65, 0, 100, 50)),
        ('fx1', 77, 4, (2, 1, 0)), ('fx2', 13, 4, (2, 1, 0)),
    ]:
        assert pr.rule_for(slot, code, p)['trust'] == pr.PROVEN
        for value in values:
            assert pr.validate(slot, code, p, value) == value
    steps = [i * 398 for i in range(11)]
    shared = (0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16)   # shared 0-3980 synced grid
    for code in range(17):
        model = pr.rules_view('dly', code)
        p = next(int(p) for p, rule in model['params'].items() if rule['name'] == 'Time')
        rule = pr.rule_for('dly', code, p)
        assert rule['trust'] == pr.PROVEN
        for value in (100, rule.get('unsynced_hi', rule['hi'])):
            assert pr.validate('dly', code, p, value, read_sync=lambda q: 0) == value
        if code in shared:
            assert rule['synced_values'] == steps
            for value in steps:
                assert pr.validate('dly', code, p, value, read_sync=lambda q: 1) == value
            for value in (1, 397, rule['hi'] - 1):
                with pytest.raises(pr.ValueRejected):
                    pr.validate('dly', code, p, value, read_sync=lambda q: 1)
            with pytest.raises(pr.ValueRejected):
                pr.validate('dly', code, p, 398)            # unknown Sync state
        else:               # Slapback has no Sync control
            assert rule.get('sync_param') is None
    for value in (398, 1592, 3980, 0):
        assert pr.validate('dly', 3, 2, value, read_sync=lambda q: 1) == value


def test_backmask_synced_time_shared_grid_and_unsynced_cap():
    steps = [i * 398 for i in range(11)]
    rule = pr.rule_for('dly', 6, 2)
    assert rule['synced_values'] == steps
    assert rule['hi'] == 3980 and rule['unsynced_hi'] == 1980
    for value in steps:                      # Sync on: the eleven divisions, past 1980
        assert pr.validate('dly', 6, 2, value, read_sync=lambda q: 1) == value
    for value in (1, 397, 1980, 3979):
        with pytest.raises(pr.ValueRejected):
            pr.validate('dly', 6, 2, value, read_sync=lambda q: 1)
    for value in (0, 430, 1980):             # Sync off: free knob up to the 1980 maximum
        assert pr.validate('dly', 6, 2, value, read_sync=lambda q: 0) == value
    for value in (1981, 2388, 3980):
        with pytest.raises(pr.ValueRejected):
            pr.validate('dly', 6, 2, value, read_sync=lambda q: 0)
    with pytest.raises(pr.ValueRejected):
        pr.validate('dly', 6, 2, 398)        # unknown Sync state


def test_oct15_map_records_full_cab_mode_and_sync_proof():
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).parents[1] / 'docs/param-map.json').read_text())
    site = (Path(__file__).parents[1] / 'site/param-map.json').read_text()
    assert site == (Path(__file__).parents[1] / 'docs/param-map.json').read_text()
    blocks = data['blocks']
    for slot, code in [('fx1', '77'), ('fx2', '13')]:
        mode = blocks[slot]['models'][code]['params']['4']
        assert mode['written'] == [0, 1, 2]
        assert '2026-10-15' in mode['note'] and 'changed value' in mode['note']
    all_cabs = list(range(50)) + list(range(112, 122)) + list(range(144, 154))
    assert len(all_cabs) == 70
    for p in ('4', '5', '6'):
        cab = blocks['cab']['models']['ALL']['params'][p]
        assert cab['verified_models'] == all_cabs
        assert 'assumed identical' not in cab['note']
    assert blocks['dly']['models']['3']['params']['2']['synced_written'] == [0, 398, 1592, 3980]
    steps = [i * 398 for i in range(11)]
    for code in ('0', '1', '2', '4', '5', '7', '8', '10', '11', '12', '13', '14', '15', '16'):
        time_entry = blocks['dly']['models'][code]['params']['2']
        assert '2026-10-15' in time_entry['note']
        assert time_entry['synced_written'] == steps
    assert blocks['dly']['models']['0']['params']['3']['status'] == 'write-verified'
    backmask = blocks['dly']['models']['6']['params']['2']
    assert 'refused' not in backmask['note'] and 'write-verified 2026-10-16' in backmask['note']
    assert backmask['synced_written'] == [i * 398 for i in range(11)]
