"""Hotone Ampero Mini USB-MIDI SysEx protocol.

Adapted from the Ampero II Stage reverse-engineering work by jpfaria
(hotone-ampero-2, MIT licensed). The Mini speaks the same SysEx frame family,
with fewer slots and patches.

Frame:  F0 21 25 4D 50 00 00 CK CMD LEN(2x7-bit LE) OFF(2x7-bit LE) NIBBLES... F7
  CK      = sum of every byte from LEN's high byte up to (not including) F7, mod 128
  CMD     = 0x11 query (host->device), 0x12 data (both directions)
  LEN     = decoded payload length; OFF = decoded offset of this chunk
  NIBBLES = each payload byte b as two bytes (b >> 4, b & 0x0F)

Payload: [type 2B] [op] [target] [len32 LE = LEN-8] [LEN+5] body [11 00 00]

Mini specifics (to verify against the hardware):
  SLOTS = 9  (Mini has 9 effect modules, II Stage has 12)
  PATCHES = 198 (99 user + 99 factory)
  Port name is expected to be "Ampero Mini MIDI".
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

SYSEX_START = 0xF0
SYSEX_END = 0xF7
HEADER = bytes.fromhex("2125 4D50 0000")  # after F0
CMD_QUERY = 0x11
CMD_DATA = 0x12
TRAILER = bytes.fromhex("110000")

# Ampero Mini constants (II Stage values in comments where they differ)
SLOTS = 9            # II Stage: 12
PATCHES = 198        # II Stage: 300
PATCHES_PER_BANK = 5
PATCH_NAME_LEN = 16  # plus NUL on the wire
PORT_NAME = "Ampero Mini MIDI"
MAX_CHUNK = 185

_CK_FROM = 10
_INNER_LEN_EXTRA = 8
_INNER_TAG_EXTRA = 5


def encode_nibbles(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        out += bytes((b >> 4, b & 0x0F))
    return bytes(out)


def decode_nibbles(data: bytes) -> bytes:
    if len(data) % 2:
        raise ValueError(f"odd nibble stream length {len(data)}")
    return bytes((data[i] << 4) | data[i + 1] for i in range(0, len(data), 2))


def _u14(v: int) -> bytes:
    return bytes((v & 0x7F, (v >> 7) & 0x7F))


def checksum(frame: bytes) -> int:
    return sum(frame[_CK_FROM:-1]) & 0x7F


@dataclass(frozen=True)
class Frame:
    cmd: int
    length: int
    offset: int
    payload: bytes


def build_frame(cmd: int, payload: bytes, offset: int = 0, total: int | None = None) -> bytes:
    total = len(payload) if total is None else total
    body = bytes((cmd,)) + _u14(total) + _u14(offset) + encode_nibbles(payload)
    frame = bytes((SYSEX_START,)) + HEADER + b"\0" + body + bytes((SYSEX_END,))
    return frame[:7] + bytes((checksum(frame),)) + frame[8:]


def parse_frame(frame: bytes) -> Frame:
    if frame[0] != SYSEX_START or frame[-1] != SYSEX_END or frame[1:7] != HEADER:
        raise ValueError("not an Ampero frame")
    cmd = frame[8]
    length = frame[9] | (frame[10] << 7)
    offset = frame[11] | (frame[12] << 7)
    return Frame(cmd, length, offset, decode_nibbles(frame[13:-1]))


def _payload(kind: bytes, body: bytes) -> bytes:
    total = len(kind) + 4 + 1 + len(body) + len(TRAILER)
    return kind + struct.pack("<I", total - _INNER_LEN_EXTRA) + bytes((total + _INNER_TAG_EXTRA,)) + body + TRAILER


def _msg(cmd: int, kind: str, body: bytes) -> bytes:
    return build_frame(cmd, _payload(bytes.fromhex(kind), body))


def msg_set_param(slot: int, index: int, value: float) -> bytes:
    """Set a knob parameter. slot 0-based, index = knob order, value = float."""
    return _msg(CMD_DATA, "03000401", bytes((slot, 0, index, 0)) + struct.pack("<f", value))


def msg_scene_powers(scene: int, powers: list[int]) -> bytes:
    """Block on/off for a scene: 12 bytes on II Stage, SLOTS bytes here."""
    if len(powers) != SLOTS:
        raise ValueError(f"need {SLOTS} slot states")
    return _msg(CMD_DATA, "04000901", bytes((scene, *powers)))


def msg_load_patch(index: int) -> bytes:
    return _msg(CMD_DATA, "00000900", struct.pack("<I", index))


def msg_get_patch(index: int) -> bytes:
    return _msg(CMD_QUERY, "00000001", struct.pack("<I", index))


def msg_save_patch(index: int, name: str) -> bytes:
    raw = name.encode("ascii")
    if len(raw) > PATCH_NAME_LEN:
        raise ValueError(f"patch name longer than {PATCH_NAME_LEN}: {name!r}")
    return _msg(CMD_DATA, "00000005", struct.pack("<I", index) + raw.ljust(PATCH_NAME_LEN + 1, b"\0"))


def msg_query_patch_names() -> bytes:
    return build_frame(CMD_QUERY, bytes.fromhex("00000801") + bytes(4))


def msg_query_firmware() -> bytes:
    return build_frame(CMD_QUERY, bytes.fromhex("05000003") + bytes(4))


def msg_query_scene() -> bytes:
    return build_frame(CMD_QUERY, bytes.fromhex("01000003") + bytes(4))


def msg_set_model(slot: int, category: int, code: int) -> bytes:
    """Set the effect model in a slot. A wrong category byte can hang the pedal's
    SysEx until power-cycle: only send category/code pairs from the catalog."""
    return _msg(CMD_DATA, "02000401", bytes((slot, category)) + struct.pack("<I", code) + b"\x01")


def msg_clear_slot(slot: int) -> bytes:
    return _msg(CMD_DATA, "02000401", bytes((slot,)) + bytes((0xFF,)) * 5 + b"\x01")


def msg_set_patch_volume(volume: int) -> bytes:
    return _msg(CMD_DATA, "01000901", b"\0\0" + struct.pack("<H", volume))


def msg_set_tempo(bpm: int) -> bytes:
    return _msg(CMD_DATA, "02000901", b"\0\0" + struct.pack("<H", bpm))


_REPLY_BODY_START = 9


def reply_body(frame: Frame) -> bytes:
    return frame.payload[_REPLY_BODY_START:-len(TRAILER)]


def patch_index(label: str) -> int:
    """'A28-4' -> 138 (bank A, 5 patches per bank, both 1-based)."""
    bank, pos = label.upper().lstrip("A").split("-")
    return (int(bank) - 1) * PATCHES_PER_BANK + int(pos) - 1


def patch_label(index: int) -> str:
    return f"A{index // PATCHES_PER_BANK + 1}-{index % PATCHES_PER_BANK + 1}"
