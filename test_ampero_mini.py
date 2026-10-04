import pytest

import ampero_mini as am


def test_save_frames_match_editor_capture():
    a, b = am.save_patch(0x4B, "WADE")
    assert a.hex(" ") == "f0 21 25 7f 4d 50 2d 32 12 00 02 06 07 01 4b f7"
    assert b.hex(" ") == ("f0 21 25 7f 4d 50 2d 32 12 10 00 00 00 01 4b 57 41 44 45"
                          + " 00" * 14 + " f7")


def test_name_rules():
    with pytest.raises(am.ProtocolError):
        am.save_patch(1, "x" * 19)
    with pytest.raises(am.ProtocolError):
        am.save_patch(1, "bad\x01")


def test_model_and_param_frames():
    # EQ slot, Para EQ (code 4), from the captured burst
    assert am.model_select("eq", 4).hex(" ").endswith("10 06 00 01 00 04 f7")
    assert am.param_set("eq", 4, 3, 0x1E).hex(" ").endswith("10 06 00 02 00 04 03 00 1e f7")


def test_plain_midi():
    assert am.program_change(75) == bytes([0xC0, 75])
    assert am.block_power("rvb", True) == bytes([0xB0, 56, 127])
    assert am.block_power("fx1", False) == bytes([0xB0, 48, 0])
    with pytest.raises(am.ProtocolError):
        am.block_power("nope", True)


def test_labels():
    assert am.patch_label(75) == "P26-1"


def test_read_requests_match_editor_group():
    reqs = [r[len(am.HEADER):-1].hex(" ") for r in am.read_patch_requests(0x4B)]
    assert reqs[0] == "11 00 02 0a 00 00 00"
    assert reqs[1] == "12 00 02 13 00 01 4b 01"
    assert reqs[2] == "12 00 02 15 00 01 4b 00 00 01"
    assert reqs[6] == "12 00 02 15 00 01 4b 00 04 01"
    assert reqs[7] == "11 00 00 05 01"


CAPTURE = """\
f0 21 25 7f 4d 50 2d 32 12 00 02 14 00 01 4b 00 00 00 01 04 0b 00 00 03 0c 05 07 04 01 04 04 04 05 00 00 f7
"""


def test_decode_patch_name():
    # a short fake dump: chunk 0 carries the record start, the rest are empty
    def chunk(n, nibbles):
        return am.frame(am.KIND_DATA, bytes([0x00, 0x02, 0x14, 0x00, 0x01, 0x4B, 0x00, n]) + bytes(nibbles))
    rec = bytes([0x01, 0x4B, 0x00, 0x3C]) + b"WADE" + bytes(14)
    nib = [x for b in rec for x in (b >> 4, b & 15)]
    replies = [chunk(0, nib)] + [chunk(i, [0, 0]) for i in range(1, 5)]
    out = am.decode_patch(replies)
    assert out["name"] == "WADE" and out["index"] == 0x4B and out["label"] == "P26-1"
    with pytest.raises(am.ProtocolError):
        am.decode_patch(replies[:3])
