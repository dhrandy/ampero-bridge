# Ampero Mini model codes

Code = what the pedal stores in the record and what `POST /api/model` sends. For the models checked live,
code = on-screen number minus 1 (FX2: Big Pi 05 -> 4, Black Tail 08 -> 7, Governor 10 -> 9; CAB: UK Black 4x12 35 -> 34;
DLY: Slapback 10 -> 9; RVB: Spring 05 -> 4). The FX2 codes below jump (0-15, 48-54, 80-93, 112-134), so the
screen-minus-1 rule is not a straight count for every slot: read the code from the record, do not compute it.

## Proven live (set on the pedal, read back from the record)

| Slot | Screen | Name | Code |
| --- | --- | --- | --- |
| FX2 | 05 | Big Pi | 4 |
| FX2 | 08 | Black Tail | 7 |
| FX2 | 10 | Governor | 9 |
| FX2 | 01 | Green Drive (TS-808) | 0 (set from the bridge; not checked on the screen) |
| FX1 | 47 | 90 Phaser | 137 (params: Rate, Sync) |
| CAB | 35 | UK Black 4x12 | 34 |
| AMP | - | Marshell 50 (normal channel) | 55 |
| DLY | 10 | Slapback | 9 |
| RVB | 05 | Spring | 4 |

Writing a model from the bridge (`POST /api/model`) gave the same record as picking it on the pedal (checked for FX2).

FX1 has its own list. Its numbering is not FX2's: screen 47 is code 137, and FX1's default was code 76, which the FX2 list does not contain. Read FX1 codes from the record after picking the model on the pedal.

## FX2 code list (from a listen-only scroll, 60 models)

Names are from the manual where the parameter count and order match; `?` means not named yet. Only the rows above were checked on the pedal.

| Screen | Code | Params (defaults) | Name |
| --- | --- | --- | --- |
| 1 | 0 | 3 | Green Drive |
| 2 | 1 | 3 | Super Drive |
| 3 | 2 | 5 | Screamood |
| 4 | 3 | 4 | Zen Garden |
| 5 | 4 | 3 | Big Pie |
| 6 | 5 | 2 | Face Fuzz |
| 7 | 6 | 2 | Bend Fuzz |
| 8 | 7 | 3 | ? (Black-Rat-style distortion) |
| 9 | 8 | 3 | Smooth Dist |
| 10 | 9 | 5 | Governor |
| 11 | 10 | 3 | Crunchist |
| 12 | 11 | 5 | Bass Crusher |
| 13 | 12 | 5 | ? |
| 14 | 13 | 5 | ? |
| 15 | 14 | 3 | ? |
| 16 | 15 | 3 | ? |
| 17 | 48 | 2 | ? |
| 18 | 49 | 7 | ? |
| 19 | 50 | 4 | ? |
| 20 | 51 | 4 | ? |
| 21 | 52 | 3 | ? |
| 22 | 53 | 1 | ? |
| 23 | 54 | 2 | ? |
| 24 | 80 | 4 | ? |
| 25 | 81 | 5 | ? |
| 26 | 82 | 7 | ? |
| 27 | 83 | 3 | ? |
| 28 | 84 | 3 | ? |
| 29 | 85 | 3 | ? |
| 30 | 86 | 3 | ? |
| 31 | 87 | 5 | ? |
| 32 | 88 | 2 | ? |
| 33 | 89 | 4 | Satisfaction |
| 34 | 90 | 6 | ? |
| 35 | 91 | 5 | Bit Krusher |
| 36 | 92 | 4 | ? |
| 37 | 93 | 4 | ? |
| 38 | 112 | 4 | Aozora Chorus |
| 39 | 113 | 4 | Grand Choruium |
| 40 | 114 | 1 | Liquid C |
| 41 | 115 | 4 | Choruium B |
| 42 | 116 | 3 | ? |
| 43 | 117 | 5 | ? |
| 44 | 118 | 5 | ? |
| 45 | 119 | 3 | ? |
| 46 | 120 | 4 | ? |
| 47 | 121 | 2 | ? |
| 48 | 122 | 3 | ? |
| 49 | 123 | 5 | ? |
| 50 | 124 | 3 | ? |
| 51 | 125 | 7 | ? |
| 52 | 126 | 2 | ? |
| 53 | 127 | 3 | ? |
| 54 | 128 | 4 | ? |
| 55 | 129 | 5 | ? |
| 56 | 130 | 5 | ? |
| 57 | 131 | 5 | ? |
| 58 | 132 | 5 | ? |
| 59 | 133 | 5 | ? |
| 60 | 134 | 5 | ? |
