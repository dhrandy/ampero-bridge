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


def test_short_messages_match_captured_packets():
    # captured: PC 75 = 0c c0 4b 00, CC 48 value 127 = 0b b0 30 7f
    assert u.encode_short(bytes([0xC0, 75])).hex() == "0cc04b00"
    assert u.encode_short(bytes([0xB0, 48, 127])).hex() == "0bb0307f"


def test_save_pair_is_one_72_byte_transfer():
    import ampero_mini as am
    a, b = am.save_patch(75, "WADE")
    data = u.encode_sysex(a) + u.encode_sysex(b)
    assert len(data) == 72
    assert data.hex().startswith("04f02125047f4d50042d3212040002060407014b05f70000")


def test_dev_node_count(tmp_path):
    (tmp_path / "001").mkdir()
    (tmp_path / "001" / "002").write_text("")
    (tmp_path / "001" / "003").write_text("")
    assert u.dev_node_count(str(tmp_path)) == 2
    assert u.dev_node_count(str(tmp_path / "missing")) is None


def test_visible_devices_never_raises(monkeypatch):
    monkeypatch.setattr(u, "_usb", lambda: (_ for _ in ()).throw(RuntimeError("no libusb")))
    assert u.visible_devices() == []
    assert u.seen() == {"libusb_devices": 0, "dev_nodes": u.dev_node_count()}
