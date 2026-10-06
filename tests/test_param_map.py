import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
STATUSES = {"write-verified", "address-confirmed-only", "inferred", "unswept"}


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
