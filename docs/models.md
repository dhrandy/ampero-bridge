# Ampero Mini model codes

Code = what the pedal stores in the record and what `POST /api/model` sends. For the models checked live,
code = on-screen number minus 1 (FX2: Big Pie 05 -> 4, Black Tail 08 -> 7, Governor 10 -> 9; CAB: UK Black 4x12 35 -> 34;
DLY: Slapback 10 -> 9; RVB: Spring 05 -> 4). The FX2 codes below jump (0-15, 48-54, 80-93, 112-134), so the
screen-minus-1 rule is not a straight count for every slot: read the code from the record, do not compute it.

Which knob is which for each model is in `docs/knobs.md`, and in each model's Details on the model library page (from `docs/param-map.json`).

Everything here is a snapshot of firmware V2.2. Hotone can add, rename or reorder models in an update, and the codes may move with them. Check a code with a read-back before relying on it after a firmware change.

## Proven live (set on the pedal, read back from the record)

| Slot | Screen | Name | Code |
| --- | --- | --- | --- |
| FX1 | 47 | 90 Phaser | 137 (params: Rate, Sync) |
| FX2 | 05 | Big Pie | 4 |
| FX2 | 08 | Black Tail | 7 |
| FX2 | 10 | Governor | 9 |
| FX2 | 01 | Green Drive (TS-808) | 0 (set from the bridge) |
| AMP | - | Marshell 50 (normal channel) | 55 |
| CAB | 35 | UK Black 4x12 | 34 |
| DLY | 10 | Slapback | 9 |
| RVB | 05 | Spring | 4 |

`POST /api/model` accepts only the codes in this table (per slot), plus every code in the FX1, FX2, AMP, CAB, EQ, DLY and RVB tables below (all read on a real pedal by stepping through each list). FX3 (slot 07) and NR (slot 04) are accepted too. Their param writes are pedal-verified; model select on those two slots is not yet. Set `AMPERO_ALLOW_UNPROVEN_MODELS=1` to send others.

Writing a model from the bridge (`POST /api/model`) gave the same record as picking it on the pedal (checked for FX2).

FX1 has its own list. Its numbering is not FX2's: screen 47 is code 137, and FX1's default was code 76, which the FX2 list does not contain. The full FX1 and AMP code tables further down come from stepping through the pedal's lists and reading the record; only the rows in the table above were also set from the bridge, and only those are accepted by `POST /api/model`.

## FX2 models (60)

The FX2 list has 60 models, in the editor's order. The codes jump in groups (0-15, 48-54, 80-93, 112-134). All 60 codes were read from the record while stepping through the pedal's FX2 list by hand (the poller at 4 s, every stop caught). The rows in the proven table above were also set from the bridge. The names match the FX1 list below: FX2 screens 1 to 16 are FX1 screens 22 to 37, 17 to 23 are FX1 1 to 7, 24 to 37 are FX1 8 to 21, and 38 to 60 are FX1 38 to 60.

| Screen | Code | Params (defaults) | Name |
| --- | --- | --- | --- |
| 1 | 0 | 3 | Green Drive |
| 2 | 1 | 3 | Super Drive |
| 3 | 2 | 5 | Screamood |
| 4 | 3 | 4 | Zen Garden |
| 5 | 4 | 3 | Big Pie |
| 6 | 5 | 2 | Face Fuzz |
| 7 | 6 | 2 | Bend Fuzz |
| 8 | 7 | 3 | Black Tail |
| 9 | 8 | 3 | Smooth Dist |
| 10 | 9 | 5 | Governor |
| 11 | 10 | 3 | Crunchist |
| 12 | 11 | 5 | Bass Crusher |
| 13 | 12 | 5 | Solid Steel |
| 14 | 13 | 5 | Magic T |
| 15 | 14 | 3 | Blues Butter |
| 16 | 15 | 3 | Dr. Blues |
| 17 | 48 | 2 | Comprosso |
| 18 | 49 | 7 | Squeezer |
| 19 | 50 | 4 | Affinity Boost |
| 20 | 51 | 4 | FET Boost |
| 21 | 52 | 3 | Enhancer |
| 22 | 53 | 1 | Smart Gate |
| 23 | 54 | 2 | Fast Gate |
| 24 | 80 | 4 | AC Sim |
| 25 | 81 | 5 | Toucher |
| 26 | 82 | 7 | Crier |
| 27 | 83 | 3 | Voxy Wah |
| 28 | 84 | 3 | Cry Wah |
| 29 | 85 | 3 | Bass Press |
| 30 | 86 | 3 | Clean Octa |
| 31 | 87 | 5 | Harmony |
| 32 | 88 | 2 | Telephone Line |
| 33 | 89 | 4 | Satisfaction |
| 34 | 90 | 6 | Path Filter |
| 35 | 91 | 5 | Bit Krusher |
| 36 | 92 | 4 | Ring Mod |
| 37 | 93 | 4 | Classic PS |
| 38 | 112 | 4 | Aozora Chorus |
| 39 | 113 | 4 | Grand Choruium |
| 40 | 114 | 1 | Liquid C |
| 41 | 115 | 4 | Choruium B |
| 42 | 116 | 3 | Detune |
| 43 | 117 | 5 | Jetter |
| 44 | 118 | 5 | Jetter B |
| 45 | 119 | 3 | Pulser |
| 46 | 120 | 4 | Grand Vibrato |
| 47 | 121 | 2 | 90 Phaser |
| 48 | 122 | 3 | Green Phaser |
| 49 | 123 | 5 | Revolver |
| 50 | 124 | 3 | Helicopter |
| 51 | 125 | 7 | Custom Trem |
| 52 | 126 | 2 | Sweller |
| 53 | 127 | 3 | Gated Boost |
| 54 | 128 | 4 | Pitch Shift |
| 55 | 129 | 5 | Precise Attack |
| 56 | 130 | 5 | Sound Clone 1 |
| 57 | 131 | 5 | Sound Clone 2 |
| 58 | 132 | 5 | Sound Clone 3 |
| 59 | 133 | 5 | Sound Clone 4 |
| 60 | 134 | 5 | Sound Clone 5 |

## FX3 list (screen number, code, name)

FX3 has its own list of 30 models, in the editor's order. It is not the FX2 list (Liquid C is code 114 in FX2, 2 in FX3). Codes are screen minus 1 for screens 1 to 17 and screen plus 46 from 18 onwards. All 30 codes were read from the record while stepping through the pedal's FX3 list by hand, and the pattern held at every stop (0-16, then 64-76). `/api/model` accepts every code in this table.

| Screen | Code | Name | Source |
| --- | --- | --- | --- |
| 01 | 0 | Aozora Chorus | pedal-proven |
| 02 | 1 | Grand Choruium | pedal-proven |
| 03 | 2 | Liquid C | pedal-proven |
| 04 | 3 | Choruium B | pedal-proven |
| 05 | 4 | Detune | pedal-proven |
| 06 | 5 | Jetter | pedal-proven |
| 07 | 6 | Jetter B | pedal-proven |
| 08 | 7 | Jetter N | pedal-proven |
| 09 | 8 | Trem Jet | pedal-proven |
| 10 | 9 | Pulser | pedal-proven |
| 11 | 10 | Grand Vibrato | pedal-proven |
| 12 | 11 | Shiver T | pedal-proven |
| 13 | 12 | 90 Phaser | pedal-proven |
| 14 | 13 | Green Phaser | pedal-proven |
| 15 | 14 | Revolver | pedal-proven |
| 16 | 15 | Helicopter | pedal-proven |
| 17 | 16 | Custom Trem | pedal-proven |
| 18 | 64 | Acoustic Refiner | pedal-proven |
| 19 | 65 | AC Sim | pedal-proven |
| 20 | 66 | Toucher | pedal-proven |
| 21 | 67 | Crier | pedal-proven |
| 22 | 68 | Clean Octa | pedal-proven |
| 23 | 69 | Harmony | pedal-proven |
| 24 | 70 | Telephone Line | pedal-proven |
| 25 | 71 | Satisfaction | pedal-proven |
| 26 | 72 | Path Filter | pedal-proven |
| 27 | 73 | Bit Krusher | pedal-proven |
| 28 | 74 | Ring Mod | pedal-proven |
| 29 | 75 | Sweller | pedal-proven |
| 30 | 76 | Classic PS | pedal-proven |

Knobs for the FX3 models checked so far are in `docs/knobs.md`.

## Full effect list (from the manufacturer's model list)

A full list of the model names, in the manufacturer's order, with an ID per model (1 to 202). The ID is not the code the pedal stores, but for most blocks the code is the ID minus where that block's section starts. Rows say how each code was found: `pedal-proven` means it was set on a real pedal and read back from the record; In the CAB, EQ, DLY, RVB and FX3 tables every row has now been read from the record while stepping through the pedal's list, so all rows say `pedal-proven`. Do not rely on a code after a firmware change before you have read it back. This list names the models; it says nothing about the knobs, which are in `docs/knobs.md`.

### CAB models

The editor's CAB list, in screen order. The first 60 rows are the 60 cabs of the ID list (IDs 109 to 168) under their real names, in the same order. After them comes a block of cabs that start with "TJ", which the ID list does not have. All 70 codes were read from the record while stepping through the pedal's CAB list. Screens 1-50 are codes 0-49 (code = screen - 1), screens 51-60 are codes 112-121 and screens 61-70 are codes 144-153; the codes jump, so read them from the table, do not compute them. Earlier versions listed screens 51-70 as 50-69 by list order, which was wrong. The editor's list has 70 rows, which matches the count the pedal shows. The three "TJ 66 Alnico Sil" rows look identical on screen, probably because the names are cut short. Names are as shown, including the spelling "Orchestal". The ID list also has user IR slots (ID 169); where they sit in the editor's list is not known.

| Screen | Code | Name | Source |
| --- | --- | --- | --- |
| 1 | 0 | Super Zep 1x6 | pedal-proven |
| 2 | 1 | Tweed Chap 1x8 | pedal-proven |
| 3 | 2 | Black Lux 1x12 | pedal-proven |
| 4 | 3 | Black Vint 1x12 | pedal-proven |
| 5 | 4 | Glacian 1x12 | pedal-proven |
| 6 | 5 | Bad Kitty 1x12 | pedal-proven |
| 7 | 6 | Voxy 1x12 | pedal-proven |
| 8 | 7 | Tweed Lux 1x12 | pedal-proven |
| 9 | 8 | Ace 20 1x12 | pedal-proven |
| 10 | 9 | UK G12M 1x12 | pedal-proven |
| 11 | 10 | Voxy 2x12 | pedal-proven |
| 12 | 11 | Emperor 2x12 | pedal-proven |
| 13 | 12 | Jazz Twin 2x12 | pedal-proven |
| 14 | 13 | Black Twin 2x12 | pedal-proven |
| 15 | 14 | Tweed Super 2x10 | pedal-proven |
| 16 | 15 | Boutique 2x12 | pedal-proven |
| 17 | 16 | Baseman 2x12 | pedal-proven |
| 18 | 17 | Superb 2x12 | pedal-proven |
| 19 | 18 | Superstar 2x12 | pedal-proven |
| 20 | 19 | Twin Rock 2x12 | pedal-proven |
| 21 | 20 | Bluesky 2x12 | pedal-proven |
| 22 | 21 | Baseman 4x10 | pedal-proven |
| 23 | 22 | UK Lead 4x12 | pedal-proven |
| 24 | 23 | UK Trad 4x12 | pedal-proven |
| 25 | 24 | UK Modern 4x12 | pedal-proven |
| 26 | 25 | UK Green 4x12 | pedal-proven |
| 27 | 26 | Eddie 4x12 | pedal-proven |
| 28 | 27 | Rector 4x12 | pedal-proven |
| 29 | 28 | Boger 4x12 | pedal-proven |
| 30 | 29 | Engle 4x12 | pedal-proven |
| 31 | 30 | Urban 4x12 | pedal-proven |
| 32 | 31 | Soloist 4x12 | pedal-proven |
| 33 | 32 | Tang 4x12 | pedal-proven |
| 34 | 33 | Hiway 4x12 | pedal-proven |
| 35 | 34 | UK Black 4x12 | pedal-proven |
| 36 | 35 | The Way 4x12 | pedal-proven |
| 37 | 36 | Dizzle 4x12 | pedal-proven |
| 38 | 37 | Triple 4x12 | pedal-proven |
| 39 | 38 | UK T75 4x12 | pedal-proven |
| 40 | 39 | US King 4x12 | pedal-proven |
| 41 | 40 | Adam 1x15 | pedal-proven |
| 42 | 41 | Worker 1x15 | pedal-proven |
| 43 | 42 | Flip Top 1x15 | pedal-proven |
| 44 | 43 | US Bass 2x10 | pedal-proven |
| 45 | 44 | Mark 2x10 | pedal-proven |
| 46 | 45 | Adam 4x10 | pedal-proven |
| 47 | 46 | Ampage 4x10 | pedal-proven |
| 48 | 47 | Worker 4x10 | pedal-proven |
| 49 | 48 | Hacker 4x12 | pedal-proven |
| 50 | 49 | Ampage 8x10 | pedal-proven |
| 51 | 112 | Dreadnought 1 | pedal-proven |
| 52 | 113 | Dreadnought 2 | pedal-proven |
| 53 | 114 | Orchestal | pedal-proven |
| 54 | 115 | Jumbo | pedal-proven |
| 55 | 116 | Hum Bird | pedal-proven |
| 56 | 117 | Auditorium | pedal-proven |
| 57 | 118 | Classical | pedal-proven |
| 58 | 119 | Mandolin | pedal-proven |
| 59 | 120 | Fretless Bass | pedal-proven |
| 60 | 121 | Double Bass | pedal-proven |
| 61 | 144 | TJ 66 Alnico Sil | pedal-proven |
| 62 | 145 | TJ 66 Alnico Sil | pedal-proven |
| 63 | 146 | TJ 66 Alnico Sil | pedal-proven |
| 64 | 147 | TJ 69 G12M Green | pedal-proven |
| 65 | 148 | TJ 70 G12H Green | pedal-proven |
| 66 | 149 | TJ C12N e906 2 | pedal-proven |
| 67 | 150 | TJ C12N R121-SM5 | pedal-proven |
| 68 | 151 | TJ M75 e906 3 | pedal-proven |
| 69 | 152 | TJ M75 FAT-SM57 | pedal-proven |
| 70 | 153 | TJ M75 R121-SM54 | pedal-proven |

### EQ models

Rule: code = ID - 170. All 7 read from the record while stepping through the pedal's list. The editor's EQ list has the same 7 models in this order.

| ID | Code | Name | Source |
| --- | --- | --- | --- |
| 170 | 0 | Guitar EQ 1 | pedal-proven |
| 171 | 1 | Guitar EQ 2 | pedal-proven |
| 172 | 2 | Bass EQ 1 | pedal-proven |
| 173 | 3 | Bass EQ 2 | pedal-proven |
| 174 | 4 | Para EQ | pedal-proven |
| 175 | 5 | Graphic EQ | pedal-proven |
| 176 | 6 | V-EQ | pedal-proven |

### DLY models

Rule: code = ID - 177. All 17 read from the record while stepping through the pedal's list. The editor's list order matches the ID order and has one more model at the end (2290 Mod), so 17 models.

| ID | Code | Name | Source |
| --- | --- | --- | --- |
| 177 | 0 | Sweetie | pedal-proven |
| 178 | 1 | Recaller | pedal-proven |
| 179 | 2 | Pure Eko | pedal-proven |
| 180 | 3 | Analog Eko | pedal-proven |
| 181 | 4 | Mag Eko | pedal-proven |
| 182 | 5 | Tube Eko | pedal-proven |
| 183 | 6 | Backmask | pedal-proven |
| 184 | 7 | Ping Pong | pedal-proven |
| 185 | 8 | Multi Head | pedal-proven |
| 186 | 9 | Slapback | pedal-proven |
| 187 | 10 | Vintage Rack | pedal-proven |
| 188 | 11 | Sweep Eko | pedal-proven |
| 189 | 12 | Trem Eko | pedal-proven |
| 190 | 13 | Lofi Eko | pedal-proven |
| 191 | 14 | Ring Eko | pedal-proven |
| 192 | 15 | Ekoverb | pedal-proven |
| - | 16 | 2290 Mod | pedal-proven (in the editor, not in the ID list) |

### RVB models

Rule: code = ID - 193. All 11 read from the record while stepping through the pedal's list. The editor shows the same order with one more model at the end (Cloud), so 11 models. In the editor's list Oceandeep, Sweet Space and Shimmer follow Northstar.

| ID | Code | Name | Source |
| --- | --- | --- | --- |
| 193 | 0 | Room | pedal-proven |
| 194 | 1 | Hall | pedal-proven |
| 195 | 2 | Church | pedal-proven |
| 196 | 3 | Plate | pedal-proven |
| 197 | 4 | Spring | pedal-proven |
| 198 | 5 | Izumi | pedal-proven |
| 199 | 6 | Northstar | pedal-proven |
| 200 | 7 | Oceandeep | pedal-proven |
| 201 | 8 | Sweet Space | pedal-proven |
| 202 | 9 | Shimmer | pedal-proven |
| - | 10 | Cloud | pedal-proven (in the editor, not in the ID list) |

### NR models

Rule: code = ID - 107. Both checked. The editor's NR list has these 2 models.

| ID | Code | Name | Source |
| --- | --- | --- | --- |
| 107 | 0 | Smart Gate | pedal-proven |
| 108 | 1 | Fast Gate | pedal-proven |

### AMP models

The editor's AMP list has 60 models, in this screen order. All 60 were stepped through on the pedal and the record read at each stop: 57 codes were read directly in the first pass and the other three (screens 22, 28 and 36) were read in a second pass: codes 59, 65 and 102, exactly what the unbroken run predicted. The codes run in groups: screens 1-10 are 0-9, 11-21 are 48-58, 22-29 are 59-66, 30-47 are 96-113, 48-52 are 160-164 and 53-60 are 192-199. They do not follow the manufacturer's ID order, because the editor has eight amps the ID list lacks (Tweed Prince, Black Prince, Match 30 Clean and Sound Clone 6 to 10) and calls one Boger XT Blue M where the ID list says Red M. Sound Clone 6 to 10 (screens 56 to 60) produce no sound on the pedal; this was confirmed on a real pedal.

| Screen | Name | Code |
| --- | --- | --- |
| 1 | Tweed Lux | 0 |
| 2 | Baseman Norm | 1 |
| 3 | Black Twin | 2 |
| 4 | Voxy 30HW Norm | 3 |
| 5 | Jazz Clean | 4 |
| 6 | Emperor Clean | 5 |
| 7 | Superstar Clean | 6 |
| 8 | Glacian Clean | 7 |
| 9 | Tweed Prince | 8 |
| 10 | Black Prince | 9 |
| 11 | Baseman Bright | 48 |
| 12 | Voxy 30HW TB | 49 |
| 13 | Emperor Drive | 50 |
| 14 | Superstar Drive | 51 |
| 15 | Marshell 45 | 52 |
| 16 | Marshell 45+ | 53 |
| 17 | Marshell 45 Jump | 54 |
| 18 | Marshell 50 | 55 |
| 19 | Marshell 50+ | 56 |
| 20 | Marshell 50 Jump | 57 |
| 21 | Hot Kitty Drive | 58 |
| 22 | Messe IIC+ 1 | 59 |
| 23 | Messe IIC+ 2 | 60 |
| 24 | Messe IIC+ 3 | 61 |
| 25 | Soloist 100 Crunch | 62 |
| 26 | Marshell 800 | 63 |
| 27 | Fryman B1 | 64 |
| 28 | Fryman B2 | 65 |
| 29 | Glacian Drive | 66 |
| 30 | Marshell 900 | 96 |
| 31 | Dizzle VH B | 97 |
| 32 | Dizzle VH S | 98 |
| 33 | Engle Saga 1 | 99 |
| 34 | Engle Saga 2 | 100 |
| 35 | Fryman HB | 101 |
| 36 | Fryman HB+ | 102 |
| 37 | Eddie 51 | 103 |
| 38 | Soloist 100 Lead | 104 |
| 39 | Messe IV Lead 1 | 105 |
| 40 | Messe IV Lead 2 | 106 |
| 41 | Messe IV Lead 3 | 107 |
| 42 | Tangerine R100 | 108 |
| 43 | Rector Dual V | 109 |
| 44 | Rector Dual M | 110 |
| 45 | Dizzle VH+ B | 111 |
| 46 | Dizzle VH+ S | 112 |
| 47 | Boger XT Blue M | 113 |
| 48 | Alchemy Pre | 160 |
| 49 | Ampage Classic | 161 |
| 50 | Ampage Flip | 162 |
| 51 | Voxy Bass | 163 |
| 52 | Messe Bass 400 | 164 |
| 53 | Acoustic Preamp 1 | 192 |
| 54 | Acoustic Preamp 2 | 193 |
| 55 | Match 30 Clean | 194 |
| 56 | Sound Clone 6 | 195 (no sound on the pedal) |
| 57 | Sound Clone 7 | 196 (no sound on the pedal) |
| 58 | Sound Clone 8 | 197 (no sound on the pedal) |
| 59 | Sound Clone 9 | 198 (no sound on the pedal) |
| 60 | Sound Clone 10 | 199 (no sound on the pedal) |

### FX1, FX2 and FX3 models

These models share one list, but each block stores its own codes, and each shows only part of the list in its own order.

FX3 is in the table above (screens 1 to 30). Its screens 1 to 17 are IDs 38 to 54 in order (code = ID - 38), then IDs 9, 10, 11, 12, 17, 18, 20, 21, 16, 22, 23 and 24 as screens 18 to 29 (codes 64 to 75).

FX2 and FX1 are in their own tables (FX2 above, FX1 below). Both have 60 models.

| ID | Name | Group |
| --- | --- | --- |
| 1 | Comprosso | Dynamic |
| 2 | Squeezer | Dynamic |
| 3 | Affinity Boost | Boost |
| 4 | FET Boost | Boost |
| 5 | Enhancer | Boost |
| 6 | Gated Boost | Boost |
| 7 | Smart Gate | Gate |
| 8 | Fast Gate | Gate |
| 9 | Acoustic Refiner | Acoustic |
| 10 | AC Sim | Acoustic |
| 11 | Toucher | Filter |
| 12 | Crier | Filter |
| 13 | Voxy Wah | Wah |
| 14 | Cry Wah | Wah |
| 15 | Bass Press | Wah |
| 16 | Path Filter | Filter |
| 17 | Clean Octa | Octave/Pitch |
| 18 | Harmony | Octave/Pitch |
| 19 | Pitch Shift | Octave/Pitch |
| 20 | Telephone Line | Lo-Fi |
| 21 | Satisfaction | Saturation |
| 22 | Bit Krusher | Bit Crusher |
| 23 | Ring Mod | Ring Mod |
| 24 | Sweller | Swell |
| 25 | Green Drive | Overdrive |
| 26 | Super Drive | Overdrive |
| 27 | Screamood | Overdrive |
| 28 | Zen Garden | Overdrive |
| 29 | Big Pie | Fuzz/Dist |
| 30 | Face Fuzz | Fuzz/Dist |
| 31 | Bend Fuzz | Fuzz/Dist |
| 32 | Black Tail | Distortion |
| 33 | Smooth Dist | Distortion |
| 34 | Governor | Distortion |
| 35 | Crunchist | Distortion |
| 36 | Bass Crusher | Bass Drive |
| 37 | Solid Steel | Bass Drive |
| 38 | Aozora Chorus | Chorus |
| 39 | Grand Choruium | Chorus |
| 40 | Liquid C | Chorus |
| 41 | Choruium B | Chorus |
| 42 | Detune | Chorus |
| 43 | Jetter | Flanger |
| 44 | Jetter B | Flanger |
| 45 | Jetter N | Flanger |
| 46 | Trem Jet | Flanger/Trem |
| 47 | Pulser | Vibrato |
| 48 | Grand Vibrato | Vibrato |
| 49 | Shiver T | Vibrato |
| 50 | 90 Phaser | Phaser |
| 51 | Green Phaser | Phaser |
| 52 | Revolver | Uni-Vibe |
| 53 | Helicopter | Tremolo |
| 54 | Custom Trem | Tremolo |

## FX1 list (screen order)

The editor's FX1 list has 60 models, which matches the count the pedal shows. All 60 codes below come from stepping through the pedal's FX1 list and reading the record at each stop. 55 were read directly during the first pass. The other five (screens 3, 7, 11, 17 and 26) were stepped past too fast to catch, then read on the pedal in a second pass with the poller at 4 s: codes 2, 6, 35, 41 and 68, exactly what the unbroken run predicted. Screen 47 (90 Phaser, code 137) was proven earlier by setting it. The codes run in four groups: screens 1-7 are 0-6, 8-21 are 32-45, 22-37 are 64-79 and 38-60 are 128-150. FX1 codes are not the FX2 ones. Classic PS, Magic T, Blues Butter, Dr. Blues, Precise Attack and Sound Clone 1 to 5 are not in the manufacturer's ID list above.

| Screen | Name | Code |
| --- | --- | --- |
| 1 | Comprosso | 0 |
| 2 | Squeezer | 1 |
| 3 | Affinity Boost | 2 |
| 4 | FET Boost | 3 |
| 5 | Enhancer | 4 |
| 6 | Smart Gate | 5 |
| 7 | Fast Gate | 6 |
| 8 | AC Sim | 32 |
| 9 | Toucher | 33 |
| 10 | Crier | 34 |
| 11 | Voxy Wah | 35 |
| 12 | Cry Wah | 36 |
| 13 | Bass Press | 37 |
| 14 | Clean Octa | 38 |
| 15 | Harmony | 39 |
| 16 | Telephone Line | 40 |
| 17 | Satisfaction | 41 |
| 18 | Path Filter | 42 |
| 19 | Bit Krusher | 43 |
| 20 | Ring Mod | 44 |
| 21 | Classic PS | 45 |
| 22 | Green Drive | 64 |
| 23 | Super Drive | 65 |
| 24 | Screamood | 66 |
| 25 | Zen Garden | 67 |
| 26 | Big Pie | 68 |
| 27 | Face Fuzz | 69 |
| 28 | Bend Fuzz | 70 |
| 29 | Black Tail | 71 |
| 30 | Smooth Dist | 72 |
| 31 | Governor | 73 |
| 32 | Crunchist | 74 |
| 33 | Bass Crusher | 75 |
| 34 | Solid Steel | 76 |
| 35 | Magic T | 77 |
| 36 | Blues Butter | 78 |
| 37 | Dr. Blues | 79 |
| 38 | Aozora Chorus | 128 |
| 39 | Grand Choruium | 129 |
| 40 | Liquid C | 130 |
| 41 | Choruium B | 131 |
| 42 | Detune | 132 |
| 43 | Jetter | 133 |
| 44 | Jetter B | 134 |
| 45 | Pulser | 135 |
| 46 | Grand Vibrato | 136 |
| 47 | 90 Phaser | 137 |
| 48 | Green Phaser | 138 |
| 49 | Revolver | 139 |
| 50 | Helicopter | 140 |
| 51 | Custom Trem | 141 |
| 52 | Sweller | 142 |
| 53 | Gated Boost | 143 |
| 54 | Pitch Shift | 144 |
| 55 | Precise Attack | 145 |
| 56 | Sound Clone 1 | 146 |
| 57 | Sound Clone 2 | 147 |
| 58 | Sound Clone 3 | 148 |
| 59 | Sound Clone 4 | 149 |
| 60 | Sound Clone 5 | 150 |
