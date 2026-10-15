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
- Unlisted new fields remain unverified. The October 14 live tests below cover only the listed
  models, fields and states; they do not establish a general wide-write guarantee.
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
not an actual outgoing USB transaction. Later live checks are listed below.

Analog Eko Time, FX2 Sweller Attack and cab Z, Low Cut and High Cut left this list in
v2.12.3 after live write and read-back tests (see docs/protocol.md). The remaining
checks below were added in v2.12.4.

FX2 Magic T Treble left this list in v2.12.1: 65, 0, 100 and 50 written through the
bridge each read back exactly on a throwaway patch, edit buffer only.

Time checks current Sync even on the strict opt-in path. Analog Eko was read at
all eleven division steps: 0,398,796,1194,1592,1990,2388,2786,3184,3582,3980.
The same table serves every delay model with the identical 0-3980 Time layout
(opened in v2.12.5, write-proven on all fourteen in v2.12.6). Backmask's
different maximum keeps its scale refused rather than inferred.

## Added write proof (v2.12.4)

FX3 Sweller Attack (0, 100, 920, 3920), Time on all 17 delays (100 and each
maximum, Sync off), FX1 Magic T Treble (65, 0, 100, 50), and Magic T Mode on
FX1/FX2 (2 and 0) now have live write/read-back proof. Mode 1 was already stored;
its write was a no-op, not proven as a changed value. The documented enum is unchanged.
Analog Eko synced Time was written at 398, 1592, 3980 and 0; other division steps
are read-confirmed only. Other models' synced Time remains unverified and refused.
Turning Sync off restores the model default Time, not the last value set.
Cab Z/cuts passed on seven cab codes (0, 13, 25, 49, 112, 144, 153). Shared rules
assume the same layout on other cabs, not individual live proof on all 70.

## Added write proof (v2.12.5)

Cab Z/cuts were swept on all 70 cab codes: 490 live writes, every read-back
exact, record bytes identical across models, so no cab is assumed any more.
Magic T Mode 1 was written live on FX1 and FX2 as a changed value and read back
exact, completing the enum proof. Synced-Time division tables (index x 398 over
0-3980) were opened on the fourteen delay models sharing Analog Eko's Time
layout; those tables were live read-back pending at this release.

## Added write proof (v2.12.6)

Synced Time on the fourteen 0-3980 delay models: all eleven division steps
written live on each model and read back exact (154 writes), plus Sync on/off
on each (closing Sweetie's editor-defined Sync switch). Edit buffer only,
nothing saved. Only the written Time/Sync bytes and the record checksum moved.
All checks were edit-buffer only, nothing saved, no USB errors, expected bytes
plus checksum only. No other fields gain verified status in this release.
