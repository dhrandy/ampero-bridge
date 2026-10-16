"""Replay sanitized measurements from prior live sweeps. No hardware access.

The fixture keeps only model/parameter/value tuples, never whole preset snapshots.
These tests guard rules and decode ownership; they cannot prove a USB write works.
"""
import json
from pathlib import Path

import ampero_mini as am
import fakepedal as fp
import paramrules as pr
import records

DATA = json.loads((Path(__file__).parent / 'fixtures/hardware-regressions.json').read_text())


def test_recovered_sweep_coverage():
    cases = DATA['cases']
    assert len({code for slot, code, *_ in cases if slot == 'amp'}) == 60
    assert len({code for slot, code, *_ in cases if slot == 'cab'}) == 70
    assert DATA['coverage']['other_models'] == 187
    # 31 sync/rate models from the Oct 13 sweep plus the 15 delay models whose synced Time
    # tables were proven 2026-10-15 (fourteen) and 2026-10-16 (Backmask).
    assert len({(slot, code) for slot, code, p, v, got, source, sync in cases if source == 'sync'}) == 46
    assert any(row[:5] == ['eq', 4, 13, 6, 6] for row in cases)
    assert any(row[:5] == ['eq', 4, 14, 75, 75] for row in cases)


def test_prior_measured_values_still_fit_verify_rules_and_decode(monkeypatch):
    monkeypatch.setattr(pr, 'VERIFY_ENABLED', True)
    excluded = []
    for slot, code, p, want, got, source, sync in DATA['cases']:
        assert want == got
        rule = pr.rule_for(slot, code, p)
        # A historical value may lie outside today's documented guard (notably the
        # old wide decoder, sync side effects and partial enum sweeps). Do not loosen
        # a safety rule just to replay it. The fixture preserves the evidence instead.
        try:
            pr.validate_verify(slot, code, p, want, read_sync=lambda q: sync if sync is not None else 0)
        except pr.ValueRejected as error:
            excluded.append((slot, code, p, want, error.extra['reason']))
            continue
        kind, body = am.parse_frame(am.param_set(slot, code, p, want))
        assert kind == am.KIND_DATA and body[7] * 128 + body[8] == want
        buf = bytearray(fp.make_record(0, 'DEMO', {slot: (True, code, [])}))
        fp.store_param(buf, slot, code, p, want)
        assert records.block_fields(bytes(buf), slot)['params'][p] == got
    assert excluded == [('dly', 11, 4, value, 'sync_unknown') for value in (25, 50, 75)]


def test_fixture_contains_only_allowed_fields():
    assert set(DATA) == {'format', 'scope', 'columns', 'coverage', 'cases', 'excluded_mismatches'}
    for row in DATA['cases']:
        assert len(row) == 7
        assert row[0] in am.SLOTS and all(isinstance(v, int) for v in row[1:5])
        assert row[5] in ('amp', 'cab', 'other', 'verify', 'sync')
        assert row[6] is None or row[6] in (0, 1)
