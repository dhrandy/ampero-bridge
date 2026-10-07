import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
STATUSES = {"write-verified", "address-confirmed-only", "inferred", "unswept", "editor-defined"}


def test_param_map_is_valid_and_matches_the_bridge_slots():
    import ampero_mini as am
    import records
    with open(os.path.join(HERE, "..", "docs", "param-map.json")) as f:
        data = json.load(f)
    assert set(data["blocks"]) == set(am.SLOTS)
    for slot, block in data["blocks"].items():
        assert block["bridge_slot_id"] == am.SLOTS[slot]
        assert block["state_offset"] == records.BLOCK_OFFSETS[slot]
        for model in block["models"].values():
            for param in model["params"].values():
                assert param["status"] in STATUSES
                assert records.BLOCK_OFFSETS[slot] < param["record_offset"] < 459


def test_site_copy_matches_docs_copy():
    a = open(os.path.join(HERE, "..", "docs", "param-map.json"), "rb").read()
    b = open(os.path.join(HERE, "..", "site", "param-map.json"), "rb").read()
    assert a == b


def test_official_editor_coverage_and_black_twin_names():
    with open(os.path.join(HERE, '..', 'docs', 'param-map.json')) as f:
        m = json.load(f)
    with open(os.path.join(HERE, '..', 'docs', 'editor-parameters.json')) as f:
        e = json.load(f)
    assert {b: len(x['models']) for b, x in e['blocks'].items()} == {
        'fx1': 60, 'fx2': 60, 'amp': 60, 'nr': 2, 'cab': 70,
        'eq': 7, 'fx3': 30, 'dly': 17, 'rvb': 11}
    black = m['blocks']['amp']['models']['2']['params']
    assert [black[str(i)]['name'] for i in range(6)] == [
        'Gain', 'Master', 'Bass', 'Middle', 'Treble', 'Bright']
    assert black['5']['status'] == 'address-confirmed-only'
    assert all(black[str(i)]['name_screen_verified'] for i in range(6))


def test_editor_does_not_override_proven_conflicts():
    with open(os.path.join(HERE, '..', 'docs', 'param-map.json')) as f:
        m = json.load(f)
    trem = m['blocks']['fx3']['models']['8']['params']
    assert trem['4']['name'] == 'Trm Rate'
    assert trem['5']['name'] == 'Flg Sync' and trem['5']['record_offset'] == 307
    assert trem['6']['name'] == 'Trm Sync' and trem['6']['record_offset'] == 309
    assert trem['5']['status'] == trem['6']['status'] == 'write-verified'
    assert m['blocks']['amp']['models']['55']['params']['2']['name'] == 'Master'
    assert m['blocks']['amp']['models']['55']['params']['2']['editor_definition']['name'] == 'Output'
    for block, code in [('fx1', '45'), ('fx2', '93'), ('fx3', '76')]:
        p = m['blocks'][block]['models'][code]['params']
        assert p['0']['valid_range'] == [0, 5]
        assert p['3']['status'] == 'editor-defined'
    assert m['blocks']['amp']['models']['9']['params']['3']['status'] == 'editor-defined'
    assert m['blocks']['dly']['models']['0']['params']['4']['status'] == 'editor-defined'
