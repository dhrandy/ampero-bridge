#!/usr/bin/env python3
"""ampero-bridge: HTTP front for the Hotone Ampero Mini, key-gated.

The pedal plugs into the server over USB. This service talks to it with libusb
(no ALSA) and exposes a small JSON API so any AI can build presets from a script.

Auth: X-Api-Key header, except GET /health.

  GET  /health                     liveness, pedal presence, request counters, USB device counts
  GET  /api/usb                    interfaces and endpoints the pedal reports, plus every USB device this process sees
  GET  /api/patch/current          read the patch the pedal has selected (name + raw record)
  GET  /api/patch/<index>          same, but 409 unless <index> is the selected patch
  POST /api/patch/select           {"index": 75}            Program Change
  POST /api/block                  {"block": "rvb", "on": true}
  POST /api/model                  {"slot": "eq", "code": 4}
  POST /api/param                  {"slot": "eq", "model_code": 4, "param": 3, "value": 30}
  POST /api/patch/save             {"index": 75, "name": "WADE", "confirm": "SAVE P26-1"}

Errors are JSON: {"error": "..."} with 400 bad request, 401 key, 503 pedal
missing or busy, 504 pedal silent, 502 other USB trouble.

Nothing here can leave the process stuck: see usbmidi.Link and docs/usb-lockups.md.
"""
import hmac
import json
import logging
import os
import signal
import threading
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
CLIENT_TIMEOUT = 10  # seconds a client may stall before we drop the socket
GAP = 0.15           # pause between frames, the pacing the pedal was tested with

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
    try:
        return int(data[key])
    except (TypeError, ValueError):
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
    if path == "/api/model":
        send_sysex([am.model_select(data.get("slot"), _int(data, "code"))], "model")
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
    am.ProtocolError: 400, LookupError: 404, PatchNotCurrent: 409,
}


def status_for(exc: Exception) -> int:
    for cls, code in STATUS.items():
        if isinstance(exc, cls):
            return code
    return 500


class Handler(BaseHTTPRequestHandler):
    server_version = "ampero-bridge/2.0"
    timeout = CLIENT_TIMEOUT   # socket timeout: a stalled client cannot pin a thread

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
        n = int(self.headers.get("Content-Length") or 0)
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
            if code >= 500:
                log.warning("%s %s -> %d %s: %s", self.command, self.path, code, type(e).__name__, e)
            self._send(code, {"error": str(e), "kind": type(e).__name__, **getattr(e, "extra", {})})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._send(200, {"ok": True, "pedal_connected": usb.is_present(), "usb": link.status(),
                              "usb_seen": usb.seen()})
            return
        if not self._authed():
            self._send(401, {"error": "unauthorized"})
            return
        if path == "/api/usb":
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


def _term(signum, frame):
    log.info("signal %d, exiting", signum)
    os._exit(0)  # nothing is held between requests, nothing to clean up


def main():
    if not API_KEY:
        raise SystemExit("API_KEY is not set")
    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    log.info("ampero-bridge on :%d (hard deadline %.0fs)", PORT, HARD_DEADLINE)
    Server(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
