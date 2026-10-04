# Knobs: which parameter is which

`POST /api/param` sets one knob:

    {"slot": "dly", "model_code": 9, "param": 2, "value": 110}

* `slot` is the block (`fx1 fx2 amp nr cab eq fx3 dly rvb`).
* `model_code` must be the code the block holds right now (see `docs/models.md`). Set the model first: a model change resets that block's knobs to defaults.
* `param` is the knob's position, counting from 0, in the order of the tables below. This is the order of the Hotone manual's parameter list for that model, and the same order the values appear in the record.
* `value` is 0-127. The bridge refuses anything else, because nothing larger has been seen on the wire. A knob whose range is larger (a delay time over 127 ms) cannot be set from the bridge yet.

To read a knob, take the record (`GET /api/patch/current`, field `record_hex`), go to the block's state offset (`docs/protocol.md`, "Record layout") and read two bytes at `state offset + 4 + 2 * param`, low byte first. Knob values are the same numbers the pedal shows.

Switches read as 0 (Off) and 1 (On). Ranges below are from the manual: `0-100` unless noted.

How sure each entry is:

* **Checked**: the order matches both the manual and a record read back from a real pedal.
* **Manual**: the order and names come from the manual and the parameter count matches the record, but it was not set and read back here.
* **Unknown**: only the parameter count and the default values are known (`docs/models.md`). Do not guess the knob names. Pick the model on the pedal, turn one knob, read the record, and see which position changed.

## AMP

| Model | Code | Knobs in order | Status |
| --- | --- | --- | --- |
| Marshell 50 (normal channel) | 55 | 0 Volume, 1 Presence, 2 Master, 3 Bass, 4 Middle, 5 Treble | Checked (positions 3 and 5 are Bass and Treble) |

Other amps in the manual use the same names in one of two layouts: Volume, Presence, Master, Bass, Middle, Treble for the older style amps, or Gain, Presence, Master, Bass, Middle, Treble for the high gain ones. Treat any amp other than the one above as Manual at best until it has been read back.

## FX2 (drive, distortion, chorus)

The first table is Checked or Manual. The remaining FX2 models, with their parameter counts and defaults, are in `docs/models.md`.

| Code | Model | Knobs in order | Status |
| --- | --- | --- | --- |
| 0 | Green Drive | 0 Gain, 1 Tone, 2 Volume | Manual (the values in a record read back fit this order) |
| 1 | Super Drive | 0 Gain, 1 Tone, 2 Volume | Manual |
| 2 | Screamood | 0 Gain, 1 Tone, 2 Volume, 3 Fat, 4 Air | Manual |
| 3 | Zen Garden | 0 Gain, 1 Tone, 2 Volume, 3 Voice | Manual |
| 4 | Big Pie | 0 Sustain, 1 Tone, 2 Volume | Checked |
| 5 | Face Fuzz | 0 Fuzz, 1 Volume | Manual |
| 7 | Black-Rat-style distortion | 0 Gain, 1 Filter, 2 Volume | Manual |
| 8 | Smooth Dist | 0 Gain, 1 Tone, 2 Volume | Manual |
| 9 | Governor | 0 Gain, 1 Volume, 2 Bass, 3 Middle, 4 Treble | Manual (the values in a record read back fit this order) |
| 10 | Crunchist | 0 Gain, 1 Tone, 2 Volume | Manual |
| 11 | Bass Crusher | 0 Gain, 1 Blend, 2 Volume, 3 Bass, 4 Treble | Manual |
| 89 | Satisfaction | 0 Saturation, 1 Mix, 2 Output, 3 High Cut | Manual |
| 91 | Bit Krusher | 0 Mix, 1 Krush, 2 Bit, 3 Hi Cut, 4 Lo Cut | Manual |
| 112 | Aozora Chorus | 0 Depth, 1 Rate, 2 Tone, 3 Sync | Manual |
| 113 | Grand Choruium | 0 Depth, 1 Rate, 2 Volume, 3 Sync | Manual |
| 114 | Liquid C | 0 Mode | Manual |
| 115 | Choruium B | 0 Depth, 1 Rate, 2 E.Level, 3 Sync | Manual (less sure) |

## FX1

| Code | Model | Knobs in order | Status |
| --- | --- | --- | --- |
| 137 | 90 Phaser | 0 Rate, 1 Sync | Checked |

## DLY

| Code | Model | Knobs in order | Status |
| --- | --- | --- | --- |
| 9 | Slapback | 0 Mix, 1 Feedback, 2 Time (20-300 ms), 3 Trail (Off/On) | Manual (the values in a record read back fit this order) |

Other delays in the manual start with Mix, Feedback, Time (20-4000 ms) and then add their own knobs and Sync and Trail switches. Not read back here.

## RVB

| Code | Model | Knobs in order | Status |
| --- | --- | --- | --- |
| 4 | Spring | 0 Mix, 1 Decay, 2 Tone, 3 Trail (Off/On) | Manual (the values in a record read back fit this order) |

Other reverbs start with Mix and then Decay (Hall and Church have Pre Delay first; Plate has High Damp). Not read back here.

## CAB, NR, EQ, FX3

Not mapped yet. The Cab block has a mic type, low and high cut, volume and mic position knobs, and its record holds values larger than 127 for some of them, so reading a cab is fine but changing its knobs from the bridge is not supported. UK Black 4x12 is code 34. Pick other cabs on the pedal and read the code from the record.
