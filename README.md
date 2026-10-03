# ampero-bridge

HTTP bridge for the Hotone Ampero Mini. The pedal plugs into the NAS over USB
when Randy wants changes; this service speaks its SysEx protocol over USB MIDI
and exposes a small key-gated HTTP API so Todd can read patches and push effect
settings without the Hotone editor.

## Protocol

The Ampero family talks MIDI SysEx over USB. Frame format and commands were
reverse-engineered from the Hotone editor (see `ampero_mini.py`). Adapted from
the Ampero II Stage work at github.com/jpfaria/hotone-ampero-2 (MIT).

Mini specifics used here (verify against hardware on first connect):
- 9 effect slots (II Stage has 12)
- 198 patches, 5 per bank (A1-1 .. A40-3 roughly)
- MIDI port name expected: `Ampero Mini MIDI` (override with AMPERO_PORT)

## Deploy (CasaOS / Dockhand, compose only)

Same pattern as mc-bot:

1. `git clone https://github.com/dhrandy/ampero-bridge.git` on the NAS
   (one time).
2. In Dockhand, create a stack from the repo's `docker-compose.yml`.
3. Set `API_KEY` in Dockhand's Environment tab (same key Todd uses).
4. The container needs `/dev/snd` for USB MIDI. If the pedal isn't seen,
   check the port name with `amidi -l` on the host and set AMPERO_PORT.

To update: `git pull` in the repo directory on the NAS, then rebuild in
Dockhand. No registry images, no remote builds.

The pedal only needs to be plugged in when changes are wanted. `/health`
reports `pedal_connected` so Todd knows whether it's there.

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

## Known issue (Oct 3, 2026)

The NAS's ALSA/USB MIDI driver hangs when the bridge communicates with the
Ampero Mini. Symptoms: the pedal's MIDI port opens fine, but it never answers
SysEx (not even standard identity requests), and the bridge process wedges in
the kernel (D-state, unkillable without reboot). Unplugging the pedal does not
recover it. The bridge code and deployment are fine; this is a driver/hardware
compatibility issue between the Synology USB stack and the Mini. Possible
alternative: talk raw USB (pyusb) instead of ALSA MIDI, but the Mini's USB
protocol is undocumented.

## Safety

- Never send `model` with a guessed category/code: a wrong category byte can
  hang the pedal's SysEx until power-cycle.
- Writes go to the edit buffer; nothing is permanent until `save`.
- If the pedal stops responding to SysEx, power-cycle it (USB replug is not enough).
