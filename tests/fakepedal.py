"""A pedal that behaves like the notes in docs/protocol.md, for tests and for trying the site.

It holds a set of stored patches and one edit buffer. Program Change copies a stored patch into
the buffer, block CCs, model and param frames edit the buffer, and a save copies the buffer
back. Every read answers with the buffer, whatever index the request carries (like the real
pedal). Nothing here is measured: the model defaults are made up.
"""
import copy

import ampero_mini as am
import records
import usbmidi as usb

SLOT_NAMES = {v: k for k, v in am.SLOTS.items()}
SLOT_BY_BLOCK_STATE = {name: off for name, off in records.BLOCK_OFFSETS.items()}


def make_record(idx, name, blocks=None, level=60):
    """A 460-byte record. blocks: {"dly": (on, model_code, [params])}."""
    rec = bytearray(records.RECORD_LEN)
    rec[0], rec[1], rec[2], rec[3] = 1, idx, 0, level
    rec[4:4 + am.NAME_LEN] = name.encode().ljust(am.NAME_LEN, b"\0")
    for slot, off in records.BLOCK_OFFSETS.items():
        on, code, params = (blocks or {}).get(slot, (False, 0, []))
        rec[off] = 1 if on else 0
        rec[off + 1], rec[off + 2] = code >> 7, code & 0x7F
        for i, v in enumerate(params):
            rec[off + 4 + 2 * i], rec[off + 5 + 2 * i] = v & 0xFF, v >> 8
    return bytes(rec)


def default_params(code):
    return [(code % 7 + 1) * 10 + i for i in range(4)] + [0] * (records.PARAM_SLOTS - 4)


class Pedal:
    """Shared state; the class is installed as usbmidi.Pedal, so tests reset it with reset()."""
    store = {}
    cur = 0
    edit = b""
    present = True
    out = []
    log = []
    count = 100

    @classmethod
    def reset(cls, patches=None):
        cls.store = dict(patches or {})
        cls.cur = min(cls.store) if cls.store else 0
        cls.edit = cls.store.get(cls.cur, make_record(cls.cur, "EMPTY"))
        cls.present, cls.out, cls.log = True, [], []

    def __enter__(self):
        if not Pedal.present:
            raise usb.PedalNotConnected("pedal not connected")
        return self

    def __exit__(self, *a):
        return False

    def drain(self):
        Pedal.out = []

    # --- what the host sends -------------------------------------------------------
    def send_midi(self, m):
        status, a = m[0] & 0xF0, m[1]
        Pedal.log.append(("midi", bytes(m)))
        buf = bytearray(Pedal.edit)
        if status == 0xC0:
            if a < Pedal.count:
                Pedal.cur = a
                Pedal.edit = Pedal.store.get(a, make_record(a, "EMPTY"))
            return
        if status == 0xB0:
            v = m[2]
            for slot, cc in am.BLOCK_CC.items():
                if cc == a:
                    buf[records.BLOCK_OFFSETS[slot]] = 1 if v >= 64 else 0
            if a == records.LEVEL_CC:
                buf[records.LEVEL_OFFSET] = min(v, 99)
        Pedal.edit = bytes(buf)

    def send_sysex(self, f):
        Pedal.log.append(("sysex", bytes(f)))
        kind, body = am.parse_frame(f)
        if kind == am.KIND_QUERY:
            return
        buf = bytearray(Pedal.edit)
        if body[:3] == bytes([0x00, 0x02, 0x13]):
            self._queue_dump()
        elif body[0] == 0x10 and body[1] in SLOT_NAMES and body[3] == 0x01 and len(body) == 6:
            off = records.BLOCK_OFFSETS[SLOT_NAMES[body[1]]]
            code = body[4] * 128 + body[5]
            buf[off + 1], buf[off + 2] = body[4], body[5]
            for i, v in enumerate(default_params(code)):
                buf[off + 4 + 2 * i], buf[off + 5 + 2 * i] = v & 0xFF, v >> 8
        elif body[0] == 0x10 and body[1] in SLOT_NAMES and body[3] == 0x02:
            off = records.BLOCK_OFFSETS[SLOT_NAMES[body[1]]]
            if buf[off + 1] * 128 + buf[off + 2] == body[4] * 128 + body[5]:
                i = body[6]
                buf[off + 4 + 2 * i], buf[off + 5 + 2 * i] = body[8], body[7]
        elif body[:5] == bytes([0x10, 0x00, 0x00, 0x00, 0x01]):
            idx = body[5]
            name = body[6:6 + am.NAME_LEN]
            buf[1] = idx
            buf[4:4 + am.NAME_LEN] = name
            Pedal.store[idx] = bytes(buf)
            Pedal.cur = idx
        Pedal.edit = bytes(buf)

    def send_sysex_batch(self, fs):
        for f in fs:
            self.send_sysex(f)

    def _queue_dump(self):
        rec = Pedal.edit
        nib = bytes(x for b in rec for x in (b >> 4, b & 15))
        size = len(nib) // am.PATCH_CHUNKS
        Pedal.out = [am.frame(am.KIND_DATA, bytes([0, 2, 0x14, 0, 1, rec[1], 0, n]) + nib[n * size:(n + 1) * size])
                     for n in range(am.PATCH_CHUNKS)]

    def collect(self, t, until=None):
        r, Pedal.out = Pedal.out, []
        return r


def sample_patches():
    """A few fake presets with no connection to anyone's real ones."""
    return {
        0: make_record(0, "CLEAN SPARKLE", {"amp": (True, 0, [55, 40, 50, 50, 55, 60]), "dly": (True, 9, [25, 15, 110, 1]),
                                           "rvb": (True, 4, [20, 35, 55, 1]), "cab": (True, 34, [3, 60, 50, 50])}),
        1: make_record(1, "CRUNCH RHYTHM", {"amp": (True, 55, [55, 50, 55, 45, 60, 55]), "fx2": (True, 9, [35, 55, 50, 60, 55]),
                                           "dly": (False, 9, [10, 10, 90, 0]), "rvb": (True, 4, [15, 30, 50, 0])}),
        2: make_record(2, "LEAD SOLO", {"amp": (True, 100, [70, 50, 60, 40, 55, 65]), "fx2": (True, 4, [80, 55, 60]),
                                       "dly": (True, 9, [35, 30, 110, 1]), "rvb": (True, 4, [25, 40, 50, 1])}),
        3: make_record(3, "AMBIENT PAD", {"fx1": (True, 137, [30, 1]), "amp": (True, 0, [40, 30, 50, 50, 50, 50]),
                                         "dly": (True, 9, [45, 50, 120, 1]), "rvb": (True, 4, [60, 80, 40, 1])}),
    }


def copy_store():
    return copy.deepcopy(Pedal.store)
