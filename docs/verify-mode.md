# Verify mode

A switch for checking a few more params on a real pedal, one write at a time, without loosening the normal
rules. It is off unless the bridge is started with `AMPERO_VERIFY_MODE=1`, and even then only a write that
says `"verify": true` uses it. Every other write goes through the strict rules exactly as before.

## What it admits

- Params whose range is documented in the vendor editor database but that the map has not swept. Today that
  is Classic PS Position and Mix (0-100) and Para EQ Hi Shelf (raw 0-24) and Volume (0-100). Each takes only
  its documented range.
- Everything the strict rules already allow with `"unverified_ok": true`, still inside its range or enum.

## What it will not write

- Anything without a documented range or an enabled encoding. Unrelated wide fields stay capped.
- Newly decoded fields have bounded opt-in rules, but their new outgoing writes are not hardware-proven.
  Cab addressing and wide high-byte writes still need an outgoing editor capture before live testing.
- A model that is not in the proven list, even with `AMPERO_ALLOW_UNPROVEN_MODELS=1`.

## Synced Rate

A Rate that follows a Sync switch is a division step when Sync is on: 0, 10, 20 ... 100 (1/1 to 1/16). The
bridge reads the patch the pedal holds, finds the Sync switch for that Rate, and refuses a value that is not a
step. It also refuses when the pedal holds a different model than the request names, when it cannot read the
state, and for a Rate the map cannot tie to one Sync switch (Sweep Eko, 2290 Mod). With Sync off a Rate is a
free 0-100 knob.

## Requests and errors

    POST /api/param {"slot": "eq", "model_code": 4, "param": 14, "value": 50, "verify": true}

`verify` must be the JSON value `true`. Refusals are 422 with a `reason`: `verify_mode_off`,
`model_not_proven`, `blocked_param`, `wide_param`, `out_of_range`, `not_in_enum`, `not_a_division`,
`sync_unknown`, `model_mismatch`. With the mode on, `GET /api/rules` adds `verify_range` and `sync_param` per
param. Reading the result back is the caller's job: use `GET /api/patch/current` and the decoder in
`records.py` (`decode_params`).

Only the edit buffer changes. Nothing here saves a patch.

## Read-confirmed fields (v2.12.0)

The encoder carries HI/LO as two seven-bit bytes. Delay Time uses its editor raw
maximum (3980 normally, Backmask 1980, Slapback 280), FX3 Sweller Attack 0-3920,
cab Z 0-100, Low Cut 0-1981 and High Cut 0-1801, FX1 Magic T Treble 0-100.
These rules were unverified when added. The synthetic tests prove limits and byte ownership,
not an actual outgoing USB transaction. Capture that transaction before live testing.

Analog Eko Time, FX2 Sweller Attack and cab Z, Low Cut and High Cut left this list in
v2.12.3 after live write and read-back tests (see docs/protocol.md). FX3 Sweller Attack,
the other delay models and FX1 Magic T Treble remain unverified.

FX2 Magic T Treble left this list in v2.12.1: 65, 0, 100 and 50 written through the
bridge each read back exactly on a throwaway patch, edit buffer only.

Time checks current Sync even on the strict opt-in path. Analog Eko was read at
all eleven division steps: 0,398,796,1194,1592,1990,2388,2786,3184,3582,3980.
Other synced Time scales are intentionally refused rather than inferred.
