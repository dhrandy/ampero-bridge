# ampero-bridge

HTTP bridge to a Hotone Ampero Mini, so any AI can build presets from a
script: select a patch, switch blocks, pick models, set parameters, read a stored
patch, save. The pedal plugs into the NAS over USB. The service talks to it with
libusb and a small JSON API.

## Status

| Piece | State |
| --- | --- |
| Patch select, block on/off (CC) | verified on the pedal's screen |
| Model select, parameter set (SysEx) | verified for the EQ slot; other slots follow the same frame |
| Read patch (name, raw record) | works; only the name and index are decoded |
| Save | **verified on the pedal.** The editor's two frames, sent together in one USB transfer, saved the name TEST into P26-1 (seen on the screen after hopping patches). The pedal sends no reply, so only its screen confirms it |
| Lock (CC 77), all-off (CC 78) | not isolated on the Mini |

Details and the captured bytes: `docs/protocol.md`.

## Why it will not lock up the NAS again

The first version held an ALSA MIDI port. When the Mini stalled, the Dell's
kernel waited forever on it and only a reboot helped. This version has no ALSA
anywhere: libusb only, a timeout on every transfer, one request at a time,
the pedal found fresh by vendor/product on every request (replugging just works),
a watchdog that exits the process if a request outlives its deadline, a Docker
healthcheck and `restart: unless-stopped`. What was researched, and what can
not be fixed in app code, is in `docs/usb-lockups.md`.

## Deploy (CasaOS / Dockhand, compose only)

1. In Dockhand, create a stack from `docker-compose.yml` (builds from this repo,
   `#main`).
2. Set `API_KEY` in Dockhand's Environment tab.
3. The container gets `/dev/bus/usb` and the cgroup rule for USB char devices
   (major 189). No `/dev/snd`.

The pedal only has to be plugged in when changes are wanted. `GET /health` says
whether it is there.

## API

Send `X-Api-Key`. Only `/health` is open.

| Call | Body | What it does |
| --- | --- | --- |
| `GET /health` | | liveness, `pedal_connected`, request counters |
| `GET /api/usb` | | interfaces and endpoints the pedal reports |
| `GET /api/patch/<index>` | | read a stored patch: `name`, `label`, `record_hex` |
| `POST /api/patch/select` | `{"index": 75}` | Program Change (0 based, 75 = P26-1) |
| `POST /api/block` | `{"block": "rvb", "on": true}` | block on/off (fx1 fx2 amp nr cab eq fx3 dly rvb) |
| `POST /api/model` | `{"slot": "eq", "code": 4}` | pick a model for a slot |
| `POST /api/param` | `{"slot": "eq", "model_code": 4, "param": 3, "value": 30}` | set one parameter (0-127) |
| `POST /api/patch/save` | `{"index": 75, "name": "WADE", "confirm": "SAVE P26-1"}` | save to a slot; needs the exact confirm text |

Errors come back as `{"error", "kind"}`: 400 bad input, 401 key, 503 pedal not
connected or busy, 504 pedal silent, 502 other USB error.

The pedal never echoes a write. Only its screen shows that a write applied. Before
overwriting a patch, `GET /api/patch/<index>` first and keep the record as the
restore point.

## Env

| Var | Default | |
| --- | --- | --- |
| `API_KEY` | required | |
| `PORT` | 8080 | |
| `AMPERO_USB_TIMEOUT_MS` | 1000 | per transfer |
| `AMPERO_HARD_DEADLINE_S` | 20 | a request longer than this makes the bridge exit and restart |
| `AMPERO_USB_REATTACH` | unset | `1` gives the interface back to snd-usb-audio after each request |
| `AMPERO_USB_INTERFACE`, `AMPERO_USB_MODE` | auto | only after checking `/api/usb` |

## Develop

    pip install pyusb pytest
    python -m pytest

Tests use a fake pedal. Frames are checked byte for byte against the ones
captured from the editor and the pedal.

## Safety

* Hardware writes go through one function that sends exactly the captured frames.
* A save needs `confirm`. Block on/off uses CC, never SysEx: a SysEx write of the
  enable marker crashed the pedal once.
* Credits: the Ampero II Stage work by jpfaria (github.com/jpfaria/hotone-ampero-2)
  started this, but the Mini uses a different header, so none of its frames are
  used here.
