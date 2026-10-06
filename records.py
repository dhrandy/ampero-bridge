"""Reading a patch record and working out what differs between two of them.

A record is the 460 bytes the pedal returns for the patch it has selected
(docs/protocol.md, "Record layout"). This module only looks at bytes. It never
talks to the pedal: server.py does the sending and uses these helpers to decide
what to send.

Used by block copy, backup and restore. All three do the same thing in the end:
take the record we want, read the record the pedal has now, and write the
difference with the writes the bridge is allowed to make.
"""
from __future__ import annotations

import datetime
import json

import ampero_mini as am

RECORD_LEN = 460
LEVEL_OFFSET = 3          # patch level, 0-99 (CC 7 sets it)
LEVEL_CC = 7
PARAM_SLOTS = 14          # a block is 33 bytes: 4 of header, then 14 two-byte params
MAX_WRITE_VALUE = 127     # the biggest param value the bridge has seen on the wire

# State byte of each block in the record, in slot order (docs/protocol.md).
BLOCK_OFFSETS = {"fx1": 95, "fx2": 128, "amp": 161, "nr": 194, "cab": 227,
                 "eq": 260, "fx3": 293, "dly": 326, "rvb": 359}
BLOCKS = tuple(BLOCK_OFFSETS)

# The cab block does not use sixteen-bit params: from slot 4 on the bytes hold
# position Z and the two cuts, which the param frame cannot set (docs/knobs.md).
CAB_WRITABLE_PARAMS = 4

BACKUP_FORMAT = "ampero-bridge-backup"
BACKUP_VERSION = 1


class RecordError(am.ProtocolError):
    pass


def to_bytes(record_hex: str) -> bytes:
    try:
        rec = bytes.fromhex(record_hex)
    except (TypeError, ValueError):
        raise RecordError("record is not hex")
    if len(rec) != RECORD_LEN:
        raise RecordError(f"a record is {RECORD_LEN} bytes, this one is {len(rec)}")
    return rec


def block_fields(rec: bytes, slot: str) -> dict:
    """On/off, model code and the 14 param values of one block."""
    off = BLOCK_OFFSETS[slot]
    params = [rec[off + 4 + 2 * i] | (rec[off + 5 + 2 * i] << 8) for i in range(PARAM_SLOTS)]
    return {"on": rec[off] == 1, "code": rec[off + 1] * 128 + rec[off + 2], "params": params}


def name_of(rec: bytes) -> str:
    return rec[4:4 + am.NAME_LEN].split(b"\0")[0].decode("ascii", "replace")


def level_of(rec: bytes) -> int:
    return rec[LEVEL_OFFSET]


def diffs(want: bytes, have: bytes, slots=BLOCKS, level: bool = False) -> list[dict]:
    """What has to change in `have` to match `want`, for the given blocks.

    Params are only compared when both blocks hold the same model: a different
    model means different knobs, and the model write resets them anyway. Call
    again after the model has been written.
    """
    out = []
    if level and want[LEVEL_OFFSET] != have[LEVEL_OFFSET]:
        out.append({"slot": "patch", "field": "level", "want": want[LEVEL_OFFSET], "have": have[LEVEL_OFFSET]})
    for slot in slots:
        w, h = block_fields(want, slot), block_fields(have, slot)
        if w["on"] != h["on"]:
            out.append({"slot": slot, "field": "power", "want": w["on"], "have": h["on"]})
        if w["code"] != h["code"]:
            out.append({"slot": slot, "field": "model", "want": w["code"], "have": h["code"]})
            continue
        for i, (a, b) in enumerate(zip(w["params"], h["params"])):
            if a != b:
                out.append({"slot": slot, "field": "param", "index": i, "want": a, "have": b,
                            "model_code": w["code"]})
    return out


def why_not(d: dict, proven: dict, allow_unproven: bool) -> str | None:
    """None when the bridge can write this difference, otherwise the reason it cannot."""
    field, slot = d["field"], d["slot"]
    if field == "power":
        return None
    if field == "level":
        return None if 0 <= d["want"] <= 99 else "patch level must be 0-99"
    if slot not in am.SLOTS:
        return f"the {slot.upper()} block has no write slot in the bridge yet"
    if field == "model":
        codes = proven.get(slot)
        if not allow_unproven and (codes is None or d["want"] not in codes):
            return f"model code {d['want']} is not proven for {slot.upper()}"
        return None
    if slot == "cab" and d["index"] >= CAB_WRITABLE_PARAMS:
        return "CAB position Z and the cuts are not writable yet"
    if not 0 <= d["want"] <= MAX_WRITE_VALUE:
        return f"value {d['want']} is above the {MAX_WRITE_VALUE} the bridge can write"
    return None


def summarize(ds: list[dict], proven: dict, allow_unproven: bool) -> dict:
    """Split differences into writable and stuck ones (each stuck one carries its reason)."""
    todo, stuck = [], []
    for d in ds:
        reason = why_not(d, proven, allow_unproven)
        (stuck if reason else todo).append({**d, "reason": reason} if reason else d)
    return {"writable": todo, "stuck": stuck}


# --- backup files -------------------------------------------------------------------

def make_backup(patches: list[dict], skipped: list[dict]) -> dict:
    return {"format": BACKUP_FORMAT, "version": BACKUP_VERSION,
            "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "pedal": "Hotone Ampero Mini",
            "patches": [{"index": p["index"], "label": p["label"], "name": p["name"],
                         "record_hex": p["record_hex"]} for p in patches],
            "skipped": skipped}


def load_backup(obj) -> dict:
    """Check a backup file and return {index: record bytes}.

    Also takes the reply of GET /api/patch/current (one patch), so a single
    preset dump can be restored the same way.
    """
    if not isinstance(obj, dict):
        raise RecordError("backup must be a JSON object")
    if "patches" not in obj and "record_hex" in obj:
        obj = {"format": BACKUP_FORMAT, "version": BACKUP_VERSION, "patches": [obj]}
    if obj.get("format") != BACKUP_FORMAT:
        raise RecordError(f"not an {BACKUP_FORMAT} file")
    if obj.get("version") != BACKUP_VERSION:
        raise RecordError(f"backup version {obj.get('version')!r} is not supported (this bridge reads {BACKUP_VERSION})")
    items = obj.get("patches")
    if not isinstance(items, list) or not items:
        raise RecordError("backup has no patches")
    out = {}
    for item in items:
        if not isinstance(item, dict) or isinstance(item.get("index"), bool) or not isinstance(item.get("index"), int):
            raise RecordError("every patch needs an integer 'index'")
        idx = item["index"]
        if not 0 <= idx <= am.MAX_PATCH:
            raise RecordError(f"patch index {idx} is out of range")
        rec = to_bytes(item.get("record_hex", ""))
        if rec[1] != idx:
            raise RecordError(f"patch {idx}: the record says it belongs to index {rec[1]}")
        if idx in out:
            raise RecordError(f"patch {idx} is in the file twice")
        out[idx] = rec
    return out


def dumps(obj: dict) -> bytes:
    return json.dumps(obj, indent=1).encode()
