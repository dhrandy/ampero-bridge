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

- Anything without a documented range, the packed cab fields (Z, Low Cut, High Cut) and Magic T Treble.
- Wide params (delay Time, Sweller Attack). The bridge has no 14-bit writer yet.
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
