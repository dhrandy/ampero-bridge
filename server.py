#!/usr/bin/env python3
"""ampero-bridge: expose the Hotone Ampero Mini over HTTP, key-gated.

The pedal plugs into the NAS over USB when Randy wants changes. This bridge
speaks the pedal's SysEx protocol over raw USB and serves a tiny HTTP API so
an assistant can read patches and push effect settings without the editor.

Endpoints (all key-gated except /health):
  GET  /health              -> {"ok": true, "pedal_connected": bool, "port": str|null}
  GET  /api/patches         -> {"patches": [{"index": int, "label": "A1-1", "name": str}]}
  GET  /api/patch/<index>   -> {"index": int, "label": str, "name": str, "raw": "<hex of dump>"}
  POST /api/patch/load      -> {"index": int} load patch into edit buffer
  POST /api/patch/param     -> {"index": int, "slot": int, "param": int, "value": float}
  POST /api/patch/block     -> {"scene": int, "powers": [0/1 x9]} block on/off bitmap
  POST /api/patch/model     -> {"slot": int, "category": int, "code": int} set effect model
  POST /api/patch/clear     -> {"slot": int} clear a slot
  POST /api/patch/volume    -> {"volume": 0-100}
  POST /api/patch/save      -> {"index": int, "name": str} save edit buffer
  GET  /api/firmware        -> {"firmware": str}

Auth: send API_KEY as the X-Api-Key header.

USB: talks to the pedal through libusb (no ALSA, no sequencer). The container
needs /dev/bus/usb. The pedal only needs to be plugged in when changes are
wanted; /health reports whether it is currently visible. The SysEx protocol is
unverified on the Mini (see README).
"""
import json
import logging
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import ampero_mini as am
import usbmidi

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ampero-bridge")

API_KEY = os.environ["API_KEY"]
PORT = int(os.environ.get("PORT", "8080"))
_lock = threading.Lock()


def _present() -> bool:
    return usbmidi.is_present()


def _request(frame: bytes, timeout: float = 2.0):
    """One short USB session: open, send a frame, return the reply frame.

    The device is opened and released for every request, and every transfer has
    a hard timeout, so nothing can hold the pedal across a replug or hang.
    """
    with _lock, usbmidi.Pedal() as p:
        p.drain()
        p.send_sysex(frame)
        raw = p.recv_sysex(timeout)
        if raw is None:
            raise TimeoutError("no reply from pedal (it may need a power cycle)")
        return am.parse_frame(raw)


def _request_dump(frame: bytes, timeout: float = 3.0) -> bytes:
    """Send a query whose answer is a chunked dump; return reassembled payload."""
    with _lock, usbmidi.Pedal() as p:
        p.drain()
        p.send_sysex(frame)
        raw = p.recv_sysex(timeout)
        first = am.parse_frame(raw) if raw else None
        if first is None or first.cmd != am.CMD_DATA:
            raise TimeoutError("no dump from pedal")
        chunks = [first]
        while sum(len(c.payload) for c in chunks) < first.length:
            raw = p.recv_sysex(timeout)
            if raw is None:
                raise TimeoutError("dump stalled")
            chunks.append(am.parse_frame(raw))
        chunks.sort(key=lambda c: c.offset)
        return b"".join(c.payload for c in chunks)


class Handler(BaseHTTPRequestHandler):
    server_version = "ampero-bridge/1.0"

    def _send_json(self, code: int, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self) -> bool:
        return self.headers.get("X-Api-Key") == API_KEY

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(200, {"ok": True, "pedal_connected": _present(),
                                 "transport": "libusb"})
            return
        if not self._auth():
            self._send_json(401, {"error": "unauthorized"})
            return
        try:
            if path == "/api/patches":
                payload = _request_dump(am.msg_query_patch_names())
                patches = []
                # 300 x u16 order table then names; Mini: PATCHES entries
                for i in range(am.PATCHES):
                    name = payload[600 + i * 17:600 + i * 17 + 17].split(b"\0")[0].decode("ascii", "replace")
                    patches.append({"index": i, "label": am.patch_label(i), "name": name})
                self._send_json(200, {"patches": patches})
            elif path.startswith("/api/patch/") and path.count("/") == 3:
                index = int(path.rsplit("/", 1)[1])
                payload = _request_dump(am.msg_get_patch(index))
                name = payload[34:51].split(b"\0")[0].decode("ascii", "replace")
                self._send_json(200, {"index": index, "label": am.patch_label(index),
                                     "name": name, "dump_hex": payload.hex()})
            elif path == "/api/firmware":
                frame = _request(am.msg_query_firmware())
                fw = am.reply_body(frame).split(b"\0")[0].decode("ascii", "replace")
                self._send_json(200, {"firmware": fw})
            elif path in ("/api/usb", "/api/ports"):
                # Interfaces and endpoints as the pedal reports them. Read-only,
                # opens nothing: use this to see which interface carries SysEx.
                self._send_json(200, usbmidi.describe())
            elif path == "/api/identity":
                # Standard MIDI Identity Request. A compliant MIDI device answers.
                # If this works but Hotone commands don't, the Mini uses a
                # different SysEx dialect than the II Stage.
                with _lock, usbmidi.Pedal() as p:
                    p.drain()
                    p.send_sysex(bytes([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7]))
                    raw = p.recv_sysex(2.0)
                self._send_json(200, {"identity_hex": raw.hex() if raw else None})
            else:
                self._send_json(404, {"error": "not found"})
        except Exception as e:
            log.exception("GET %s failed", path)
            self._send_json(500, {"error": str(e)})

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._auth():
            self._send_json(401, {"error": "unauthorized"})
            return
        try:
            data = self._read_body()
            if path == "/api/patch/load":
                _request(am.msg_load_patch(int(data["index"])))
                self._send_json(200, {"ok": True})
            elif path == "/api/patch/param":
                _request(am.msg_set_param(int(data["slot"]), int(data["param"]), float(data["value"])))
                self._send_json(200, {"ok": True})
            elif path == "/api/patch/block":
                powers = [int(x) for x in data["powers"]]
                _request(am.msg_scene_powers(int(data.get("scene", 0)), powers))
                self._send_json(200, {"ok": True})
            elif path == "/api/patch/model":
                # Guard: never send a model change without explicit category+code.
                _request(am.msg_set_model(int(data["slot"]), int(data["category"]), int(data["code"])))
                self._send_json(200, {"ok": True})
            elif path == "/api/patch/clear":
                _request(am.msg_clear_slot(int(data["slot"])))
                self._send_json(200, {"ok": True})
            elif path == "/api/patch/volume":
                _request(am.msg_set_patch_volume(int(data["volume"])))
                self._send_json(200, {"ok": True})
            elif path == "/api/patch/save":
                _request(am.msg_save_patch(int(data["index"]), str(data["name"])))
                self._send_json(200, {"ok": True})
            elif path == "/api/shutdown":
                # Nothing holds the pedal between requests, so a plain stop is safe.
                self._send_json(200, {"ok": True, "shutting_down": True})
                threading.Thread(target=Handler._server.shutdown, daemon=True).start()
            else:
                self._send_json(404, {"error": "not found"})
        except Exception as e:
            log.exception("POST %s failed", path)
            self._send_json(500, {"error": str(e)})

    def log_message(self, *args):
        log.info("%s", args[0] % args[1:])


def _handle_term(signum, frame):
    # Docker stop: exit immediately. No kernel MIDI client is held between
    # requests, so there is nothing to clean up.
    log.info("received signal %d, exiting", signum)
    os._exit(0)


signal.signal(signal.SIGTERM, _handle_term)
signal.signal(signal.SIGINT, _handle_term)


def main():
    log.info("ampero-bridge starting on :%d", PORT)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    Handler._server = server
    server.serve_forever()


if __name__ == "__main__":
    main()
