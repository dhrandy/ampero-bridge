import usbmidi as u


def test_roundtrip_all_lengths():
    for n in range(0, 40):
        f = bytes([0xF0]) + bytes([5] * n) + bytes([0xF7])
        assert u.SysexAssembler().feed(u.encode_sysex(f)) == [f]


def test_split_reads_and_noise():
    f = bytes([0xF0]) + bytes(range(1, 30)) + bytes([0xF7])
    e = u.encode_sysex(f)
    a = u.SysexAssembler()
    noise = bytes([0x09, 0x90, 0x40, 0x7F])  # note-on, not sysex
    assert a.feed(noise + e[:8]) == []
    assert a.feed(e[8:] + bytes(4)) == [f]


def test_identity_request_bytes():
    assert u.encode_sysex(bytes.fromhex("F07E7F0601F7")).hex() == "04f07e7f070601f7"
