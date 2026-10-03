"""Raw USB-MIDI transport for the Hotone Ampero Mini (libusb, no ALSA).

Why this exists: the ALSA sequencer/rawmidi path wedged the Dell's kernel. If a
process held a sequencer port while the Mini stalled or was unplugged, the USB
hub worker waited forever on the port's use count (seq_free_client, D-state,
only a reboot clears it). This module talks to the pedal through libusb
instead, so no kernel MIDI client ever exists, every transfer has a hard
timeout, and the device is opened per request and released right after.

UNVERIFIED: which USB interface carries the Mini's SysEx has not been
confirmed on real hardware (dmesg shows interface 3 with odd bulk endpoint
sizes; see README). Auto-detect only uses a standard MIDIStreaming interface
(class 1, subclass 3). Anything else needs AMPERO_USB_INTERFACE set on purpose.
"""
from __future__ import annotations

import os
import time

VID = int(os.environ.get("AMPERO_USB_VID", "0x84ef"), 0)
PID = int(os.environ.get("AMPERO_USB_PID", "0x0080"), 0)
IFACE_ENV = os.environ.get("AMPERO_USB_INTERFACE")  # explicit interface number
MODE_ENV = os.environ.get("AMPERO_USB_MODE")        # "midi" (4-byte packets) or "raw"
XFER_TIMEOUT_MS = int(os.environ.get("AMPERO_USB_TIMEOUT_MS", "1000"))

_CIN_LEN = {0x4: 3, 0x5: 1, 0x6: 2, 0x7: 3}  # sysex-only code index numbers


class UsbMidiError(RuntimeError):
    pass


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


def describe() -> dict:
    """Interfaces and endpoints, for diagnosing which one carries SysEx."""
    dev = find_device()
    if dev is None:
        return {"present": False}
    info = {"present": True, "vid": hex(VID), "pid": hex(PID), "interfaces": []}
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
        self._asm = SysexAssembler()
        self._detached = False

    def __enter__(self):
        core, util = _usb()
        self._dev = find_device()
        if self._dev is None:
            raise UsbMidiError("pedal not connected")
        self._intf, self._out, self._in, self._mode = _pick_interface(self._dev)
        n = self._intf.bInterfaceNumber
        try:
            if self._dev.is_kernel_driver_active(n):
                self._dev.detach_kernel_driver(n)
                self._detached = True
        except (NotImplementedError, core.USBError) as e:
            raise UsbMidiError(f"cannot take interface {n} from the kernel: {e}")
        try:
            util.claim_interface(self._dev, n)
        except core.USBError as e:
            raise UsbMidiError(f"cannot claim interface {n}: {e}")
        self._claimed = n
        return self

    def __exit__(self, *exc):
        core, util = _usb()
        try:
            util.release_interface(self._dev, self._claimed)
        except Exception:
            pass
        if self._detached:
            try:
                self._dev.attach_kernel_driver(self._claimed)
            except Exception:
                pass
        try:
            util.dispose_resources(self._dev)
        except Exception:
            pass
        return False

    def send_sysex(self, frame: bytes):
        core, _ = _usb()
        data = encode_sysex(frame) if self._mode == "midi" else frame
        try:
            self._out.write(data, timeout=XFER_TIMEOUT_MS)
        except core.USBError as e:
            raise UsbMidiError(f"usb write failed: {e}")

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
                raise UsbMidiError(f"usb read failed: {e}")
            if self._mode == "midi":
                msgs = self._asm.feed(data)
                if msgs:
                    return msgs[0]
            elif data:
                return data
        return None

    def drain(self):
        while self.recv_sysex(0.05) is not None:
            pass
