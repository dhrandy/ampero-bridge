"""Hotone Ampero Mini protocol, as captured from the real pedal.

Everything here was read off a Mini over USB (Oct 3, 2026) and checked against
its screen. Where something is a guess, the comment says so. Nothing in this
file comes from the Ampero II Stage docs: the Mini uses a different SysEx
header and a different command layout.

Two kinds of traffic:

* plain MIDI: Program Change selects a patch, Control Change switches blocks.
* SysEx with the header below: model select, parameter set, patch read, save.

Every SysEx frame is  F0 21 25 7F 4D 50 2D 32 <kind> <body> F7  with no
checksum. kind 0x12 carries data, kind 0x11 is a query.
"""
from __future__ import annotations

HEADER = bytes([0xF0, 0x21, 0x25, 0x7F, 0x4D, 0x50, 0x2D, 0x32])
KIND_DATA = 0x12
KIND_QUERY = 0x11

# Effect slots as they appear in the slot byte of model/param frames.
# 04 and 07 are probably NR and FX3 (never seen on the wire), 09 is probably RVB.
SLOTS = {"fx1": 0x01, "fx2": 0x02, "amp": 0x03, "cab": 0x05,
         "eq": 0x06, "dly": 0x08, "rvb": 0x09}

# Block on/off is plain CC on channel 1, value 0 = off, 127 = on. Verified on screen.
BLOCK_CC = {"fx1": 48, "fx2": 49, "amp": 50, "nr": 51, "cab": 52,
            "eq": 53, "fx3": 54, "dly": 55, "rvb": 56}
CC_BACK_TO_MAIN = 57   # screen navigation, not a toggle
CC_BACK = 58           # screen navigation, not a toggle
# CC 77 (lock) and CC 78 (all effects off) showed an effect in a sweep but were
# not isolated. They follow Hotone's Ampero II Stage list. Treat as unproven.
CC_LOCK_UNPROVEN = 77
CC_ALL_OFF_UNPROVEN = 78

# From the TouchOSC-Hotone-Ampero-template repo (no license, Feb 2024, model not
# stated): its FX1/FX2/EQ/FX3/DLY buttons use 48/49/53/54/55, which matches the
# map above. It also sends CC 22-25 (arrow buttons, pairing unknown) and CC 72
# (Tuner, probably). Not tried on this Mini yet.
CC_TEMPLATE_ARROWS_UNPROVEN = (22, 23, 24, 25)
CC_TEMPLATE_TUNER_UNPROVEN = 72

# EQ slot model codes, in the manual's order, with parameter counts.
EQ_MODELS = {
    0: ("Guitar EQ1", 6), 1: ("Guitar EQ2", 6), 2: ("Bass EQ1", 6),
    3: ("Bass EQ2", 6), 4: ("Para EQ", 15), 5: ("Graphic EQ", 11), 6: ("V-EQ", 5),
}

PATCHES_PER_BANK = 3   # index 75 is bank 26 patch 1 on the screen ("P26-1")
MAX_PATCH = 127        # Program Change range; the real patch count is not confirmed
NAME_LEN = 18          # the pedal's name field, NUL padded


class ProtocolError(ValueError):
    pass


def _check7(value: int, what: str) -> int:
    if not 0 <= value <= 0x7F:
        raise ProtocolError(f"{what} must be 0-127, got {value}")
    return value


def split14(value: int) -> tuple[int, int]:
    """14-bit value as two 7-bit bytes, high first (how model codes are sent)."""
    if not 0 <= value <= 0x3FFF:
        raise ProtocolError(f"value out of 14-bit range: {value}")
    return value >> 7, value & 0x7F


def frame(kind: int, body: bytes) -> bytes:
    if any(b > 0x7F for b in body):
        raise ProtocolError("SysEx body bytes must be 7-bit")
    return HEADER + bytes([kind]) + bytes(body) + b"\xf7"


def parse_frame(data: bytes) -> tuple[int, bytes] | None:
    """Return (kind, body) for a Mini SysEx frame, or None for anything else."""
    if len(data) < len(HEADER) + 2 or not data.startswith(HEADER) or data[-1] != 0xF7:
        return None
    return data[len(HEADER)], data[len(HEADER) + 1:-1]


# --- plain MIDI -----------------------------------------------------------------

def program_change(index: int, channel: int = 0) -> bytes:
    """Select patch `index` (0 based). PC 75 lands on P26-1."""
    if not 0 <= index <= MAX_PATCH:
        raise ProtocolError(f"patch index must be 0-{MAX_PATCH}")
    return bytes([0xC0 | channel, index])


def control_change(cc: int, value: int, channel: int = 0) -> bytes:
    return bytes([0xB0 | channel, _check7(cc, "cc"), _check7(value, "value")])


def block_power(block: str, on: bool) -> bytes:
    if block not in BLOCK_CC:
        raise ProtocolError(f"unknown block {block!r}; use one of {sorted(BLOCK_CC)}")
    return control_change(BLOCK_CC[block], 127 if on else 0)


# --- SysEx writes ---------------------------------------------------------------

def _slot(slot: str | int) -> int:
    if isinstance(slot, str):
        if slot not in SLOTS:
            raise ProtocolError(f"unknown slot {slot!r}; use one of {sorted(SLOTS)}")
        return SLOTS[slot]
    return _check7(slot, "slot")


def model_select(slot: str | int, code: int) -> bytes:
    """Pick the effect model for a slot:  10 AA 00 01 HH LL"""
    hi, lo = split14(code)
    return frame(KIND_DATA, bytes([0x10, _slot(slot), 0x00, 0x01, hi, lo]))


def param_set(slot: str | int, model_code: int, param: int, value: int) -> bytes:
    """Set one parameter:  10 AA 00 02 HH LL SS HI LO

    HH LL is the model code the slot currently holds, SS the parameter number
    in the manual's order for that model. Only 0-127 values have been seen on
    the wire, so that is all this accepts.
    """
    hi, lo = split14(model_code)
    return frame(KIND_DATA, bytes([0x10, _slot(slot), 0x00, 0x02, hi, lo,
                                   _check7(param, "param"), 0x00, _check7(value, "value")]))


def encode_name(name: str) -> bytes:
    try:
        raw = name.encode("ascii", "strict")
    except UnicodeEncodeError:
        raise ProtocolError(f"name must be up to {NAME_LEN} printable ASCII characters")
    if len(raw) > NAME_LEN or any(b < 0x20 or b > 0x7E for b in raw):
        raise ProtocolError(f"name must be up to {NAME_LEN} printable ASCII characters")
    return raw.ljust(NAME_LEN, b"\0")


def save_patch(index: int, name: str) -> list[bytes]:
    """The editor's save: two frames sent back to back.

    A  00 02 06 07 01 <idx>        opener
    B  10 00 00 00 01 <idx> <name18>  index and name

    Captured from the official editor. Verified on the pedal: both frames in
    one USB transfer saved the name TEST into P26-1. The pedal sends nothing
    back for a save, so only its screen shows the result.
    """
    _check7(index, "patch index")
    a = frame(KIND_DATA, bytes([0x00, 0x02, 0x06, 0x07, 0x01, index]))
    b = frame(KIND_DATA, bytes([0x10, 0x00, 0x00, 0x00, 0x01, index]) + encode_name(name))
    return [a, b]


# --- patch read (what the editor does to "load" a patch) --------------------------

def read_patch_requests(index: int) -> list[bytes]:
    """The eight frames the editor sends to pull patch `index` off the pedal.

    The pedal answers with a header (00 02 12), five data chunks (00 02 14,
    chunk 0-4) and a trailer (00 02 16). Use decode_patch() on the chunks.
    """
    _check7(index, "patch index")
    reqs = [frame(KIND_QUERY, bytes([0x00, 0x02, 0x0A, 0x00, 0x00, 0x00])),
            frame(KIND_DATA, bytes([0x00, 0x02, 0x13, 0x00, 0x01, index, 0x01]))]
    for chunk in range(5):
        reqs.append(frame(KIND_DATA, bytes([0x00, 0x02, 0x15, 0x00, 0x01, index, 0x00, chunk, 0x01])))
    reqs.append(frame(KIND_QUERY, bytes([0x00, 0x00, 0x05, 0x01])))
    return reqs


PATCH_CHUNKS = 5


def decode_patch(replies: list[bytes]) -> dict:
    """Turn the pedal's 00 02 14 chunks into the patch record.

    Each chunk body is nibble split (two 4-bit values per real byte). Joined and
    decoded, the record is 460 bytes: `01 <idx> 00 3C <name18> ...`. Only the
    index and the name are understood. The rest (models, parameters, block
    states) is returned as raw bytes for later decoding.
    """
    chunks: dict[int, bytes] = {}
    for data in replies:
        parsed = parse_frame(data)
        if not parsed or parsed[0] != KIND_DATA:
            continue
        body = parsed[1]
        if body[:3] == bytes([0x00, 0x02, 0x14]) and len(body) > 6:
            chunks[body[7]] = body[8:]   # 00 02 14 00 01 <idx> 00 <chunk> <data...>
    missing = [i for i in range(PATCH_CHUNKS) if i not in chunks]
    if missing:
        raise ProtocolError(f"patch dump incomplete, missing chunks {missing}")
    nibbles = b"".join(chunks[i] for i in range(PATCH_CHUNKS))
    if len(nibbles) % 2:
        nibbles = nibbles[:-1]
    record = bytes((nibbles[i] << 4) | nibbles[i + 1] for i in range(0, len(nibbles), 2))
    index = record[1] if len(record) > 1 else None
    name = record[4:4 + NAME_LEN].split(b"\0")[0].decode("ascii", "replace")
    return {"index": index, "label": patch_label(index) if index is not None else None,
            "name": name, "record_hex": record.hex()}


# --- helpers ----------------------------------------------------------------------

def patch_label(index: int) -> str:
    return f"P{index // PATCHES_PER_BANK + 1}-{index % PATCHES_PER_BANK + 1}"


def describe_frame(data: bytes) -> str:
    """Readable one-liner for logs."""
    parsed = parse_frame(data)
    if not parsed:
        return data.hex(" ")
    kind, body = parsed
    return f"{'data' if kind == KIND_DATA else 'query' if kind == KIND_QUERY else hex(kind)} {body.hex(' ')}"
