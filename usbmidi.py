"""Raw USB-MIDI transport for the Hotone Ampero Mini (libusb, no ALSA).

Why this exists: the ALSA sequencer/rawmidi path wedged the Dell's kernel. A
process holding a sequencer port while the Mini stalled or was unplugged left
the USB hub worker waiting forever on the port's use count (D-state, only a
reboot clears it). This module talks to the pedal through libusb, so no kernel
MIDI client ever exists.

What keeps it from locking up again (see docs/usb-lockups.md):

* every transfer has a timeout, and a whole request has a deadline;
* the device is opened per request and released right after, so a replug or a
  power cycle is picked up by the next request with nothing to reconnect;
* requests are serialized, and a second caller waits a bounded time, then gets
  PedalBusy (HTTP 503) instead of piling up;
* a watchdog thread exits the process if a request outlives its hard deadline,
  so Docker's restart policy brings the bridge back clean.

Interface 3 (vendor 84ef, product 0080) is a standard USB-MIDI 1.0
MIDIStreaming interface: bulk OUT 0x03, bulk IN 0x83, one cable. Verified on
the real pedal Oct 3, 2026.
"""
from __future__ import annotations

import errno
import logging
import os
import threading
import time

log = logging.getLogger("ampero-usb")

VID = int(os.environ.get("AMPERO_USB_VID", "0x84ef"), 0)
PID = int(os.environ.get("AMPERO_USB_PID", "0x0080"), 0)
IFACE_ENV = os.environ.get("AMPERO_USB_INTERFACE")  # explicit interface number
MODE_ENV = os.environ.get("AMPERO_USB_MODE")        # "midi" (4-byte packets) or "raw"
XFER_TIMEOUT_MS = int(os.environ.get("AMPERO_USB_TIMEOUT_MS", "1000"))
# By default the kernel's snd-usb-audio is left detached after a request. Handing
# the interface back on every request would rebind the ALSA MIDI device each
# time, which is churn we do not need. Set AMPERO_USB_REATTACH=1 to restore it.
REATTACH = os.environ.get("AMPERO_USB_REATTACH") == "1"

_CIN_LEN = {0x4: 3, 0x5: 1, 0x6: 2, 0x7: 3}  # sysex-only code index numbers


class UsbMidiError(RuntimeError):
    """Anything that went wrong talking to the pedal."""


class PedalNotConnected(UsbMidiError):
    """The pedal is not on the bus. Plug it in; the next request will find it."""


class PedalGone(UsbMidiError):
    """The pedal vanished mid-request (unplugged, power cycled, USB reset)."""


class PedalBusy(UsbMidiError):
    """Another request still holds the pedal and did not finish in time."""


class PedalTimeout(UsbMidiError):
    """The pedal accepted the request but did not answer in time."""


# errno values libusb reports when the device went away under us.
_GONE_ERRNOS = {errno.ENODEV, errno.EIO, errno.EPIPE, errno.ESHUTDOWN, errno.EPROTO,
                errno.ENOENT, errno.EBUSY}


def _wrap_usb_error(e: Exception, what: str) -> UsbMidiError:
    code = getattr(e, "errno", None)
    if code in _GONE_ERRNOS or "no such device" in str(e).lower() or "no device" in str(e).lower():
        return PedalGone(f"{what}: pedal went away ({e})")
    return UsbMidiError(f"{what}: {e}")


# --- USB-MIDI 1.0 event packets (pure functions, unit tested) -----------------

def encode_sysex(frame: bytes, cable: int = 0) -> bytes:
    """Wrap one complete SysEx message (F0 ... F7) into 4-byte USB-MIDI packets."""
    if not frame or frame[0] != 0xF0 or frame[-1] != 0xF7:
        raise ValueError("not a complete SysEx message")
    out = bytearray()
    i = 0
    n = len(frame)
    while i < n:
        chunk = frame[i:i + 3]
        i += len(chunk)
        if i < n:
            cin = 0x4
        else:
            cin = {1: 0x5, 2: 0x6, 3: 0x7}[len(chunk)]
        out += bytes(((cable << 4) | cin,)) + chunk.ljust(3, b"\0")
    return bytes(out)


def encode_short(msg: bytes, cable: int = 0) -> bytes:
    """Wrap one channel message (Program Change, Control Change) as a USB-MIDI packet."""
    if not msg or not 0x80 <= msg[0] <= 0xEF:
        raise ValueError("not a channel message")
    cin = msg[0] >> 4
    need = 2 if cin in (0xC, 0xD) else 3
    if len(msg) != need:
        raise ValueError(f"{msg[0]:#x} needs {need} bytes, got {len(msg)}")
    return bytes([(cable << 4) | cin]) + msg + b"\0" * (3 - len(msg))


class SysexAssembler:
    """Feed raw USB-MIDI bytes, get complete SysEx messages back."""

    def __init__(self):
        self._buf = bytearray()
        self._active = False

    def feed(self, data: bytes) -> list[bytes]:
        done = []
        for p in range(0, len(data) - len(data) % 4, 4):
            cin = data[p] & 0x0F
            if cin not in _CIN_LEN:
                continue  # not sysex (notes, clock, empty padding)
            payload = data[p + 1:p + 1 + _CIN_LEN[cin]]
            if payload[:1] == b"\xf0":
                self._buf = bytearray()
                self._active = True
            if not self._active:
                continue
            self._buf += payload
            if cin != 0x4:
                done.append(bytes(self._buf))
                self._buf = bytearray()
                self._active = False
        return done


# --- device access ------------------------------------------------------------

def _usb():
    import usb.core
    import usb.util
    return usb.core, usb.util


def find_device():
    core, _ = _usb()
    return core.find(idVendor=VID, idProduct=PID)


def is_present() -> bool:
    """Enumerate only. Never opens or claims the device."""
    try:
        return find_device() is not None
    except Exception:
        return False


def visible_devices() -> list[dict]:
    """Every USB device libusb can see from inside this process. Enumerate only."""
    try:
        core, _ = _usb()
        return [{"id": f"{d.idVendor:04x}:{d.idProduct:04x}", "bus": d.bus, "address": d.address}
                for d in core.find(find_all=True)]
    except Exception:
        return []


def dev_node_count(root: str = "/dev/bus/usb") -> int | None:
    """How many device nodes this process has under /dev/bus/usb, or None if the
    directory is not there. Compare with `lsusb` on the host: fewer here means the
    container's view is stale and it needs a restart."""
    if not os.path.isdir(root):
        return None
    return sum(len(files) for _, _, files in os.walk(root))


def seen() -> dict:
    """Small summary for /health. Counts only, so the open endpoint leaks no device list."""
    return {"libusb_devices": len(visible_devices()), "dev_nodes": dev_node_count()}


def describe() -> dict:
    """Interfaces and endpoints, for diagnosing which one carries SysEx.
    Also lists every device libusb sees, so a blind container is easy to spot."""
    visible = visible_devices()
    dev = find_device()
    if dev is None:
        return {"present": False, "visible_devices": visible, "dev_nodes": dev_node_count()}
    info = {"present": True, "visible_devices": visible, "dev_nodes": dev_node_count(),
            "mini_node": os.path.exists(f"/dev/bus/usb/{dev.bus:03d}/{dev.address:03d}"), "vid": hex(VID), "pid": hex(PID), "interfaces": []}
    for cfg in dev:
        for intf in cfg:
            info["interfaces"].append({
                "number": intf.bInterfaceNumber, "alt": intf.bAlternateSetting,
                "class": intf.bInterfaceClass, "subclass": intf.bInterfaceSubClass,
                "protocol": intf.bInterfaceProtocol,
                "endpoints": [{"addr": hex(e.bEndpointAddress), "attrs": hex(e.bmAttributes),
                               "max_packet": e.wMaxPacketSize} for e in intf],
            })
    return info


def _pick_interface(dev):
    """Return (interface, ep_out, ep_in, mode)."""
    _, util = _usb()
    cfg = dev.get_active_configuration()
    cands = []
    for intf in cfg:
        if IFACE_ENV is not None and intf.bInterfaceNumber != int(IFACE_ENV):
            continue
        if IFACE_ENV is None and not (intf.bInterfaceClass == 1 and intf.bInterfaceSubClass == 3):
            continue
        ep_out = util.find_descriptor(intf, custom_match=lambda e: util.endpoint_direction(
            e.bEndpointAddress) == util.ENDPOINT_OUT and util.endpoint_type(e.bmAttributes) == util.ENDPOINT_TYPE_BULK)
        ep_in = util.find_descriptor(intf, custom_match=lambda e: util.endpoint_direction(
            e.bEndpointAddress) == util.ENDPOINT_IN and util.endpoint_type(e.bmAttributes) == util.ENDPOINT_TYPE_BULK)
        if ep_out is not None and ep_in is not None:
            mode = MODE_ENV or ("midi" if intf.bInterfaceClass == 1 else "raw")
            cands.append((intf, ep_out, ep_in, mode))
    if not cands:
        raise UsbMidiError(
            "no usable MIDIStreaming interface found; see GET /api/usb and set "
            "AMPERO_USB_INTERFACE (and AMPERO_USB_MODE) deliberately")
    return cands[0]


class Pedal:
    """One short session: open, claim one interface, transfer, release."""

    def __init__(self):
        self._dev = None
        self._intf = None
        self._claimed = None
        self._asm = SysexAssembler()
        self._detached = False

    def __enter__(self):
        core, util = _usb()
        try:
            self._dev = find_device()
        except Exception as e:
            raise _wrap_usb_error(e, "usb enumerate")
        if self._dev is None:
            raise PedalNotConnected("pedal not connected")
        try:
            self._intf, self._out, self._in, self._mode = _pick_interface(self._dev)
            n = self._intf.bInterfaceNumber
            if self._dev.is_kernel_driver_active(n):
                self._dev.detach_kernel_driver(n)
                self._detached = True
        except UsbMidiError:
            raise
        except (NotImplementedError, core.USBError) as e:
            raise _wrap_usb_error(e, "cannot take the interface from the kernel")
        self._claimed = n
        try:
            util.claim_interface(self._dev, n)
        except core.USBError as e:
            self._give_back()
            raise _wrap_usb_error(e, f"cannot claim interface {n}")
        return self

    def _give_back(self):
        _, util = _usb()
        if self._claimed is not None:
            try:
                util.release_interface(self._dev, self._claimed)
            except Exception:
                pass
        if self._detached and REATTACH:
            try:
                self._dev.attach_kernel_driver(self._claimed)
            except Exception:
                pass
        try:
            util.dispose_resources(self._dev)
        except Exception:
            pass

    def __exit__(self, *exc):
        self._give_back()
        return False

    def _write(self, data: bytes):
        core, _ = _usb()
        try:
            self._out.write(data, timeout=XFER_TIMEOUT_MS)
        except core.USBError as e:
            raise _wrap_usb_error(e, "usb write")

    def send_sysex(self, frame: bytes):
        self._write(encode_sysex(frame) if self._mode == "midi" else frame)

    def send_sysex_batch(self, frames: list[bytes]):
        """Several frames in one USB transfer, like the editor's save pair."""
        if self._mode != "midi":
            raise UsbMidiError("batching needs USB-MIDI packet mode")
        self._write(b"".join(encode_sysex(f) for f in frames))

    def send_midi(self, msg: bytes):
        """Program Change or Control Change."""
        if self._mode != "midi":
            raise UsbMidiError("channel messages need USB-MIDI packet mode")
        self._write(encode_short(msg))

    def recv_sysex(self, timeout: float = 2.0) -> bytes | None:
        core, _ = _usb()
        deadline = time.monotonic() + timeout
        size = max(self._in.wMaxPacketSize, 512)
        while time.monotonic() < deadline:
            wait_ms = max(1, min(XFER_TIMEOUT_MS, int((deadline - time.monotonic()) * 1000)))
            try:
                data = bytes(self._in.read(size, timeout=wait_ms))
            except core.USBTimeoutError:
                continue
            except core.USBError as e:
                raise _wrap_usb_error(e, "usb read")
            if self._mode == "midi":
                msgs = self._asm.feed(data)
                if msgs:
                    return msgs[0]
            elif data:
                return data
        return None

    def collect(self, timeout: float, until=None) -> list[bytes]:
        """Gather SysEx frames for up to `timeout` seconds, or until `until(frames)` is true."""
        deadline = time.monotonic() + timeout
        frames: list[bytes] = []
        while time.monotonic() < deadline:
            msg = self.recv_sysex(max(0.05, deadline - time.monotonic()))
            if msg is None:
                break
            frames.append(msg)
            if until is not None and until(frames):
                break
        return frames

    def drain(self):
        """Throw away what the pedal broadcast since the last request (bounded)."""
        end = time.monotonic() + 0.5
        while time.monotonic() < end and self.recv_sysex(0.05) is not None:
            pass


class Link:
    """Serializes pedal requests and keeps one stuck request from taking the bridge down.

    `session()` runs a function with an open Pedal. Only one runs at a time.
    A watchdog exits the process if one runs longer than `hard_deadline`
    seconds; with `restart: unless-stopped` Docker then starts a fresh bridge.
    """

    def __init__(self, hard_deadline: float = 20.0, wait: float = 3.0, exit_fn=os._exit):
        self._lock = threading.Lock()
        self._state = threading.Lock()
        self._hard = hard_deadline
        self._wait = wait
        self._exit = exit_fn
        self._op = None          # (name, started monotonic)
        self.last_ok = None      # wall clock of the last good request
        self.last_error = None
        self.requests = 0
        self.errors = 0
        threading.Thread(target=self._watch, daemon=True, name="usb-watchdog").start()

    def _watch(self):
        while True:
            time.sleep(1.0)
            with self._state:
                op = self._op
            if op and time.monotonic() - op[1] > self._hard:
                log.critical("usb request %r still running after %.0fs, exiting so Docker restarts us",
                             op[0], self._hard)
                self._exit(70)
                return

    def session(self, name: str, fn):
        if not self._lock.acquire(timeout=self._wait):
            raise PedalBusy("another pedal request is still running")
        try:
            with self._state:
                self._op = (name, time.monotonic())
                self.requests += 1
            try:
                with Pedal() as p:
                    result = fn(p)
                self.last_ok = time.time()
                return result
            except Exception as e:
                self.errors += 1
                self.last_error = f"{type(e).__name__}: {e}"
                raise
        finally:
            with self._state:
                self._op = None
            self._lock.release()

    def busy_for(self) -> float:
        with self._state:
            return 0.0 if not self._op else time.monotonic() - self._op[1]

    def status(self) -> dict:
        return {"busy_for_s": round(self.busy_for(), 1), "requests": self.requests,
                "errors": self.errors, "last_ok": self.last_ok, "last_error": self.last_error}
