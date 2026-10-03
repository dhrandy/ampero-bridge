# ampero-bridge

HTTP bridge for the Hotone Ampero Mini. The pedal plugs into the NAS over USB
when Randy wants changes; this service speaks its SysEx protocol over USB MIDI
and exposes a small key-gated HTTP API so Todd can read patches and push effect
settings without the Hotone editor.

## Transport and protocol

The bridge talks to the pedal over raw USB with libusb (pyusb). It does not use
ALSA, the sequencer or rtmidi. Every request opens the device, claims one
interface, transfers with a hard timeout, and releases it. Nothing holds the
pedal between requests, so replugging it or stopping the container is safe.

Why: on the Dell (Debian, kernel 6.1) the ALSA path wedged the whole machine.
A sequencer port held by the bridge never finished a write to the Mini, the
kernel sat in `snd_use_lock_sync_helper` forever (uninterruptible), and the USB
hub worker and `docker stop` blocked behind it until a reboot.

**Unverified:** which USB interface carries the Mini's SysEx. The Mini enumerates
as vendor 84ef, product 0080, and the kernel logs `interface 3 ... bulk endpoint
0x83 has invalid maxpacket 64` and `endpoint 0x3 ... maxpacket 256`. Look at
`GET /api/usb` (read-only, opens nothing) to see the interfaces. Auto-detect only
uses a standard MIDIStreaming interface (class 1, subclass 3). If the pedal uses
a vendor interface, set `AMPERO_USB_INTERFACE` and `AMPERO_USB_MODE` on purpose.

The SysEx frame format in `ampero_mini.py` is adapted from the Ampero II Stage
work at github.com/jpfaria/hotone-ampero-2 (MIT). It has not been confirmed on
a Mini. The Mini may use something else; if so, capture the official editor
with USBPcap.

## What the Mini actually sends (captured Oct 3, 2026)

Interface 3 is a standard USB-MIDI 1.0 MIDIStreaming interface (bulk OUT 0x03
maxpacket 256, bulk IN 0x83 maxpacket 64, one cable). The pedal does not answer
a Universal Identity Request, but it sends SysEx on its own while it is used.
Every frame seen (298) has the same prefix and a plain, not nibble-split, body:

    F0 21 25 7F 4D 50 2D 32 12 <body> F7

This is not the header in `ampero_mini.py` (`F0 21 25 4D 50 00 00 <ck> <cmd> ...`),
so the II Stage frames written there will be ignored by the Mini. Observed body
shapes (meaning partly guessed):

- `00 02 06 05 00 00 00 78` heartbeat/status, repeated
- `00 02 06 04 01 NN` rolling event counter
- `10 AA 00 02 00 BB 00 00 VV` parameter change, VV is a 0-100 value
  (a slider dragged on screen produced a smooth 0x26 -> 0x64 -> 0x15 run)
- a burst with `06` then `07` on patch change (probably the patch number)

No host-to-pedal command has been captured yet. Until one is, treat every frame
builder in `ampero_mini.py` as wrong.

## Deploy (CasaOS / Dockhand, compose only)

1. In Dockhand, create a stack from `docker-compose.yml` (builds from the git
   URL, `#main`).
2. Set `API_KEY` in Dockhand's Environment tab (same key Todd uses).
3. The container needs `/dev/bus/usb` (mounted in the compose file) and the
   cgroup rule for USB devices (`c 189:*`). No `/dev/snd`.

The pedal only needs to be plugged in when changes are wanted. `/health`
reports `pedal_connected` (enumeration only, nothing is opened).

## API

All endpoints except `/health` require the `X-Api-Key` header.

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | /health | - | bridge + pedal status |
| GET | /api/patches | - | all patch names |
| GET | /api/patch/`<index>` | - | full patch dump (this is the backup) |
| POST | /api/patch/load | `{"index"}` | load into edit buffer |
| POST | /api/patch/param | `{"slot","param","value"}` | set knob (slot 0-8, value float) |
| POST | /api/patch/block | `{"scene","powers":[0/1 x9]}` | block on/off bitmap |
| POST | /api/patch/model | `{"slot","category","code"}` | set effect model (use catalog codes only) |
| POST | /api/patch/clear | `{"slot"}` | clear a slot |
| POST | /api/patch/volume | `{"volume"}` | 0-100 |
| POST | /api/patch/save | `{"index","name"}` | save edit buffer to slot |
| GET | /api/firmware | - | firmware string |

## Workflow

Todd's rule: before changing any patch, `GET /api/patch/<index>` first and
save the dump. The Mini only has 99 user slots, so changes go back to the
same slot and the saved dump is the restore point.

## Known issue history (Oct 3, 2026)

The old ALSA/rtmidi transport hung the host kernel when the bridge talked to the
Mini (see "Transport and protocol"). It was replaced with the libusb transport
above. Whether the pedal answers SysEx at all is still unconfirmed on hardware.

## Safety

- Never send `model` with a guessed category/code: a wrong category byte can
  hang the pedal's SysEx until power-cycle.
- Writes go to the edit buffer; nothing is permanent until `save`.
- If the pedal stops responding to SysEx, power-cycle it (USB replug is not enough).
