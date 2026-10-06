# Knobs: which parameter is which

`POST /api/param` sets one knob:

    {"slot": "dly", "model_code": 9, "param": 2, "value": 110}

* `slot` is the block (`fx1 fx2 amp nr cab eq fx3 dly rvb`).
* `model_code` must be the code the block holds right now (see `docs/models.md`). Set the model first: a model change resets that block's knobs to defaults.
* `param` is the knob's position, counting from 0, in the order of the tables below. This is the order of the Hotone manual's parameter list for that model, and the same order the values appear in the record.
* `value` is 0-127. The bridge refuses anything else, because nothing larger has been seen on the wire. A knob whose range is larger (a delay time over 127 ms) cannot be set from the bridge yet.

To read a knob, take the record (`GET /api/patch/current`, field `record_hex`), go to the block's state offset (`docs/protocol.md`, "Record layout") and read two bytes at `state offset + 4 + 2 * param`, low byte first. Knob values are the same numbers the pedal shows, except for the EQ bands (offset by 50) and the cab (see those sections).

Switches read as 0 (Off) and 1 (On). Ranges below are from the manual: `0-100` unless noted.

How sure each entry is:

* **Checked**: the order matches both the manual and a record read back from a real pedal.
* **Manual**: the order and names come from the manual and the parameter count matches the record, but it was not set and read back here.
* **Unknown**: only the parameter count and the default values are known (`docs/models.md`). Do not guess the knob names. Pick the model on the pedal, turn one knob, read the record, and see which position changed.

## FX1

| Code | Model | Knobs in order | Status |
| --- | --- | --- | --- |
| 137 | 90 Phaser | 0 Rate, 1 Sync | Checked |
| 45 | Classic PS | 0 Range (enum 0-5), 1 Position, 2 Mix | p0 write-verified (0-5); p1 and p2 not swept |

**Classic PS (FX1 code 45, FX2 code 93): p0 is a 0-5 enum. Never write 6.** The value 6 wedges the block until the pedal is power cycled. p0 write-verified on FX1 (0-5); FX2 uses the same bound, and 6 was left unwritten there on purpose.

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
| 7 | Black Tail | 0 Gain, 1 Filter, 2 Volume | Manual |
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

## AMP

| Model | Code | Knobs in order | Status |
| --- | --- | --- | --- |
| Jazz Clean | 4 | 1 Bright (switch, 0 off, 1 on); other positions in `docs/param-map.json` | p1 write-verified |
| Marshell 50 (normal channel) | 55 | 0 Volume, 1 Presence, 2 Master, 3 Bass, 4 Middle, 5 Treble | Checked (positions 3 and 5 are Bass and Treble) |

Other amps in the manual use the same names in one of two layouts: Volume, Presence, Master, Bass, Middle, Treble for the older style amps, or Gain, Presence, Master, Bass, Middle, Treble for the high gain ones. Treat any amp other than the one above as Manual at best until it has been read back.

## CAB

UK Black 4x12 (code 34) is Checked. The cab block does not use the eight 16-bit slots like the other blocks. Offsets below count from the start of the block's four-byte header (state, model hi, model lo, unused), so byte 4 is the first parameter byte.

| Byte | Knob | Encoding | Status |
| --- | --- | --- | --- |
| 4 | Mic type | Index. 9 = Con U87, 5 = Dyn112, 3 = Dyn421. Other mics not mapped | Checked for those three |
| 6 | Volume | 0-100, raw | Checked |
| 8 | Position X | 0-100, raw | Checked |
| 10 | Position Y | 0-100, raw | Checked |
| 12 | Position Z | 0-100, raw, one byte | Checked |
| 13, 14 | Low Cut | Two 7-bit halves, `(byte13 << 7) \| byte14`. Hz = value + 19. 0 = off | Checked |
| 15, 16 | High Cut | Two 7-bit halves. Hz = 2000 + 10 * value. 1801 (bytes `0e 09`) = off | Checked |

The cuts overlap what would be parameter slots 4 to 6 in the other blocks, which is why a cab record looks like it has values over 127. Mic, volume and the three positions fit in 0-127. Low Cut goes up to about 1900 and High Cut up to 1800, so the bridge cannot set either. Other cab models were not checked and may differ. The pedal screen splits these over three pages; the record is one flat list.

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

## NR

The first byte of the block is the on/off switch (1 on, 0 off).

| Code | Model | Knobs in order | Status |
| --- | --- | --- | --- |
| 0 | Smart Gate (screen 01) | 0 Threshold (0-100) | Checked |
| 1 | Fast Gate (screen 02) | 0 Threshold (0-100), 1 Mode (0 = I, 1 = II) | Checked (Mode II = 1 read; Mode I = 0 inferred) |

## EQ

| Code | Model | Knobs in order | Status |
| --- | --- | --- | --- |
| 0 | Guitar EQ 1 (screen 01) | 0 125 Hz, 1 400 Hz, 2 800 Hz, 3 1.6 kHz, 4 4 kHz, 5 Volume | Checked |

The five bands show -50 to +50 on the pedal and are stored as the shown value plus 50 (0 to 100, 50 is flat). Volume is stored as shown (0-100). The pedal screen splits the knobs over two pages; the record is one flat list. Other EQ models (Guitar EQ 2, Bass EQ 1 and 2, Para EQ) were not checked.

## FX3

The full per-parameter map, with every param tagged write-verified, confirmed at its address only, inferred or not swept, is in `docs/param-map.json`. A record byte at offset 459 changes on every edit; it is a trailer, not a parameter. Turning any Sync switch on rewrites the linked Rate to 40.

FX3 has its own model list; its codes are not the FX2 codes (Liquid C is 114 in FX2) and they do not follow the screen number past screen 17 (see the list in `docs/models.md`). Read each model's code from the record.

| Code | Model (screen number) | Knobs in order | Status |
| --- | --- | --- | --- |
| 2 | Liquid C (03) | 0 Mode (stored as the shown mode minus 1; mode 3 read as 2) | Checked for one value |
| 6 | Jetter B (07) | 0 Depth, 1 Rate, 2 Pre Delay, 3 Feedback, 4 Sync (Off/On) | Checked |
| 16 | Custom Trem (17) | 0 Depth, 1 Rate, 2 Volume, 3 Color, 4 Shape (0 sine, 1 triangle, 2 square, 3 sawtooth), 5 Bias, 6 Sync (0/1) | Rate, Shape and Sync write-verified; Depth, Volume, Color and Bias confirmed at their address only. Turning Sync on resets Rate to 40 |
| 64 | Acoustic Refiner (18) | 0 Shape (0-100) | p0 write-verified; other positions not mapped |
| 69 | Harmony (23) | 0 Hi pitch, 1 Low pitch, 2 Dry, 3 Hi volume, 4 Low volume | Hi and Low pitch write-verified; Dry, Hi volume and Low volume confirmed at their address only (0-100 range from the manual) |
| 73 | Bit Krusher (27) | 0 Mix, 1 Krush, 2 Bit, 3 Hi Cut, 4 Lo Cut | Checked |
| 75 | Sweller (29) | Attack (14 bits, see below), 1 Curve (0 Line, 1 Exp, 2 Log) | Attack (14-bit) and Curve write-verified; the bridge cannot send the 14-bit attack yet |

Jetter B: all ranges 0-100 raw. Rate read 20 before Sync was turned on and 40 after, with no knob turn recorded. That change is observed but unexplained. Other FX3 models were not checked.

Harmony: Hi pitch runs 0 to +24 on the screen and is stored as shown. Low pitch runs 0 to -24 on the screen and is stored as the shown value plus 24 (screen 0 is stored 24, screen -24 is stored 0). Hotone draws the Low pitch slider backwards, with 0 at the far left. Dry, Hi volume and Low volume are 0-100.

Parameter writes to FX3 and NR go through slots 07 and 04. NR has only Smart Gate p0 (Threshold) write-verified; Fast Gate and the rest of NR are not swept.

Custom Trem: the Shape enum is 0-3 only. Sync is 0 or 1, and turning it on sets Rate to 40.

Sweller: Attack is 80 to 4000 ms; stored raw = ms - 80, split into 7-bit halves, high half at record byte 296 and low half at byte 297. So ms = 80 + (byte 296 * 128 + byte 297). Read back at 80, 1000, 2353 and 4000. Curve was read as 0, 1 and 2 for Line, Exp and Log.

The pedal screen splits the knobs over pages, the record is one flat list. Selecting a model can reload its defaults (Sweller went back to Attack 1000, Curve Line after leaving the screen and coming back). It did not always do this.
