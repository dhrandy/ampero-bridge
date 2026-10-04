# ampero-bridge

![ampero-bridge: an AI builds presets on the Hotone Ampero Mini](docs/banner.svg)

![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![REST API](https://img.shields.io/badge/REST-API-FFB020)
![USB MIDI](https://img.shields.io/badge/USB-MIDI-555555)
![Status: beta](https://img.shields.io/badge/status-beta-orange)

A small REST API in a Docker container that lets an AI agent, an LLM or any script
build presets on a Hotone Ampero Mini guitar effects pedal. The pedal plugs into a
computer over USB. This service runs on that computer and turns plain HTTP calls
into the USB MIDI messages the Hotone editor would send: pick a patch, switch
blocks on and off, choose amp, cab and effect models, set parameters, read a
preset back, and save it.

Hotone's own editor is point and click. This gives an AI the same hands, a preset
manager you can script.

## Beta

This is a beta. It works on the one Ampero Mini it was built and tested on, but
the USB protocol is partly reverse-engineered, so some things are not proven yet
(`docs/models.md` and `docs/knobs.md` say which). It has only been tried on a
single pedal and firmware, so your unit may behave differently. Back up a patch
before you let anything change it, and save last. Bug reports, and notes on what
works or breaks on your Mini, are welcome as GitHub issues.

## What it is for

You tell an agent "make me a clean Fender-ish patch with a bit of spring reverb",
and it does the work on the real pedal: it reads what is there, changes the
blocks, picks models, sets the knobs, checks its work by reading the patch back,
and saves. It can also back up a patch before touching it.

It has only been tested on the Ampero Mini, and that is the only pedal it
supports. The Mini's USB-MIDI protocol differs from the Ampero II Stage, so
nothing here is shared with those.

## What you need

* An Ampero Mini plugged into the same computer that runs the Docker container.
  The bridge talks to the pedal over that computer's USB bus, so it cannot reach
  a pedal on another machine. The computer must be Linux.
* Docker with Compose.
* About ten minutes.

## Run it

The whole setup is two files next to each other: `docker-compose.yml` and `.env`.
The repo has both (`.env.example` is the template for `.env`).

`docker-compose.yml` (builds the image straight from this repo, so there is
nothing else to download):

    services:
      ampero-bridge:
        # Builds straight from git.
        build: https://github.com/dhrandy/ampero-bridge.git#main
        # API_KEY comes from the .env file next to this one (or from the environment
        # settings of whatever deploys the stack). Never put the raw key in this file.
        environment:
          - PORT=8080
          - API_KEY=${API_KEY}
          # Optional overrides, only after checking GET /api/usb on the real pedal:
          # - AMPERO_USB_INTERFACE=3
          # - AMPERO_USB_MODE=midi   (midi = USB-MIDI 4-byte packets, raw = bytes as-is)
          # - AMPERO_USB_TIMEOUT_MS=1000
          # - AMPERO_ALLOW_UNPROVEN_MODELS=1   (let /api/model send model codes not yet proven)
        ports:
          # Published on every host interface so a reverse proxy on another machine
          # can reach it. This port speaks plain HTTP, so limit it with a firewall
          # rule to the proxy's address if you can.
          - "28551:8080"
        # libusb talks to the pedal directly. No /dev/snd: nothing in this container
        # may open an ALSA MIDI port, that is what wedged the host kernel.
        device_cgroup_rules:
          - "c 189:* rmw"
        volumes:
          # USB bus nodes, bind-mounted so replugging the pedal is seen live.
          - /dev/bus/usb:/dev/bus/usb
        # The bridge keeps no state and writes no files, so lock the container down.
        cap_drop:
          - ALL
        security_opt:
          - no-new-privileges:true
        read_only: true
        tmpfs:
          - /tmp:size=16m
        mem_limit: 128m
        pids_limit: 100
        # The bridge exits itself (code 70) if a USB request outlives its deadline,
        # so this brings it back clean. See docs/usb-lockups.md.
        restart: unless-stopped
        # Tiny init so signals reach the bridge and no zombies pile up.
        init: true
        # Docker only marks a wedged container unhealthy. The restart policy above
        # needs the process to exit, which the in-process watchdog does. /health is
        # the open liveness check and only returns {"ok": true}; pedal details are
        # behind the key at /api/health.
        healthcheck:
          test: ["CMD", "python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8080/health', timeout=4)"]
          interval: 30s
          timeout: 6s
          retries: 3
          start_period: 10s
        logging:
          driver: json-file
          options:
            max-size: "5m"
            max-file: "3"
        # The bridge exits immediately on SIGTERM, there is nothing to flush.
        stop_grace_period: 5s

`.env` (copy `.env.example` and fill it in):

    API_KEY=paste-a-long-random-string-here

Make the key with `openssl rand -hex 32`. Anyone who has it can change your pedal,
so the service will not start with a key under 24 characters or with the
placeholder. The compose file reads it as a plain `${API_KEY}`, so the key never
goes in the compose file.

1. Create the two files above in one folder.
2. Start it:

        docker compose up -d --build

3. Check it. `/health` needs no key and only says the service is up. The
   details are behind the key:

        curl http://localhost:28551/health
        curl -H "X-Api-Key: $API_KEY" http://localhost:28551/api/health

   `pedal_connected` should be `true`. The compose file maps host port 28551 to
   the container's 8080. Change the left number if you want another port.

The container gets `/dev/bus/usb` and a cgroup rule for USB devices (major 189).
It does not get `/dev/snd`, on purpose. The pedal only has to be plugged in when
you want to change something, and replugging it is fine. Any USB port works:
the bridge finds the pedal by its USB vendor and product ID (`84ef:0080`), not by
port, so moving it to another port is fine.

### Dockhand

Create a stack from `docker-compose.yml`. Set `API_KEY` in the stack's
**Environment** tab instead of a `.env` file. Dockhand fills in the `${API_KEY}`
when it deploys. Do not paste the key into the compose file.

### Behind a reverse proxy (Synology example)

The port speaks plain HTTP, so put TLS in front of it. On a Synology NAS: Control
Panel, Login Portal, Advanced, Reverse Proxy, Create. Source: HTTPS, your
hostname, port 443. Destination: HTTP, the IP of the computer running the
container, port 28551. Add a certificate for the hostname under Security, Certificate.

That is the whole setup. Without any firewall rule, this is what you have: the
container's port is open on the computer's LAN address (plain HTTP), the proxy is
the only thing meant to talk to it, and every `/api` call still needs the key. A
wrong or missing key gets a 401 and changes nothing. Keep the key long and
random, and do not forward port 28551 on your router.

Optional hardening: if you do run a firewall on the container host, limit port
28551 to the proxy's address. Docker's published ports skip the usual `ufw`
rules, so the rule has to go in the `DOCKER-USER` chain. Skip this if you do not
use firewall rules; the key is what protects the API.

## Using it with your AI agent

Give the agent three things: the bridge's address, the `X-Api-Key` value, and
this file (or `docs/models.md`). Then ask in plain words. It can do any of these:

* Build a preset from scratch: pick the blocks and models, set the knobs, name it, save it.
* Tweak a preset that already exists: read it, change a few parameters, save.
* Swap a model in one block (a different drive, amp or reverb) and keep the rest.
* Turn blocks on or off, or clean up a preset so it only uses what it needs.
* Check a patch: read it back and say what is in it, block by block (see "Reading what is in a patch" below).
* Back up a patch before changing it, and put it back if you do not like the result.

A prompt that works for any of those:

> You can control my Hotone Ampero Mini through a web API at http://SERVER:28551.
> Send the key in the `X-Api-Key` header. Read README.md in the ampero-bridge repo
> first. Here is what I want: [for example "a bright clean tone with light spring
> reverb in P26-1", or "on the patch that is selected now, lower the drive and
> swap the delay for a slapback"]. Read the patch before you change anything and
> keep it as a backup. Make every change first, read it back to check, and save
> last. To see what is in a patch, decode `record_hex` from `GET /api/patch/current`
> using "Reading what is in a patch" in README.md and docs/protocol.md; the server
> only decodes the name. Use docs/models.md for model numbers and
> docs/knobs.md for which knob is which. Never guess either: if a model is not
> listed as checked, say so and read the record to find out.

The agent should follow this order. It is the order that keeps the pedal safe:

1. `GET /api/health`. Make sure `pedal_connected` is true.
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

### Reading what is in a patch

`GET /api/patch/current` returns `index`, `label`, `name` and `record_hex`. The
name and slot come ready to use. The effect chain (which blocks are on, which
model each one runs, every knob value) is in `record_hex`, and the server does not
unpack it for you: the agent does that from the record layout in
`docs/protocol.md` ("Record layout"). The only decoding code in the repo is
`decode_patch()` in `ampero_mini.py`, which joins the pedal's reply into the
460-byte record and reads the index and name. Reading the blocks is a few lines:

    import json, urllib.request
    req = urllib.request.Request("http://SERVER:28551/api/patch/current",
                                 headers={"X-Api-Key": "your-key"})
    rec = bytes.fromhex(json.load(urllib.request.urlopen(req))["record_hex"])
    BLOCKS = {"fx1": 95, "fx2": 128, "amp": 161, "nr": 194, "cab": 227,
              "eq": 260, "fx3": 293, "dly": 326, "rvb": 359}
    for name, at in BLOCKS.items():
        on = rec[at] == 1
        model = rec[at + 1] * 128 + rec[at + 2]
        params = [int.from_bytes(rec[at + 4 + 2 * i : at + 6 + 2 * i], "little")
                  for i in range(5)]
        print(name, "on" if on else "off", "model", model, params)

Each block is 33 bytes. The state byte is 1 for on and 0 for off. The model is a
code, so look it up in `docs/models.md`. Knob values are two bytes each, low byte
first, and the first five cover most models. Which knob is which for a model is in
`docs/knobs.md`, with how sure each entry is. Reading never changes
the pedal; it also needs no select first if the patch you want is the one on the
screen.

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

Send `X-Api-Key`. Only `/health` is open, and it only returns `{"ok": true}`.

| Call | Body | What it does |
| --- | --- | --- |
| `GET /health` | | `{"ok": true}`, no key needed. Used by the Docker healthcheck |
| `GET /api/health` | | `pedal_connected`, request counters, `usb_seen` (how many USB devices the service can see) |
| `GET /api/usb` | | interfaces and endpoints the pedal reports, plus every USB device the service sees. If this lists fewer devices than `lsusb` on the host, restart the container |
| `GET /api/patch/current` | | read the patch the pedal has selected: `index`, `label`, `name`, `record_hex` |
| `GET /api/patch/<index>` | | same, but 409 (with `current_index`, `current_name`) unless `<index>` is the selected patch. Select it first |
| `POST /api/patch/select` | `{"index": 75}` | Program Change (0 based, 75 = P26-1) |
| `POST /api/block` | `{"block": "rvb", "on": true}` | block on/off (fx1 fx2 amp nr cab eq fx3 dly rvb) |
| `POST /api/model` | `{"slot": "rvb", "code": 4}` | pick a model for a slot. Only codes listed in `docs/models.md` as proven are accepted (see Settings) |
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
* `/api/model` only takes model numbers that were checked on a real pedal, because an unknown one can crash it. To try others, set `AMPERO_ALLOW_UNPROVEN_MODELS=1`.
* Keep `API_KEY` private and do not expose the port to the internet.

## Settings

Set these in `.env` (or Dockhand's Environment tab).

| Var | Default | |
| --- | --- | --- |
| `API_KEY` | required | the key clients send in `X-Api-Key` |
| `PORT` | 8080 | port inside the container |
| `AMPERO_ALLOW_UNPROVEN_MODELS` | off | set to `1` to let `/api/model` send model codes not listed as proven |

More options (USB timeouts and so on) are listed in `docs/usb-lockups.md`.

## Develop

    pip install -r requirements.txt pytest
    python -m pytest

Tests use a fake pedal. Frames are checked byte for byte against the ones
captured from the editor and the pedal.

## Docs

* `docs/protocol.md`: the USB and SysEx protocol, record layout, order of a preset write
* `docs/models.md`: model numbers checked on a real pedal
* `docs/usb-lockups.md`: USB stability notes and the less common settings

Credits: this was built for the Ampero Mini from scratch. The Mini speaks a
different USB-MIDI protocol from the Ampero II Stage, so no frames or code are
shared. jpfaria's Stage work (github.com/jpfaria/hotone-ampero-2) was a useful
reference for what is possible on the Stage.
