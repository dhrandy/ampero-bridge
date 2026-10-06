"""Look inside a Hotone .prst file and say what the bridge can do with it.

What is known comes from public notes on the original Ampero and Ampero One
(see docs/prst.md). The outer container is understood: a header, a table of
patch offsets, then one block per patch. What is NOT known is how the Mini
stores a patch inside that block, and no Mini file was available to check. So
this module reads the container and the names, and stops there. It never turns
patch bytes into settings by guessing.

Layout, all numbers little endian:

    0   "TSRP"                        file magic
    4   u32  size of what follows the first 8 bytes
    8   5 bytes, 1 byte              unknown
    14  u16  number of patches
    16  16 bytes                     unknown
    32  nb x (u32 offset, u32 size)  one entry per patch
        patch blocks
        3 bytes                      tail
    a patch block is "MRAP", u32 size, 1 byte, 1 byte position, 2 bytes, 16 bytes name, data
"""
from __future__ import annotations

import struct

MAGIC = b"TSRP"
PATCH_MAGIC = b"MRAP"
HEADER_LEN = 32
PATCH_HEAD_LEN = 12
NAME_LEN = 16
MAX_PATCHES = 255

WHY_NOT = ("The settings inside a Mini patch block are not documented and the bridge does not guess "
           "at bytes, so this file cannot be loaded onto the pedal. Only a backup made by this bridge can.")


def inspect(data: bytes) -> dict:
    """Describe a .prst file. Never raises on bad input; the reply says what was wrong."""
    out = {"importable": False, "container": None, "patches": [], "reason": WHY_NOT}
    if not isinstance(data, (bytes, bytearray)) or not data:
        out["error"] = "the file is empty"
        return out
    if data[:4] != MAGIC:
        out["error"] = "this does not look like a Hotone .prst file (it does not start with TSRP)"
        out["reason"] = "Only Hotone .prst files can be inspected, and only bridge backups can be loaded."
        return out
    if len(data) < HEADER_LEN:
        out["error"] = "the file is cut off inside its header"
        return out
    count = struct.unpack_from("<H", data, 14)[0]
    if not 1 <= count <= MAX_PATCHES:
        out["error"] = f"the header claims {count} patches, which is not plausible"
        return out
    table_end = HEADER_LEN + 8 * count
    if table_end > len(data):
        out["error"] = "the file is cut off inside its patch table"
        return out
    patches = []
    for i in range(count):
        offset, size = struct.unpack_from("<II", data, HEADER_LEN + 8 * i)
        if offset < table_end or size < PATCH_HEAD_LEN or offset + size > len(data):
            out["error"] = f"patch {i + 1} points outside the file"
            return out
        block = data[offset:offset + size]
        if block[:4] != PATCH_MAGIC:
            out["error"] = f"patch {i + 1} does not start with MRAP"
            return out
        name = block[PATCH_HEAD_LEN:PATCH_HEAD_LEN + NAME_LEN].split(b"\0")[0]
        patches.append({"position": block[9], "name": name.decode("ascii", "replace").strip(), "size": size})
    out["container"] = "TSRP"
    out["patches"] = patches
    out["count"] = len(patches)
    return out
