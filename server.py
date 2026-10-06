#!/usr/bin/env python3
"""ampero-bridge: HTTP front for the Hotone Ampero Mini, key-gated.

The pedal plugs into the server over USB. This service talks to it with libusb
(no ALSA) and exposes a small JSON API so any AI can build presets from a script.

Auth: X-Api-Key header, except GET /health (liveness only).

  GET  /health                     {"ok": true}, open, for the Docker healthcheck
  GET  /api/health                 pedal presence, request counters, USB device counts
  GET  /api/models                 the model library (names, codes, what each is based on); ?block=AMP, ?q=text
  GET  /api/usb                    interfaces and endpoints the pedal reports, plus every USB device this process sees
  GET  /api/patch/current          read the patch the pedal has selected (name + raw record)
  GET  /api/patch/<index>          same, but 409 unless <index> is the selected patch
  POST /api/patch/select           {"index": 75}            Program Change
  POST /api/block                  {"block": "rvb", "on": true}
  POST /api/midi/cc                {"cc": 22}   one Control Change, any CC 0-127 (22-25 = patch navigation)
  POST /api/model                  {"slot": "eq", "code": 4}
  POST /api/param                  {"slot": "eq", "model_code": 4, "param": 3, "value": 30}
  POST /api/patch/save             {"index": 75, "name": "WADE", "confirm": "SAVE P26-1"}
  GET  /api/patches/known          slot, label and name of every patch seen so far (no pedal access)
  GET  /api/history                states the bridge saw while polling the pedal (no pedal access)
  POST /api/notes                  {"patch": 75, "note": "...", "source": "todd"}  add a preset note (no pedal access)
  GET  /api/notes                  every note;  GET /api/notes/<patch>  notes for one patch (index or P26-1)
  GET  /api/favorites              starred presets and models (no pedal access)
  POST /api/favorites              {"kind": "patch", "id": 75, "starred": true}  star or unstar (kind: patch or model)
  POST /api/block/copy             {"from": 75, "to": 78, "block": "dly", "confirm": "COPY DLY P26-1 TO P27-1"}
  POST /api/backup                 start a dump of every patch to a file on the bridge;  GET /api/backup/status
  GET  /api/backups                the dump files;  GET /api/backups/<name>  download one
  POST /api/restore                put patches from a dump back on the pedal (dry run unless "apply": true)
  POST /api/import/prst            {"filename": "x.prst", "data": "<base64>"}  look inside a .prst file (read only)

Errors are JSON: {"error": "..."} with 400 bad request, 401 key, 429 too many
writes waiting (see Retry-After), 503 pedal missing or busy, 504 pedal silent, 502 other USB trouble.

Nothing here can leave the process stuck: see usbmidi.Link and docs/usb-lockups.md.
"""
import base64
import binascii
import datetime
import hmac
import json
import logging
import math
import os
import re
import signal
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import ampero_mini as am
import prst
import records
import usbmidi as usb

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ampero-bridge")


def _env(name: str, default: str) -> str:
    """An environment value, with an empty one (an unfilled ${VAR} in compose) counted as not set."""
    return (os.environ.get(name) or "").strip() or default

API_KEY = os.environ.get("API_KEY", "")
PORT = int(_env("PORT", "8080"))
HARD_DEADLINE = float(_env("AMPERO_HARD_DEADLINE_S", "20"))
MAX_BODY = 4096
MAX_BIG_BODY = 3_000_000   # restore and .prst uploads carry a whole backup or file
BIG_BODY_PATHS = {"/api/restore", "/api/import/prst"}
MAX_THREADS = 64     # simultaneous connections; more get a quick 503
MIN_KEY_LEN = 24
PLACEHOLDER_KEYS = {"change-me-to-a-long-random-string"}
ALLOW_UNPROVEN = os.environ.get("AMPERO_ALLOW_UNPROVEN_MODELS") == "1"
_HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_FILES = [p for p in (os.environ.get("AMPERO_MODELS_FILE"),
                            os.path.join(_HERE, "models.json"),
                            os.path.join(_HERE, "site", "models.json")) if p]
_models_cache = None

# Model codes that were set on the real pedal and read back, or read from the record
# with the model selected on the pedal (docs/models.md).
# An unproven code can crash the pedal, so /api/model only takes these unless
# AMPERO_ALLOW_UNPROVEN_MODELS=1.
PROVEN_MODELS = {
    # Every code read from the record while stepping the pedal's own list (docs/models.md).
    "fx1": {*range(0, 7), *range(32, 46), *range(64, 80), *range(128, 151)},
    "fx2": {*range(0, 16), *range(48, 55), *range(80, 94), *range(112, 135)},
    "amp": {*range(0, 10), *range(48, 67), *range(96, 114), *range(160, 165), *range(192, 200)},
    "cab": {*range(0, 50), *range(112, 122), *range(144, 154)},
    "eq": {*range(0, 7)},
    "dly": {*range(0, 17)},
    "rvb": {*range(0, 11)},
    "fx3": {*range(0, 17), *range(64, 77)},
    "nr": {0, 1},
}
CLIENT_TIMEOUT = 10  # seconds a client may stall before we drop the socket
GAP = 0.15           # pause between frames, the pacing the pedal was tested with

DATA_DIR = _env("AMPERO_DATA_DIR", "/data")
HISTORY_POLL = float(_env("AMPERO_HISTORY_POLL_S", "2"))      # pause between polls; 0 turns history off
HISTORY_WINDOW = float(_env("AMPERO_HISTORY_WINDOW_S", "600"))  # how far back to keep states
HISTORY_BUSY_MAX = float(_env("AMPERO_HISTORY_BUSY_MAX_S", "10"))  # longest wait while the patch keeps changing
HISTORY_MAX = 400     # states kept at most, whatever the window
WRITE_GAP = float(_env("AMPERO_WRITE_GAP_S", "0.5"))            # least seconds between two writes to the pedal
WRITE_SAVE_GAP = float(_env("AMPERO_WRITE_SAVE_GAP_S", "3"))    # quiet time before and after a save
WRITE_QUEUE_MAX = int(_env("AMPERO_WRITE_QUEUE_MAX", "30"))      # writes allowed to wait; more get a 429
NOTE_MAX_CHARS = 2000      # longest preset note
NOTES_PER_PATCH = 200      # notes kept per patch; more get a 400 (there is no delete)
NOTE_SOURCE_MAX = 60       # longest "source" label
FAVORITES_MAX = 500        # stars kept per kind
PATCH_COUNT = int(_env("AMPERO_PATCH_COUNT", "100"))        # patches a backup walks through, from index 0
PEDAL_SETTLE = float(_env("AMPERO_PEDAL_SETTLE_S", "0.4"))  # pause after a Program Change before reading
CORS_ORIGINS = {o.strip().rstrip("/") for o in os.environ.get("AMPERO_CORS_ORIGINS", "").split(",") if o.strip()}
KNOWN_REFRESH = 3600  # seconds between disk writes for a patch whose name did not change

link = usb.Link(hard_deadline=HARD_DEADLINE)


class TooFast(Exception):
    """Too many writes are already waiting for the pedal. Try again after Retry-After seconds."""

    def __init__(self, retry_after: int):
        super().__init__(f"too many writes waiting for the pedal; retry in {retry_after} s")
        self.retry_after = retry_after
        self.extra = {"retry_after": retry_after}


class WriteGate:
    """Lets one write at a time reach the pedal, with a pause after each.

    A Mini once stopped on a firmware assert during heavy use. The cause
    is not proven; giving the pedal room between writes is the cautious fix. Writes wait their
    turn here. A read that touches the pedal does not wait in line but holds off until the
    write before it is done and the quiet time has passed (settle).
    A save also waits for quiet before it goes out, and holds the next write back after it.
    """

    def __init__(self):
        self.turn = threading.Lock()
        self.count = threading.Lock()
        self.waiting = 0
        self.last_end = 0.0   # monotonic time the previous write finished
        self.next_ok = 0.0    # earliest start for the next ordinary write
        self.active = 0       # writes on the wire right now (0 or 1)

    def run(self, save: bool, fn):
        with self.count:
            if self.waiting >= WRITE_QUEUE_MAX:
                raise TooFast(max(1, math.ceil(WRITE_QUEUE_MAX * max(WRITE_GAP, 0.5))))
            self.waiting += 1
        try:
            with self.turn:
                start_ok = self.next_ok
                if save:
                    start_ok = max(start_ok, self.last_end + WRITE_SAVE_GAP)
                pause = start_ok - time.monotonic()
                if pause > 0:
                    time.sleep(pause)
                with self.count:
                    self.active += 1
                try:
                    return fn()
                finally:
                    self.last_end = time.monotonic()
                    self.next_ok = self.last_end + (WRITE_SAVE_GAP if save else WRITE_GAP)
                    with self.count:
                        self.active -= 1
        finally:
            with self.count:
                self.waiting -= 1


    def settle(self):
        """For reads that touch the pedal: wait until no write is on the wire and the quiet
        time after the last write (3 s after a save) is over. A read never joins the line
        of writes, takes a write slot or counts toward the 429 limit."""
        while True:
            with self.count:
                busy = self.active > 0
            pause = self.next_ok - time.monotonic()
            if not busy and pause <= 0:
                return
            time.sleep(0.05 if busy or pause > 0.05 else max(pause, 0.001))


gate = WriteGate()


class PatchNotCurrent(Exception):
    """The pedal answered with a different patch than the one asked for.

    The editor's read frames return the pedal's CURRENT patch whatever index
    they carry (found on the real pedal, Oct 3, 2026: reads for 0, 1, 74 and 76
    all came back as 75). Never label that data with the requested index.
    """

    def __init__(self, asked: int, got: dict):
        super().__init__(f"the pedal answered with its current patch {got['label']} ({got['name']!r}), "
                         f"not {am.patch_label(asked)}; select the patch first")
        self.extra = {"asked_index": asked, "current_index": got["index"],
                      "current_label": got["label"], "current_name": got["name"]}


class Known:
    """Names of the patches the bridge has seen, kept in one small JSON file.

    It only remembers what a read already returned: nothing extra is read from the
    pedal and nothing is written to it. A broken or unwritable file never makes a
    pedal call fail; the cache just stays in memory.
    """

    def __init__(self, directory: str):
        self.path = os.path.join(directory, "known-patches.json")
        self.lock = threading.Lock()
        self.items: dict[str, dict] = {}
        self.persistent = True
        self._warned = False
        try:
            with open(self.path) as f:
                data = json.load(f)
            for k, v in data.get("patches", {}).items():
                if k.isdigit() and isinstance(v, dict) and isinstance(v.get("name"), str):
                    self.items[k] = {"name": v["name"], "label": str(v.get("label", "")),
                                     "seen": str(v.get("seen", "")), "source": str(v.get("source", "read"))}
        except FileNotFoundError:
            pass
        except (OSError, ValueError, AttributeError) as e:
            log.warning("known patches file ignored: %s", e)

    def record(self, index: int, label: str, name: str, source: str = "read"):
        now = datetime.datetime.now(datetime.timezone.utc)
        key = str(index)
        with self.lock:
            old = self.items.get(key)
            if old and old["name"] == name and old["source"] == source:
                try:
                    age = (now - datetime.datetime.fromisoformat(old["seen"])).total_seconds()
                except ValueError:
                    age = KNOWN_REFRESH + 1
                if age < KNOWN_REFRESH:
                    return
            self.items[key] = {"name": name, "label": label, "source": source,
                               "seen": now.isoformat(timespec="seconds")}
            self._write()

    def _write(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump({"patches": self.items}, f)
            os.replace(tmp, self.path)
            self.persistent = True
        except OSError as e:
            self.persistent = False
            if not self._warned:
                self._warned = True
                log.warning("cannot save known patches to %s (%s); keeping them in memory only",
                            self.path, e)

    def listing(self) -> dict:
        with self.lock:
            rows = [{"index": int(k), **v} for k, v in sorted(self.items.items(), key=lambda kv: int(kv[0]))]
            return {"count": len(rows), "persistent": self.persistent, "patches": rows}


known = Known(DATA_DIR)


class History:
    """The last few minutes of the pedal's edit buffer, one entry per change.

    A background thread reads the current patch every few seconds and adds it here
    when the record is different from the last one. The point is to catch a state that
    came and went between two reads from a client, for example while a knob is being
    turned on the pedal. It only reads. Nothing is written to the pedal or to disk.
    """

    def __init__(self, window: float, limit: int):
        self.window, self.limit = window, limit
        self.lock = threading.Lock()
        self.entries: list[dict] = []
        self.polls = 0
        self.errors = 0
        self.last_poll = None     # wall clock of the last good poll
        self.last_error = None
        self.delay = HISTORY_POLL  # seconds the poller is waiting between reads right now
        self.mode = "idle"         # idle, busy (the patch keeps changing) or errors

    def add(self, got: dict, now: float | None = None):
        now = time.time() if now is None else now
        with self.lock:
            self.polls += 1
            self.last_poll = now
            last = self.entries[-1] if self.entries else None
            changed = not (last and last["record_hex"] == got["record_hex"])
            if not changed:
                last["last_seen"] = now
            else:
                self.entries.append({"t": now, "last_seen": now, "index": got["index"], "label": got["label"],
                                     "name": got["name"], "record_hex": got["record_hex"],
                                     "changed_bytes": _diff(last["record_hex"], got["record_hex"]) if last else None})
            cutoff = now - self.window
            while len(self.entries) > 1 and (self.entries[0]["last_seen"] < cutoff or len(self.entries) > self.limit):
                self.entries.pop(0)
            return changed

    def fail(self, exc: Exception):
        with self.lock:
            self.errors += 1
            self.last_error = f"{type(exc).__name__}: {exc}"

    def pace(self, delay: float, mode: str):
        with self.lock:
            self.delay, self.mode = delay, mode

    def status(self) -> dict:
        with self.lock:
            return {"enabled": HISTORY_POLL > 0, "poll_s": HISTORY_POLL, "window_s": self.window,
                    "entries": len(self.entries), "polls": self.polls, "poll_errors": self.errors,
                    "current_poll_s": self.delay, "pace": self.mode,
                    "last_poll": self.last_poll, "last_error": self.last_error}

    def listing(self, since: float = 0.0, with_hex: bool = True) -> dict:
        with self.lock:
            rows = [dict(e) for e in self.entries if e["last_seen"] >= since]
        if not with_hex:
            for r in rows:
                del r["record_hex"]
        return {**self.status(), "now": time.time(), "states": rows}


def _diff(a: str, b: str):
    """Byte offsets where two record hex strings differ, or None if they are not comparable."""
    if len(a) != len(b):
        return None
    return [i // 2 for i in range(0, len(a), 2) if a[i:i + 2] != b[i:i + 2]]


history = History(HISTORY_WINDOW, HISTORY_MAX)


class Pacer:
    """How long the background poller waits before its next read.

    Every read uses the USB link for a second or two, and a pedal that is being
    stepped through models or edited does not like that. So the wait grows while the
    patch keeps changing (x2, then x4, never more than HISTORY_BUSY_MAX_S) and goes
    back to the base after two quiet reads in a row. After an error it doubles up to
    30 seconds and resets on the next good read. The wait is never shorter than the
    last read took, so the pedal gets at least as much rest as work.
    """

    def __init__(self, base: float):
        self.base = base
        self.level = 0      # 0 idle, 1 and 2 busy
        self.quiet = 0
        self.errors = 0     # failed reads in a row

    def ok(self, changed: bool, took: float = 0.0) -> float:
        self.errors = 0
        if changed:
            self.level, self.quiet = min(self.level + 1, 2), 0
        else:
            self.quiet += 1
            if self.quiet >= 2:
                self.level = 0
        d = min(self.base * 2 ** self.level, max(self.base, HISTORY_BUSY_MAX))
        return max(d, took)

    def failed(self) -> float:
        self.errors += 1
        self.level = 0
        return min(30.0, max(self.base * 4, 4.0 if self.base else 0.0) * 2 ** (self.errors - 1))

    def mode(self) -> str:
        return "errors" if self.errors else ("busy" if self.level else "idle")


def poll_history(stop: threading.Event | None = None, rounds: int | None = None):
    """Read the pedal now and then and keep what it says. Never raises, never writes.

    One read at a time: the next wait starts only after the read has finished. The wait
    adapts, see Pacer. Skips a round while the pedal is unplugged. A client request that
    arrives during a poll waits for it (about two seconds).
    """
    n = 0
    pacer = Pacer(HISTORY_POLL)
    delay = HISTORY_POLL
    while rounds is None or n < rounds:
        n += 1
        if stop is not None and stop.wait(delay):
            return
        if stop is None:
            time.sleep(delay)
        try:
            if not usb.is_present():
                delay = HISTORY_POLL
                continue
            t0 = time.monotonic()
            changed = history.add(read_current_patch())
            delay = pacer.ok(changed, time.monotonic() - t0)
        except Exception as e:
            history.fail(e)
            if history.errors in (1, 10, 100):
                log.warning("history poll failed (%d so far): %s", history.errors, e)
            delay = pacer.failed()
        history.pace(delay, pacer.mode())


class Notes:
    """Free-text notes about presets, kept in one JSON file next to the known patch names.

    Notes are only ever added: there is no edit and no delete call. Nothing here talks
    to the pedal. A note is stored under the patch slot (0-based index) it is about.
    """

    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.items: dict[str, list[dict]] = {}
        try:
            with open(self.path) as f:
                data = json.load(f)
            for k, v in data.get("patches", {}).items():
                if k.isdigit() and isinstance(v, list):
                    self.items[k] = [n for n in v if isinstance(n, dict) and isinstance(n.get("note"), str)]
        except FileNotFoundError:
            pass
        except (OSError, ValueError, AttributeError) as e:
            log.warning("preset notes file ignored: %s", e)

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"version": 1, "patches": self.items}, f)
        os.replace(tmp, self.path)

    def add(self, index: int, note: str, source: str) -> dict:
        entry = {"n": 0, "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                 "source": source, "note": note}
        with self.lock:
            lst = self.items.setdefault(str(index), [])
            if len(lst) >= NOTES_PER_PATCH:
                raise am.ProtocolError(f"patch {am.patch_label(index)} already has {NOTES_PER_PATCH} notes")
            entry["n"] = (lst[-1].get("n", len(lst)) + 1) if lst else 1
            lst.append(entry)
            try:
                self._save()
            except OSError as e:
                lst.pop()
                log.warning("preset notes not saved: %s", e)
                raise OSError("notes file is not writable") from e
            return {"ok": True, "index": index, "label": am.patch_label(index), "note": dict(entry),
                    "count": len(lst)}

    def for_patch(self, index: int) -> dict:
        with self.lock:
            lst = [dict(n) for n in self.items.get(str(index), [])]
        return {"index": index, "label": am.patch_label(index), "count": len(lst), "notes": lst}

    def listing(self) -> dict:
        with self.lock:
            out = [{"index": int(k), "label": am.patch_label(int(k)), "count": len(v),
                    "notes": [dict(n) for n in v]} for k, v in sorted(self.items.items(), key=lambda kv: int(kv[0])) if v]
        return {"count": sum(p["count"] for p in out), "patches": out}


NOTES_FILE = os.environ.get("AMPERO_NOTES_FILE") or os.path.join(DATA_DIR, "preset-notes.json")
notes = Notes(NOTES_FILE)


def _patch_ref(value) -> int:
    """A patch as a 0-based index (75) or a label such as "P26-1"."""
    if isinstance(value, bool):
        raise am.ProtocolError("'patch' must be an index or a label like P26-1")
    if isinstance(value, str):
        m = re.fullmatch(r"\s*[Pp](\d{1,3})-(\d)\s*", value)
        if m:
            bank, n = int(m.group(1)), int(m.group(2))
            if bank < 1 or not 1 <= n <= am.PATCHES_PER_BANK:
                raise am.ProtocolError("patch label out of range")
            value = (bank - 1) * am.PATCHES_PER_BANK + (n - 1)
    try:
        i = int(value)
    except (TypeError, ValueError, OverflowError):
        raise am.ProtocolError("'patch' must be an index or a label like P26-1")
    if not 0 <= i <= am.MAX_PATCH:
        raise am.ProtocolError(f"patch index must be 0-{am.MAX_PATCH}")
    return i


def add_note(data: dict) -> dict:
    if "patch" not in data:
        raise am.ProtocolError("missing 'patch'")
    idx = _patch_ref(data["patch"])
    note = data.get("note")
    if not isinstance(note, str) or not note.strip():
        raise am.ProtocolError("'note' must be non-empty text")
    if len(note) > NOTE_MAX_CHARS:
        raise am.ProtocolError(f"'note' is {len(note)} characters; the limit is {NOTE_MAX_CHARS}")
    source = data.get("source", "")
    if not isinstance(source, str) or len(source) > NOTE_SOURCE_MAX:
        raise am.ProtocolError(f"'source' must be text of at most {NOTE_SOURCE_MAX} characters")
    return notes.add(idx, note.strip(), source.strip())


class Favorites:
    """Starred presets and models, kept on the bridge so every browser sees the same stars.

    Two kinds: "patch" (stored by 0-based index) and "model" (stored as "AMP:55", the block
    and the model code). Nothing here talks to the pedal.
    """

    KINDS = ("patch", "model")

    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.items: dict[str, dict[str, str]] = {k: {} for k in self.KINDS}
        try:
            with open(self.path) as f:
                data = json.load(f)
            for kind in self.KINDS:
                for key, ts in (data.get(kind) or {}).items():
                    if isinstance(key, str) and isinstance(ts, str):
                        self.items[kind][key] = ts
        except FileNotFoundError:
            pass
        except (OSError, ValueError, AttributeError) as e:
            log.warning("favorites file ignored: %s", e)

    def _save(self):
        tmp = self.path + ".tmp"
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(tmp, "w") as f:
            json.dump({"version": 1, **self.items}, f)
        os.replace(tmp, self.path)

    def set(self, kind: str, key: str, starred: bool) -> dict:
        with self.lock:
            before = dict(self.items[kind])
            if starred:
                if key not in self.items[kind] and len(self.items[kind]) >= FAVORITES_MAX:
                    raise am.ProtocolError(f"already {FAVORITES_MAX} starred {kind}s; unstar one first")
                self.items[kind].setdefault(key, datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
            else:
                self.items[kind].pop(key, None)
            try:
                self._save()
            except OSError as e:
                self.items[kind] = before
                log.warning("favorites not saved: %s", e)
                raise OSError("favorites file is not writable") from e
        return self.listing()

    def listing(self) -> dict:
        with self.lock:
            patches = sorted(self.items["patch"], key=int)
            models = sorted(self.items["model"])
            return {"patches": [{"index": int(k), "label": am.patch_label(int(k)), "starred_at": self.items["patch"][k]}
                                for k in patches],
                    "models": [{"id": k, "starred_at": self.items["model"][k]} for k in models],
                    "count": len(patches) + len(models)}


FAVORITES_FILE = os.environ.get("AMPERO_FAVORITES_FILE") or os.path.join(DATA_DIR, "favorites.json")
favorites = Favorites(FAVORITES_FILE)


def set_favorite(data: dict) -> dict:
    kind = data.get("kind", "patch")
    if kind not in Favorites.KINDS:
        raise am.ProtocolError("'kind' must be patch or model")
    if "id" not in data:
        raise am.ProtocolError("missing 'id'")
    starred = data.get("starred", True)
    if not isinstance(starred, bool):
        raise am.ProtocolError("'starred' must be true or false")
    if kind == "patch":
        key = str(_patch_ref(data["id"]))
    else:
        key = str(data["id"]).strip().upper()
        block, _, code = key.partition(":")
        if block not in (b.upper() for b in records.BLOCKS) or not code.isdigit() or len(code) > 4:
            raise am.ProtocolError("a model id looks like AMP:55 (block, colon, model code)")
        key = f"{block}:{int(code)}"
    return favorites.set(kind, key, starred)


def read_current_patch() -> dict:
    """Read the patch the pedal currently has selected. Reads only."""
    def run(p):
        p.drain()
        frames = []
        for req in am.read_patch_requests(0):
            p.send_sysex(req)
            frames += p.collect(GAP)
        frames += p.collect(0.5)
        try:
            return am.decode_patch(frames)
        except am.ProtocolError as e:
            raise usb.PedalTimeout(str(e))
    gate.settle()
    got = link.session("read current patch", run)
    known.record(got["index"], got["label"], got["name"])
    return got


def read_patch(index: int) -> dict:
    """Read patch `index`, only if it is the one the pedal has selected."""
    got = read_current_patch()
    if got["index"] != index:
        raise PatchNotCurrent(index, got)
    return got


def send_midi(msg: bytes, name: str):
    gate.run(False, lambda: link.session(name, lambda p: p.send_midi(msg)))


def send_sysex(frames: list[bytes], name: str):
    def run(p):
        if len(frames) == 1:
            p.send_sysex(frames[0])
        else:
            p.send_sysex_batch(frames)
    gate.run(name.startswith("save"), lambda: link.session(name, run))


# --- workflows: several pedal steps in a row ---------------------------------------------
#
# Copying a block, backing up and restoring all walk the pedal through patches. Only one
# of them may run at a time, because each one selects patches and the edit buffer is shared.

class WorkflowBusy(Exception):
    """A copy, backup or restore is already using the pedal."""


workflow = threading.Lock()


def select_patch(index: int):
    send_midi(am.program_change(index), f"select {index}")
    time.sleep(PEDAL_SETTLE)


def _record(got: dict) -> bytes:
    return records.to_bytes(got["record_hex"])


def apply_diff(d: dict):
    """Send the one write that fixes one difference (the caller checked it is writable)."""
    slot, field = d["slot"], d["field"]
    if field == "power":
        send_midi(am.block_power(slot, d["want"]), f"block {slot}")
    elif field == "level":
        send_midi(am.raw_cc(records.LEVEL_CC, d["want"]), "patch level")
    elif field == "model":
        send_sysex([am.model_select(slot, d["want"])], "model")
    else:
        send_sysex([am.param_set(slot, d["model_code"], d["index"], d["want"])], "param")


def converge(index: int, want: bytes, slots, level: bool, apply: bool = True) -> dict:
    """Make the selected patch `index` look like `want` as far as the bridge can write.

    Reads the patch, writes the power, level and model differences, reads again (a model
    write resets the knobs), writes the param differences, then reads once more to see what
    is still different. Nothing is saved. With apply=False it only reads and reports.
    """
    have = _record(read_patch(index))
    plan = records.summarize(records.diffs(want, have, slots, level), PROVEN_MODELS, ALLOW_UNPROVEN)
    report = {"written": 0, "param_writes_pending": False}
    if not apply:
        report["would_write"] = plan["writable"]
        report["param_writes_pending"] = any(d["field"] == "model" for d in plan["writable"])
        report["stuck"] = plan["stuck"]
        return report
    first = [d for d in plan["writable"] if d["field"] != "param"]
    for d in first:
        apply_diff(d)
    report["written"] += len(first)
    if any(d["field"] == "model" for d in first):
        time.sleep(PEDAL_SETTLE)
        have = _record(read_patch(index))
        plan = records.summarize(records.diffs(want, have, slots, level), PROVEN_MODELS, ALLOW_UNPROVEN)
    params = [d for d in plan["writable"] if d["field"] == "param"]
    for d in params:
        apply_diff(d)
    report["written"] += len(params)
    if first or params:
        time.sleep(PEDAL_SETTLE)
    final = _record(read_patch(index))
    left = records.summarize(records.diffs(want, final, slots, level), PROVEN_MODELS, ALLOW_UNPROVEN)
    report["stuck"] = left["stuck"]
    report["unwritten"] = left["writable"]    # writable, yet still different after the write
    return report


def copy_block(data: dict) -> dict:
    """Copy one block's model, switch and knobs from one patch onto another (edit buffer only)."""
    for key in ("from", "to", "block"):
        if key not in data:
            raise am.ProtocolError(f"missing {key!r}")
    src, dst = _patch_ref(data["from"]), _patch_ref(data["to"])
    block = str(data["block"]).lower()
    if block not in am.SLOTS:
        raise am.ProtocolError(f"block must be one of {sorted(am.SLOTS)}")
    if src == dst:
        raise am.ProtocolError("'from' and 'to' are the same patch")
    dry = data.get("dry_run", False)
    if not isinstance(dry, bool):
        raise am.ProtocolError("'dry_run' must be true or false")
    want = f"COPY {block.upper()} {am.patch_label(src)} TO {am.patch_label(dst)}"
    if not dry and data.get("confirm") != want:
        raise am.ProtocolError("copying selects both patches, so unsaved edits on the pedal are lost "
                               f'(set "dry_run": true to only look, or send "confirm": "{want}")')
    if not workflow.acquire(blocking=False):
        raise WorkflowBusy("a copy, backup or restore is already running")
    try:
        select_patch(src)
        source = _record(read_patch(src))
        select_patch(dst)
        report = converge(dst, source, [block], False, apply=not dry)
        name = records.name_of(_record(read_patch(dst))) if not dry else None
    finally:
        workflow.release()
    out = {"ok": not report["stuck"] and not report.get("unwritten"), "dry_run": dry, "block": block,
           "from": src, "from_label": am.patch_label(src), "to": dst, "to_label": am.patch_label(dst), **report}
    if not dry:
        out["saved"] = False
        out["note"] = (f"changed the edit buffer of {am.patch_label(dst)} only. To keep it, POST /api/patch/save with "
                       f'{{"index": {dst}, "name": "{name}", "confirm": "SAVE {am.patch_label(dst)}"}}')
    return out


class Job:
    """A long workflow running in a thread, so the request that started it can return."""

    def __init__(self, kind: str, total: int):
        self.id = uuid.uuid4().hex[:8]
        self.kind, self.total, self.done = kind, total, 0
        self.state = "running"
        self.started = time.time()
        self.finished = None
        self.result = None
        self.error = None
        self.step = ""

    def view(self) -> dict:
        return {"id": self.id, "kind": self.kind, "state": self.state, "done": self.done, "total": self.total,
                "step": self.step, "started": self.started, "finished": self.finished,
                "result": self.result, "error": self.error}


last_job: Job | None = None


def start_job(kind: str, total: int, fn) -> dict:
    """Run fn(job) in a thread while holding the workflow lock."""
    global last_job
    if not workflow.acquire(blocking=False):
        raise WorkflowBusy("a copy, backup or restore is already running")
    job = Job(kind, total)
    last_job = job

    def run():
        try:
            job.result = fn(job)
            job.state = "done"
        except Exception as e:
            log.warning("%s job failed: %s: %s", kind, type(e).__name__, e)
            job.error = f"{type(e).__name__}: {e}"
            job.state = "failed"
        finally:
            job.finished = time.time()
            workflow.release()

    threading.Thread(target=run, daemon=True, name=f"job-{kind}").start()
    return job.view()


def job_status() -> dict:
    return last_job.view() if last_job else {"state": "none"}


BACKUP_DIR = os.path.join(DATA_DIR, "backups")
BACKUP_NAME = re.compile(r"ampero-backup-\d{8}-\d{6}\.json")


def _patch_list(value, default_count: int) -> list[int]:
    if value is None:
        return list(range(min(default_count, am.MAX_PATCH + 1)))
    if not isinstance(value, list) or not value:
        raise am.ProtocolError("'patches' must be a non-empty list of indexes or labels")
    out = sorted({_patch_ref(v) for v in value})
    if len(out) > am.MAX_PATCH + 1:
        raise am.ProtocolError("too many patches")
    return out


def _return_to(index: int | None):
    if index is not None:
        try:
            select_patch(index)
        except Exception as e:
            log.warning("could not go back to patch %s: %s", index, e)


def _current_index() -> int | None:
    try:
        return read_current_patch()["index"]
    except Exception:
        return None


def start_backup(data: dict) -> dict:
    wanted = _patch_list(data.get("patches"), PATCH_COUNT)

    def run(job: Job) -> dict:
        origin = _current_index()
        got, skipped = [], []
        try:
            for i in wanted:
                job.step = f"reading {am.patch_label(i)}"
                try:
                    select_patch(i)
                    got.append(read_patch(i))
                except (PatchNotCurrent, usb.PedalTimeout, am.ProtocolError) as e:
                    skipped.append({"index": i, "label": am.patch_label(i), "error": str(e)})
                job.done += 1
        finally:
            _return_to(origin)
        if not got:
            raise RuntimeError("no patch could be read, nothing was saved")
        name = "ampero-backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"
        os.makedirs(BACKUP_DIR, exist_ok=True)
        path = os.path.join(BACKUP_DIR, name)
        with open(path + ".tmp", "wb") as f:
            f.write(records.dumps(records.make_backup(got, skipped)))
        os.replace(path + ".tmp", path)
        return {"name": name, "patches": len(got), "skipped": skipped, "bytes": os.path.getsize(path)}

    return start_job("backup", len(wanted), run)


def list_backups() -> dict:
    rows = []
    try:
        for name in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if BACKUP_NAME.fullmatch(name):
                st = os.stat(os.path.join(BACKUP_DIR, name))
                rows.append({"name": name, "bytes": st.st_size, "modified": int(st.st_mtime)})
    except FileNotFoundError:
        pass
    return {"count": len(rows), "backups": rows}


def read_backup_file(name: str) -> bytes:
    if not BACKUP_NAME.fullmatch(name):
        raise LookupError("no such backup")
    try:
        with open(os.path.join(BACKUP_DIR, name), "rb") as f:
            return f.read()
    except FileNotFoundError:
        raise LookupError("no such backup")


def start_restore(data: dict) -> dict:
    if "backup" in data:
        wanted_records = records.load_backup(data["backup"])
    elif "name" in data:
        try:
            wanted_records = records.load_backup(json.loads(read_backup_file(str(data["name"]))))
        except ValueError:
            raise records.RecordError("that backup file is not valid JSON")
    else:
        raise am.ProtocolError("send the backup itself as 'backup' or the name of one on the bridge as 'name'")
    chosen = _patch_list(data.get("patches"), 0) if "patches" in data else sorted(wanted_records)
    missing = [i for i in chosen if i not in wanted_records]
    if missing:
        raise am.ProtocolError("the backup has no patch " + ", ".join(am.patch_label(i) for i in missing))
    apply = data.get("apply", False)
    partial_ok = data.get("allow_partial", False)
    if not isinstance(apply, bool) or not isinstance(partial_ok, bool):
        raise am.ProtocolError("'apply' and 'allow_partial' must be true or false")
    if apply:
        want = f"RESTORE {len(chosen)} PATCHES"
        if data.get("confirm") != want:
            raise am.ProtocolError(f'restoring overwrites stored patches: send "confirm": "{want}" '
                                   '(leave out "apply" for a dry run that only reports the differences)')

    def run(job: Job) -> dict:
        origin = _current_index()
        rows = []
        try:
            for i in chosen:
                rec = wanted_records[i]
                name = records.name_of(rec)
                job.step = f"{'restoring' if apply else 'checking'} {am.patch_label(i)}"
                row = {"index": i, "label": am.patch_label(i), "name": name}
                try:
                    select_patch(i)
                    rep = converge(i, rec, records.BLOCKS, True, apply=apply)
                    row.update(rep)
                    if not apply:
                        row["status"] = "differs" if rep["would_write"] or rep["stuck"] else "same"
                    elif rep["stuck"] or rep.get("unwritten"):
                        if partial_ok:
                            send_sysex(am.save_patch(i, name), f"save {i}")
                            known.record(i, am.patch_label(i), name, "save")
                            row["status"] = "saved-partial"
                        else:
                            row["status"] = "not-saved"
                    else:
                        send_sysex(am.save_patch(i, name), f"save {i}")
                        known.record(i, am.patch_label(i), name, "save")
                        row["status"] = "restored"
                except (PatchNotCurrent, usb.PedalTimeout, am.ProtocolError) as e:
                    row["status"] = "failed"
                    row["error"] = str(e)
                rows.append(row)
                job.done += 1
        finally:
            _return_to(origin)
        return {"apply": apply, "patches": rows}

    return start_job("restore" if apply else "restore-check", len(chosen), run)


def inspect_prst(data: dict) -> dict:
    try:
        raw = base64.b64decode(str(data.get("data", "")), validate=True)
    except (binascii.Error, ValueError):
        raise am.ProtocolError("'data' must be the file as base64")
    return {"filename": str(data.get("filename", ""))[:120], **prst.inspect(raw)}


def _int(data: dict, key: str) -> int:
    if key not in data:
        raise am.ProtocolError(f"missing {key!r}")
    if isinstance(data[key], bool):
        raise am.ProtocolError(f"{key!r} must be a number")
    try:
        return int(data[key])
    except (TypeError, ValueError, OverflowError):
        raise am.ProtocolError(f"{key!r} must be a number")


def handle_post(path: str, data: dict) -> dict:
    if path == "/api/notes":
        return add_note(data)
    if path == "/api/favorites":
        return set_favorite(data)
    if path == "/api/block/copy":
        return copy_block(data)
    if path == "/api/backup":
        return start_backup(data)
    if path == "/api/restore":
        return start_restore(data)
    if path == "/api/import/prst":
        return inspect_prst(data)
    if path == "/api/patch/select":
        idx = _int(data, "index")
        send_midi(am.program_change(idx), f"select {idx}")
        return {"ok": True, "label": am.patch_label(idx)}
    if path == "/api/block":
        block, on = str(data.get("block", "")), bool(data.get("on"))
        send_midi(am.block_power(block, on), f"block {block}")
        return {"ok": True}
    if path == "/api/midi/cc":
        cc = _int(data, "cc")
        value = _int(data, "value") if "value" in data else 127
        send_midi(am.raw_cc(cc, value), f"cc {cc}")
        return {"ok": True, "cc": cc, "value": value,
                "note": "no reply exists; read /api/history to see what the pedal did"}
    if path == "/api/model":
        slot, code = data.get("slot"), _int(data, "code")
        proven = PROVEN_MODELS.get(slot) if isinstance(slot, str) else None
        if not ALLOW_UNPROVEN and (proven is None or code not in proven):
            raise am.ProtocolError(f"model code {code} is not proven for slot {slot!r} "
                                   f"(proven: {sorted(proven or [])}); see docs/models.md, "
                                   "or set AMPERO_ALLOW_UNPROVEN_MODELS=1")
        send_sysex([am.model_select(slot, code)], "model")
        return {"ok": True}
    if path == "/api/param":
        frame = am.param_set(data.get("slot"), _int(data, "model_code"),
                             _int(data, "param"), _int(data, "value"))
        send_sysex([frame], "param")
        return {"ok": True}
    if path == "/api/patch/save":
        idx = _int(data, "index")
        want = f"SAVE {am.patch_label(idx)}"
        if data.get("confirm") != want:
            raise am.ProtocolError(f'saving overwrites a stored patch: send "confirm": "{want}"')
        send_sysex(am.save_patch(idx, str(data.get("name", ""))), f"save {idx}")
        known.record(idx, am.patch_label(idx), str(data.get("name", "")), "save")
        # The pedal sends nothing back for a save. Only its screen shows the result,
        # so the reply says written, not confirmed.
        return {"ok": True, "label": am.patch_label(idx), "verified": False,
                "note": "no reply exists for save; read the patch back to check"}
    raise LookupError(path)


STATUS = {
    usb.PedalNotConnected: 503, usb.PedalBusy: 503, usb.PedalGone: 503,
    usb.PedalTimeout: 504, usb.UsbMidiError: 502,
    am.ProtocolError: 400, LookupError: 404, PatchNotCurrent: 409, WorkflowBusy: 409, TooFast: 429,
}
# Bad input that slipped past the checks above. Reported as 400 with a fixed message.
BAD_INPUT = (TypeError, ValueError, OverflowError, UnicodeError)


def status_for(exc: Exception) -> int:
    for cls, code in STATUS.items():
        if isinstance(exc, cls):
            return code
    return 500


class Handler(BaseHTTPRequestHandler):
    server_version = "ampero-bridge/2.9.0"
    timeout = CLIENT_TIMEOUT   # socket timeout: a stalled client cannot pin a thread

    def version_string(self):
        return "ampero-bridge"   # no version or Python build in the Server header

    def _cors(self):
        """Let a page on an allowed origin (the model library site) call the API from the browser."""
        origin = (self.headers.get("Origin") or "").rstrip("/")
        if origin and origin in CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            return True
        return False

    def _send(self, code: int, obj: dict | bytes, retry_after: int | None = None, headers: dict | None = None):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        if retry_after is not None:
            self.send_header("Retry-After", str(retry_after))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        key = self.headers.get("X-Api-Key", "")
        return bool(API_KEY) and hmac.compare_digest(key.encode(), API_KEY.encode())

    def _body(self, limit: int = MAX_BODY) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise am.ProtocolError("bad Content-Length")
        if n < 0:
            raise am.ProtocolError("bad Content-Length")
        if n > limit:
            raise am.ProtocolError("body too large")
        if not n:
            return {}
        try:
            data = json.loads(self.rfile.read(n))
        except ValueError:
            raise am.ProtocolError("body is not valid JSON")
        if not isinstance(data, dict):
            raise am.ProtocolError("body must be a JSON object")
        return data

    def _run(self, fn):
        try:
            self._send(200, fn())
        except Exception as e:
            code = status_for(e)
            if code == 500:
                if isinstance(e, BAD_INPUT):
                    log.info("%s %s -> 400 %s: %s", self.command, self.path, type(e).__name__, e)
                    self._send(400, {"error": "invalid request", "kind": "BadRequest"})
                else:
                    log.warning("%s %s -> 500 %s: %s", self.command, self.path, type(e).__name__, e)
                    self._send(500, {"error": "internal error", "kind": "InternalError"})
                return
            if code >= 500:
                log.warning("%s %s -> %d %s: %s", self.command, self.path, code, type(e).__name__, e)
            self._send(code, {"error": str(e), "kind": type(e).__name__, **getattr(e, "extra", {})},
                       getattr(e, "retry_after", None))

    def _run_raw(self, fn, headers: dict):
        """Like _run for a reply that is already JSON text (a file)."""
        try:
            self._send(200, fn(), headers=headers)
        except Exception as e:
            code = status_for(e)
            self._send(code, {"error": str(e) if code < 500 else "internal error", "kind": type(e).__name__})

    def do_OPTIONS(self):
        """Answer a browser's preflight. Nothing is allowed unless AMPERO_CORS_ORIGINS lists the origin."""
        self.send_response(204)
        if self._cors():
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "X-Api-Key, Content-Type")
            self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._send(200, {"ok": True})
            return
        if not self._authed():
            self._send(401, {"error": "unauthorized"})
            return
        if path == "/api/health":
            self._send(200, {"ok": True, "pedal_connected": usb.is_present(), "usb": link.status(),
                              "usb_seen": usb.seen(), "history": history.status()})
        elif path == "/api/patches/known":
            self._send(200, known.listing())
        elif path == "/api/history":
            self._run(lambda: history_view(urlparse(self.path).query))
        elif path == "/api/notes":
            self._send(200, notes.listing())
        elif path == "/api/favorites":
            self._send(200, favorites.listing())
        elif path == "/api/backup/status":
            self._send(200, job_status())
        elif path == "/api/backups":
            self._send(200, list_backups())
        elif path.startswith("/api/backups/") and path.count("/") == 3:
            name = path.rsplit("/", 1)[1]
            self._run_raw(lambda: read_backup_file(name), {"Content-Disposition": f'attachment; filename="{name}"'})
        elif path.startswith("/api/notes/") and path.count("/") == 3:
            self._run(lambda: notes.for_patch(_patch_ref(path.rsplit("/", 1)[1])))
        elif path == "/api/models":
            self._run(lambda: models_view(urlparse(self.path).query))
        elif path == "/api/usb":
            self._run(usb.describe)
        elif path == "/api/patch/current":
            self._run(read_current_patch)
        elif path.startswith("/api/patch/") and path.count("/") == 3:
            self._run(lambda: read_patch(_idx(path.rsplit("/", 1)[1])))
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._authed():
            self._send(401, {"error": "unauthorized"})
            return
        limit = MAX_BIG_BODY if path in BIG_BODY_PATHS else MAX_BODY
        self._run(lambda: handle_post(path, self._body(limit)))

    def log_message(self, fmt, *args):
        log.info("%s", fmt % args)


def load_models() -> dict | None:
    """The model library (same file as the website's models.json). Read once, kept in memory."""
    global _models_cache
    if _models_cache is None:
        for p in MODELS_FILES:
            try:
                with open(p, encoding="utf-8") as f:
                    _models_cache = json.load(f)
                break
            except (OSError, ValueError):
                continue
    return _models_cache


def models_view(query: str) -> dict:
    data = load_models()
    if data is None:
        raise LookupError("model library is not bundled in this build")
    q = parse_qs(query)
    block = (q.get("block") or [""])[0].strip().upper()
    text = (q.get("q") or [""])[0].strip().lower()
    names = [b["block"] for b in data["blocks"]]
    if block and block not in names:
        raise am.ProtocolError("unknown block %r, use one of %s" % (block, " ".join(names)))
    if not block and not text:
        return data
    out = {k: v for k, v in data.items() if k not in ("blocks", "counts")}
    blocks = []
    for b in data["blocks"]:
        if block and b["block"] != block:
            continue
        ms = b["models"]
        if text:
            ms = [m for m in ms if text in " ".join(str(m.get(k) or "") for k in ("name", "based_on", "category")).lower()]
        blocks.append({**b, "count": len(ms), "models": ms})
    out["blocks"] = blocks
    out["counts"] = {b["block"]: b["count"] for b in blocks}
    return out


def history_view(query: str) -> dict:
    q = parse_qs(query)
    try:
        since = float(q.get("since", ["0"])[0])
    except ValueError:
        raise am.ProtocolError("since must be a number (seconds since 1970)")
    return history.listing(since, q.get("hex", ["1"])[0] != "0")


def _idx(text: str) -> int:
    try:
        i = int(text)
    except ValueError:
        raise am.ProtocolError("patch index must be a number")
    if not 0 <= i <= am.MAX_PATCH:
        raise am.ProtocolError(f"patch index must be 0-{am.MAX_PATCH}")
    return i


class Server(ThreadingHTTPServer):
    daemon_threads = True      # worker threads never keep the process alive
    request_queue_size = 16

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._slots = threading.BoundedSemaphore(MAX_THREADS)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


def _term(signum, frame):
    log.info("signal %d, exiting", signum)
    os._exit(0)  # nothing is held between requests, nothing to clean up


def main():
    if not API_KEY:
        raise SystemExit("API_KEY is not set")
    if len(API_KEY) < MIN_KEY_LEN or API_KEY in PLACEHOLDER_KEYS:
        raise SystemExit(f"API_KEY is too weak: use at least {MIN_KEY_LEN} random characters "
                         "(for example: openssl rand -hex 32), and not the placeholder from .env.example")
    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    log.info("ampero-bridge on :%d (hard deadline %.0fs)", PORT, HARD_DEADLINE)
    if HISTORY_POLL > 0:
        threading.Thread(target=poll_history, daemon=True, name="history").start()
        log.info("history on: reading the pedal every %.0fs, keeping %.0fs", HISTORY_POLL, HISTORY_WINDOW)
    Server(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
