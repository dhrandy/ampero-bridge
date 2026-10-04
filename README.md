# ampero-bridge

A small web service that lets an AI agent (or any script) build presets on a
Hotone Ampero Mini. The pedal plugs into a computer over USB. This service runs
on that computer and turns plain HTTP calls into what the Hotone editor would
send: pick a patch, switch blocks on and off, choose models, set parameters,
read a patch back, and save it.

Hotone's own editor is point and click. This gives an AI the same hands.

## What it is for

You tell an agent "make me a clean Fender-ish patch with a bit of spring reverb",
and it does the work on the real pedal: it reads what is there, changes the
blocks, picks models, sets the knobs, checks its work by reading the patch back,
and saves. It can also back up a patch before touching it.

It only works with the Ampero Mini. The Mini's USB-MIDI protocol differs from
the Ampero II Stage, so nothing here is shared with those.

## What you need

* An Ampero Mini on a USB port of a Linux machine that runs Docker.
* Docker with Compose.
* About ten minutes.

## Run it

1. Copy `.env.example` to `.env` and put a long random string in `API_KEY`.
   Anyone who has that key can change your pedal.
2. Start it:

        docker compose up -d --build

3. Check it. `/health` needs no key:

        curl http://localhost:28551/health

   `pedal_connected` should be `true`. The compose file maps host port 28551 to
   the container's 8080. Change the left number if you want another port.

The container gets `/dev/bus/usb` and a cgroup rule for USB devices (major 189).
It does not get `/dev/snd`, on purpose. The pedal only has to be plugged in when
you want to change something, and replugging it is fine.

### Dockhand

Create a stack from `docker-compose.yml`. Set `API_KEY` in the stack's
**Environment** tab. The compose file uses a plain `${API_KEY}`, so Dockhand fills
it in when it deploys. Do not paste the key into the compose file.

## Using it with your AI agent

Give the agent three things: the bridge's address, the `X-Api-Key` value, and
this file (or `docs/models.md`). Then ask in plain words. It can do any of these:

* Build a preset from scratch: pick the blocks and models, set the knobs, name it, save it.
* Tweak a preset that already exists: read it, change a few parameters, save.
* Swap a model in one block (a different drive, amp or reverb) and keep the rest.
* Turn blocks on or off, or clean up a preset so it only uses what it needs.
* Check a patch: read it back and say what is in it.
* Back up a patch before changing it, and put it back if you do not like the result.

A prompt that works for any of those:

> You can control my Hotone Ampero Mini through a web API at http://SERVER:28551.
> Send the key in the `X-Api-Key` header. Read README.md in the ampero-bridge repo
> first. Here is what I want: [for example "a bright clean tone with light spring
> reverb in P26-1", or "on the patch that is selected now, lower the drive and
> swap the delay for a slapback"]. Read the patch before you change anything and
> keep it as a backup. Make every change first, read it back to check, and save
> last.

The agent should follow this order. It is the order that keeps the pedal safe:

1. `GET /health`. Make sure the pedal is connected.
2. `POST /api/patch/select` the slot you want to edit.
3. `GET /api/patch/current`. Keep the `record_hex` as a restore point.
4. `POST /api/block` to turn blocks on or off. Do not assume everything is on:
   turn off what the patch does not use.
5. `POST /api/model` to pick the model for each block, then `POST /api/param` for
   each knob. A model change resets that block's knobs to defaults, so set the
   model first.
6. `GET /api/patch/current` again and compare. This is the only proof a write
   worked, because the pedal never answers a write.
7. `POST /api/patch/save`, last, with the confirm text.

### Models

A model is picked by a number, not a name. `docs/models.md` lists the numbers that
have been checked on a real pedal. The numbers are not simply the screen number
minus one for every block (the effects list jumps in places), so an agent should
not guess one. The safe way to learn a new model: pick it on the pedal, read the
patch, and take the number from the record. Hotone's manual says
what real gear each model is based on.

### Example calls

    KEY=your-key
    H="X-Api-Key: $KEY"
    curl -H "$H" http://localhost:28551/api/patch/current
    curl -H "$H" -X POST -d '{"index": 75}' http://localhost:28551/api/patch/select
    curl -H "$H" -X POST -d '{"block": "rvb", "on": true}' http://localhost:28551/api/block
    curl -H "$H" -X POST -d '{"slot": "rvb", "code": 4}' http://localhost:28551/api/model
    curl -H "$H" -X POST -d '{"slot": "rvb", "model_code": 4, "param": 0, "value": 15}' http://localhost:28551/api/param
    curl -H "$H" -X POST -d '{"index": 75, "name": "MY PATCH", "confirm": "SAVE P26-1"}' http://localhost:28551/api/patch/save

Patch `index` is the Program Change number, counting from 0. Index 75 is the
pedal's P26-1 (three patches per bank).

## API

Send `X-Api-Key`. Only `/health` is open.

| Call | Body | What it does |
| --- | --- | --- |
| `GET /health` | | liveness, `pedal_connected`, request counters, `usb_seen` (how many USB devices the service can see) |
| `GET /api/usb` | | interfaces and endpoints the pedal reports, plus every USB device the service sees. If this lists fewer devices than `lsusb` on the host, restart the container |
| `GET /api/patch/current` | | read the patch the pedal has selected: `index`, `label`, `name`, `record_hex` |
| `GET /api/patch/<index>` | | same, but 409 (with `current_index`, `current_name`) unless `<index>` is the selected patch. Select it first |
| `POST /api/patch/select` | `{"index": 75}` | Program Change (0 based, 75 = P26-1) |
| `POST /api/block` | `{"block": "rvb", "on": true}` | block on/off (fx1 fx2 amp nr cab eq fx3 dly rvb) |
| `POST /api/model` | `{"slot": "rvb", "code": 4}` | pick a model for a slot |
| `POST /api/param` | `{"slot": "rvb", "model_code": 4, "param": 0, "value": 15}` | set one parameter (0-127) |
| `POST /api/patch/save` | `{"index": 75, "name": "WADE", "confirm": "SAVE P26-1"}` | save to a slot; needs the exact confirm text |

Errors come back as `{"error", "kind"}`: 400 bad input, 401 key, 503 pedal not
connected or busy, 504 pedal silent, 502 other USB error.

The record is 460 bytes: the name, then nine blocks (fx1, fx2, amp, nr, cab, eq,
fx3, dly, rvb) with their model and parameters. The layout is in `docs/protocol.md`.

## Safety

* **Save is always the last step.** A save stores whatever is in the pedal's edit
  buffer at that moment. Make every change, read it back, then save.
* A save needs the exact `confirm` text, so a stray call cannot overwrite a patch.
* Do not send a model number you have not read off the pedal.
* Keep `API_KEY` private and do not expose the port to the internet.

## Settings

Set these in `.env` (or Dockhand's Environment tab).

| Var | Default | |
| --- | --- | --- |
| `API_KEY` | required | the key clients send in `X-Api-Key` |
| `PORT` | 8080 | port inside the container |

More options (USB timeouts and so on) are listed in `docs/usb-lockups.md`.

## Develop

    pip install pyusb pytest
    python -m pytest

Tests use a fake pedal. Frames are checked byte for byte against the ones
captured from the editor and the pedal.

## Docs

* `docs/protocol.md`: the USB and SysEx protocol, record layout, order of a preset write
* `docs/models.md`: model numbers checked on a real pedal
* `docs/usb-lockups.md`: USB stability notes and the less common settings

Credits: the Ampero II Stage work by jpfaria (github.com/jpfaria/hotone-ampero-2)
started this, but the Mini uses a different header, so none of its frames are used here.
