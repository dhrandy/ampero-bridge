#!/usr/bin/env python3
"""ampero-bridge: HTTP front for the Hotone Ampero Mini, key-gated.

The pedal plugs into the server over USB. This service talks to it with libusb
(no ALSA) and exposes a small JSON API so any AI can build presets from a script.

Auth: X-Api-Key header, except GET /health (liveness only).

  GET  /health                     {"ok": true}, open, for the Docker healthcheck
  GET  /api/health                 pedal presence, request counters, USB device counts
  GET  /api/usb                    interfaces and endpoints the pedal reports, plus every USB device this process sees
  GET  /api/patch/current          read the patch the pedal has selected (name + raw record)
  GET  /api/patch/<index>          same, but 409 unless <index> is the selected patch
  POST /api/patch/select           {"index": 75}            Program Change
  POST /api/block                  {"block": "rvb", "on": true}
  POST /api/model                  {"slot": "eq", "code": 4}
  POST /api/param                  {"slot": "eq", "model_code": 4, "param": 3, "value": 30}
  POST /api/patch/save             {"index": 75, "name": "WADE", "confirm": "SAVE P26-1"}
  POST /api/backups                start a backup of every patch into one JSON file (reads only)
  GET  /api/backups                backup status and the files on disk
  GET  /api/backups/<file>         download one backup file

Errors are JSON: {"error": "..."} with 400 bad request, 401 key, 503 pedal
missing or busy, 504 pedal silent, 502 other USB trouble.

Nothing here can leave the process stuck: see usbmidi.Link and docs/usb-lockups.md.
"""
import datetime
import hmac
import json
import logging
import os
import re
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

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

# Model codes that were set on the real pedal and read back (docs/models.md).
# An unproven code can crash the pedal, so /api/model only takes these unless
# AMPERO_ALLOW_UNPROVEN_MODELS=1.
PROVEN_MODELS = {
    "fx1": {137},
    "fx2": {0, 4, 7, 9},
    "amp": {55},
    "cab": {34},
    "dly": {9},
    "rvb": {4},
}
CLIENT_TIMEOUT = 10  # seconds a client may stall before we drop the socket
GAP = 0.15           # pause between frames, the pacing the pedal was tested with

BACKUP_DIR = os.environ.get("AMPERO_BACKUP_DIR", "/backups")
BACKUP_SLOTS = int(os.environ.get("AMPERO_BACKUP_SLOTS", "100"))
SETTLE = 0.4         # seconds the pedal gets to switch patch before it is read
BACKUP_NAME = re.compile(r"^ampero-backup-\d{8}-\d{6}\.json$")

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
    return link.session("read current patch", run)


def read_patch(index: int) -> dict:
    """Read patch `index`, only if it is the one the pedal has selected."""
    got = read_current_patch()
    if got["index"] != index:
        raise PatchNotCurrent(index, got)
    return got


class Backup:
    """Reads every patch and writes one JSON file. Never writes to the pedal.

    It steps the pedal through the patches with Program Change (the same as
    turning the knob), reads each one, and puts the one that was selected before
    back at the end. Runs in a thread so the HTTP call returns at once.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.done = 0
        self.last: dict | None = None

    def start(self) -> dict:
        with self.lock:
            if self.running:
                raise Conflict("a backup is already running")
            try:
                os.makedirs(BACKUP_DIR, exist_ok=True)
            except OSError:
                raise BackupDirError(f"the backup folder {BACKUP_DIR} cannot be created; check the volume mount")
            if not os.access(BACKUP_DIR, os.W_OK):
                raise BackupDirError(f"the backup folder {BACKUP_DIR} is not writable; check the volume mount")
            self.running, self.done = True, 0
        threading.Thread(target=self._run, daemon=True).start()
        return {"ok": True, "started": True, "slots": BACKUP_SLOTS}

    def status(self) -> dict:
        return {"running": self.running, "done": self.done, "slots": BACKUP_SLOTS,
                "last": self.last, "files": list_backups()}

    def _read_slot(self, i: int) -> dict:
        err = None
        for attempt in range(2):
            try:
                send_midi(am.program_change(i), f"backup select {i}")
                time.sleep(SETTLE * (attempt + 1))
                got = read_current_patch()
                if got["index"] == i:
                    return got
                err = f"pedal answered with patch {got['index']}"
            except (usb.UsbMidiError, usb.PedalNotConnected) as e:
                err = str(e)
        raise RuntimeError(err)

    def _run(self):
        started = datetime.datetime.now(datetime.timezone.utc)
        patches, errors, start_patch = [], [], None
        try:
            start_patch = read_current_patch()
            for i in range(BACKUP_SLOTS):
                try:
                    p = self._read_slot(i)
                    patches.append({"index": p["index"], "label": p["label"], "name": p["name"],
                                    "record_hex": p["record_hex"]})
                except Exception as e:
                    log.warning("backup slot %d failed: %s", i, e)
                    errors.append({"index": i, "error": str(e)})
                self.done = i + 1
            if not patches:
                raise RuntimeError("no patch could be read")
            name = "ampero-backup-" + started.strftime("%Y%m%d-%H%M%S") + ".json"
            doc = {"created": started.isoformat(timespec="seconds"), "slots_tried": BACKUP_SLOTS,
                   "selected_before": {"index": start_patch["index"], "label": start_patch["label"],
                                       "name": start_patch["name"], "record_hex": start_patch["record_hex"]},
                   "index": [{"index": p["index"], "label": p["label"], "name": p["name"]} for p in patches],
                   "patches": patches, "errors": errors}
            tmp = os.path.join(BACKUP_DIR, "." + name + ".tmp")
            with open(tmp, "w") as f:
                json.dump(doc, f)
            os.replace(tmp, os.path.join(BACKUP_DIR, name))
            self.last = {"ok": True, "file": name, "patches": len(patches), "errors": len(errors),
                         "at": doc["created"]}
            log.info("backup written: %s (%d patches, %d errors)", name, len(patches), len(errors))
        except Exception as e:
            log.warning("backup failed: %s", e)
            self.last = {"ok": False, "error": str(e), "at": started.isoformat(timespec="seconds")}
        finally:
            if start_patch is not None:
                try:
                    send_midi(am.program_change(start_patch["index"]), "backup restore selection")
                except Exception as e:
                    log.warning("could not put the selected patch back: %s", e)
            self.running = False


class Conflict(Exception):
    pass


class BackupDirError(Exception):
    pass


def list_backups() -> list[str]:
    try:
        return sorted((n for n in os.listdir(BACKUP_DIR) if BACKUP_NAME.match(n)), reverse=True)
    except OSError:
        return []


backup = Backup()


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
    if path == "/api/backups":
        return backup.start()
    if backup.running:
        raise Conflict("a backup is running and is using the pedal; try again when it is done")
    if path == "/api/patch/select":
        idx = _int(data, "index")
        send_midi(am.program_change(idx), f"select {idx}")
        return {"ok": True, "label": am.patch_label(idx)}
    if path == "/api/block":
        block, on = str(data.get("block", "")), bool(data.get("on"))
        send_midi(am.block_power(block, on), f"block {block}")
        return {"ok": True}
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
        # The pedal sends nothing back for a save. Only its screen shows the result,
        # so the reply says written, not confirmed.
        return {"ok": True, "label": am.patch_label(idx), "verified": False,
                "note": "no reply exists for save; read the patch back to check"}
    raise LookupError(path)


STATUS = {
    usb.PedalNotConnected: 503, usb.PedalBusy: 503, usb.PedalGone: 503,
    usb.PedalTimeout: 504, usb.UsbMidiError: 502,
    am.ProtocolError: 400, LookupError: 404, PatchNotCurrent: 409, Conflict: 409, BackupDirError: 503,
}
# Bad input that slipped past the checks above. Reported as 400 with a fixed message.
BAD_INPUT = (TypeError, ValueError, OverflowError, UnicodeError)


def status_for(exc: Exception) -> int:
    for cls, code in STATUS.items():
        if isinstance(exc, cls):
            return code
    return 500


class Handler(BaseHTTPRequestHandler):
    server_version = "ampero-bridge/2.1.0"
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

    def _send_backup(self, name: str):
        if not BACKUP_NAME.match(name):
            self._send(404, {"error": "not found"})
            return
        try:
            with open(os.path.join(BACKUP_DIR, name), "rb") as f:
                body = f.read()
        except OSError:
            self._send(404, {"error": "not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
                              "usb_seen": usb.seen()})
        elif path == "/api/usb":
            self._run(usb.describe)
        elif path == "/api/patch/current":
            self._run(read_current_patch)
        elif path == "/api/backups":
            self._send(200, backup.status())
        elif path.startswith("/api/backups/"):
            self._send_backup(path.rsplit("/", 1)[1])
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
    Server(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
