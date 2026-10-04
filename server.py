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

Errors are JSON: {"error": "..."} with 400 bad request, 401 key, 503 pedal
missing or busy, 504 pedal silent, 502 other USB trouble.

Nothing here can leave the process stuck: see usbmidi.Link and docs/usb-lockups.md.
"""
import datetime
import hmac
import json
import logging
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import ampero_mini as am
import usbmidi as usb

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ampero-bridge")

API_KEY = os.environ.get("API_KEY", "")
PORT = int(os.environ.get("PORT", "8080"))
HARD_DEADLINE = float(os.environ.get("AMPERO_HARD_DEADLINE_S", "20"))
MAX_BODY = 4096
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
    # FX1 and AMP: every code read from the record while stepping the pedal's own list (docs/models.md).
    # Inferred rows are not included.
    "fx1": {0,1, *range(3, 6), *range(32, 35), *range(36, 41), *range(42, 46), *range(64, 68), *range(69, 80), *range(128, 151)},
    "fx2": {0, 4, 7, 9},
    "amp": {*range(0, 10), *range(48, 59), *range(60, 65), 66, *range(96, 102), *range(103, 114), *range(160, 165), *range(192, 200)},
    "cab": {34},
    "dly": {9},
    "rvb": {4},
}
CLIENT_TIMEOUT = 10  # seconds a client may stall before we drop the socket
GAP = 0.15           # pause between frames, the pacing the pedal was tested with

DATA_DIR = os.environ.get("AMPERO_DATA_DIR", "/data")
HISTORY_POLL = float(os.environ.get("AMPERO_HISTORY_POLL_S", "2"))      # pause between polls; 0 turns history off
HISTORY_WINDOW = float(os.environ.get("AMPERO_HISTORY_WINDOW_S", "600"))  # how far back to keep states
HISTORY_BUSY_MAX = float(os.environ.get("AMPERO_HISTORY_BUSY_MAX_S", "10"))  # longest wait while the patch keeps changing
HISTORY_MAX = 400     # states kept at most, whatever the window
KNOWN_REFRESH = 3600  # seconds between disk writes for a patch whose name did not change

link = usb.Link(hard_deadline=HARD_DEADLINE)


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
    link.session(name, lambda p: p.send_midi(msg))


def send_sysex(frames: list[bytes], name: str):
    def run(p):
        if len(frames) == 1:
            p.send_sysex(frames[0])
        else:
            p.send_sysex_batch(frames)
    link.session(name, run)


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
    am.ProtocolError: 400, LookupError: 404, PatchNotCurrent: 409,
}
# Bad input that slipped past the checks above. Reported as 400 with a fixed message.
BAD_INPUT = (TypeError, ValueError, OverflowError, UnicodeError)


def status_for(exc: Exception) -> int:
    for cls, code in STATUS.items():
        if isinstance(exc, cls):
            return code
    return 500


class Handler(BaseHTTPRequestHandler):
    server_version = "ampero-bridge/2.7.0"
    timeout = CLIENT_TIMEOUT   # socket timeout: a stalled client cannot pin a thread

    def version_string(self):
        return "ampero-bridge"   # no version or Python build in the Server header

    def _send(self, code: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        key = self.headers.get("X-Api-Key", "")
        return bool(API_KEY) and hmac.compare_digest(key.encode(), API_KEY.encode())

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise am.ProtocolError("bad Content-Length")
        if n < 0:
            raise am.ProtocolError("bad Content-Length")
        if n > MAX_BODY:
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
            self._send(code, {"error": str(e), "kind": type(e).__name__, **getattr(e, "extra", {})})

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
        self._run(lambda: handle_post(path, self._body()))

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
