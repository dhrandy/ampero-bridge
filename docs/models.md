# Ampero Mini model codes

Code = what the pedal stores in the record and what `POST /api/model` sends. For the models checked live,
code = on-screen number minus 1 (FX2: Big Pi 05 -> 4, Black Tail 08 -> 7, Governor 10 -> 9; CAB: UK Black 4x12 35 -> 34;
DLY: Slapback 10 -> 9; RVB: Spring 05 -> 4). The FX2 codes below jump (0-15, 48-54, 80-93, 112-134), so the
screen-minus-1 rule is not a straight count for every slot: read the code from the record, do not compute it.

Which knob is which for each model is in `docs/knobs.md`.

Everything here is a snapshot of firmware V2.2. Hotone can add, rename or reorder models in an update, and the codes may move with them. Check a code with a read-back before relying on it after a firmware change.

## Proven live (set on the pedal, read back from the record)

| Slot | Screen | Name | Code |
| --- | --- | --- | --- |
| FX1 | 47 | 90 Phaser | 137 (params: Rate, Sync) |
| FX2 | 05 | Big Pi | 4 |
| FX2 | 08 | Black Tail | 7 |
| FX2 | 10 | Governor | 9 |
| FX2 | 01 | Green Drive (TS-808) | 0 (set from the bridge; not checked on the screen) |
| AMP | - | Marshell 50 (normal channel) | 55 |
| CAB | 35 | UK Black 4x12 | 34 |
| DLY | 10 | Slapback | 9 |
| RVB | 05 | Spring | 4 |

`POST /api/model` accepts only the codes in this table (per slot). Set `AMPERO_ALLOW_UNPROVEN_MODELS=1` to send others.

Writing a model from the bridge (`POST /api/model`) gave the same record as picking it on the pedal (checked for FX2).

FX1 has its own list. Its numbering is not FX2's: screen 47 is code 137, and FX1's default was code 76, which the FX2 list does not contain. Read FX1 codes from the record after picking the model on the pedal.

## FX2 code list (from a listen-only scroll, 60 models)

The order was confirmed end to end against screenshots of the editor's FX2 list (60 models). Names follow the editor's FX1 list order (see the FX1 list below): screens 1 to 16 are FX1 screens 22 to 37, 17 to 23 are FX1 1 to 7, 24 to 37 are FX1 8 to 21, and 38 to 60 are FX1 38 to 60. Codes and parameter counts come from a scroll of the pedal. Names are matched by that order and by parameter counts (for example screens 17 to 23 have 2, 7, 4, 4, 3, 1 and 2 parameters, as the manual gives Comprosso to Fast Gate). The code of each row is from the pedal scroll; only the rows in the proven table above were read back on the pedal, so treat the other codes as likely, not proven.

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

FX3 has its own list. It is not the FX2 list (Liquid C is code 114 in FX2, 2 in FX3). The Hotone manual gives the names in groups, in the order the pedal shows them: the modulation group first, then the special effects. Screen 03, 07, 17, 26, 27 and 29 were checked on a real pedal. Codes are screen minus 1 for screens 1 to 17 and screen plus 46 for 18 onwards, which fits all the codes read so far (2, 6, 16, 72, 73, 75). Only the rows marked "pedal-read" had their code read back; the other rows come from the pattern and are not proven. The list has 30 models; the order was checked against screenshots of the editor's FX3 list, which ends at Classic PS. Screen 30 is the only row whose code was not read. `/api/model` still only accepts the codes in the proven table above.

| Screen | Code | Name | Source |
| --- | --- | --- | --- |
| 01 | 0 | Aozora Chorus | manual order, code from the pattern |
| 02 | 1 | Grand Choruium | manual order, code from the pattern |
| 03 | 2 | Liquid C | pedal-read (screen and code) |
| 04 | 3 | Choruium B | manual order, code from the pattern |
| 05 | 4 | Detune | name seen on screen, code from the pattern |
| 06 | 5 | Jetter | manual order, code from the pattern |
| 07 | 6 | Jetter B | pedal-read (screen and code) |
| 08 | 7 | Jetter N | manual order, code from the pattern |
| 09 | 8 | Trem Jet | manual order, code from the pattern |
| 10 | 9 | Pulser | manual order, code from the pattern |
| 11 | 10 | Grand Vibrato | manual order, code from the pattern |
| 12 | 11 | Shiver T | manual order, code from the pattern |
| 13 | 12 | 90 Phaser | manual order, code from the pattern |
| 14 | 13 | Green Phaser | manual order, code from the pattern |
| 15 | 14 | Revolver | manual order, code from the pattern |
| 16 | 15 | Helicopter | manual order, code from the pattern |
| 17 | 16 | Custom Trem | pedal-read (screen and code) |
| 18 | 64 | Acoustic Refiner | manual order, code from the pattern |
| 19 | 65 | AC Sim | manual order, code from the pattern |
| 20 | 66 | Toucher | manual order, code from the pattern |
| 21 | 67 | Crier | manual order, code from the pattern |
| 22 | 68 | Clean Octa | manual order, code from the pattern |
| 23 | 69 | Harmony | manual order, code from the pattern |
| 24 | 70 | Telephone Line | manual order, code from the pattern |
| 25 | 71 | Satisfaction | manual order, code from the pattern |
| 26 | 72 | Path Filter | pedal-read (screen and code) |
| 27 | 73 | Bit Krusher | pedal-read (screen and code) |
| 28 | 74 | Ring Mod | manual order, code from the pattern |
| 29 | 75 | Sweller | pedal-read (screen and code) |
| 30 | 76 | Classic PS | name from the editor list, code from the pattern (not read) |

Knobs for the FX3 models checked so far are in `docs/knobs.md`.

## Full effect list (from the manufacturer's model list)

A full list of the model names, in the manufacturer's order, with an ID per model (1 to 202). The ID is not the code the pedal stores, but for most blocks the code is the ID minus where that block's section starts. Rows say how each code was found: `pedal-proven` means it was set on a real pedal and read back from the record; `list order, not checked` means it follows from the rule and the list order only. Do not rely on an unchecked code before you have read it back. This list names the models; it says nothing about the knobs, which are in `docs/knobs.md`.

### CAB models

The editor's CAB list, in screen order, read off screenshots. The manufacturer's ID list only has generic names for cabs (Guitar Cab 1x12 and so on), so the names here are the editor's. The first 60 rows are the 60 cabs of the ID list (IDs 109 to 168) under their real names, in the same order. After them comes a block of cabs that start with "TJ", which the ID list does not have. Rule: code = screen - 1. Checked at UK Black 4x12 (screen 35, code 34). The editor's list has 70 rows, which matches the count the pedal shows. The three "TJ 66 Alnico Sil" rows look identical on screen, probably because the names are cut short. Names are as shown, including the spelling "Orchestal". The ID list also has user IR slots (ID 169); where they sit in the editor's list is not known.

| Screen | Code | Name | Source |
| --- | --- | --- | --- |
| 1 | 0 | Super Zep 1x6 | list order, not checked |
| 2 | 1 | Tweed Chap 1x8 | list order, not checked |
| 3 | 2 | Black Lux 1x12 | list order, not checked |
| 4 | 3 | Black Vint 1x12 | list order, not checked |
| 5 | 4 | Glacian 1x12 | list order, not checked |
| 6 | 5 | Bad Kitty 1x12 | list order, not checked |
| 7 | 6 | Voxy 1x12 | list order, not checked |
| 8 | 7 | Tweed Lux 1x12 | list order, not checked |
| 9 | 8 | Ace 20 1x12 | list order, not checked |
| 10 | 9 | UK G12M 1x12 | list order, not checked |
| 11 | 10 | Voxy 2x12 | list order, not checked |
| 12 | 11 | Emperor 2x12 | list order, not checked |
| 13 | 12 | Jazz Twin 2x12 | list order, not checked |
| 14 | 13 | Black Twin 2x12 | list order, not checked |
| 15 | 14 | Tweed Super 2x10 | list order, not checked |
| 16 | 15 | Boutique 2x12 | list order, not checked |
| 17 | 16 | Baseman 2x12 | list order, not checked |
| 18 | 17 | Superb 2x12 | list order, not checked |
| 19 | 18 | Superstar 2x12 | list order, not checked |
| 20 | 19 | Twin Rock 2x12 | list order, not checked |
| 21 | 20 | Bluesky 2x12 | list order, not checked |
| 22 | 21 | Baseman 4x10 | list order, not checked |
| 23 | 22 | UK Lead 4x12 | list order, not checked |
| 24 | 23 | UK Trad 4x12 | list order, not checked |
| 25 | 24 | UK Modern 4x12 | list order, not checked |
| 26 | 25 | UK Green 4x12 | list order, not checked |
| 27 | 26 | Eddie 4x12 | list order, not checked |
| 28 | 27 | Rector 4x12 | list order, not checked |
| 29 | 28 | Boger 4x12 | list order, not checked |
| 30 | 29 | Engle 4x12 | list order, not checked |
| 31 | 30 | Urban 4x12 | list order, not checked |
| 32 | 31 | Soloist 4x12 | list order, not checked |
| 33 | 32 | Tang 4x12 | list order, not checked |
| 34 | 33 | Hiway 4x12 | list order, not checked |
| 35 | 34 | UK Black 4x12 | pedal-proven |
| 36 | 35 | The Way 4x12 | list order, not checked |
| 37 | 36 | Dizzle 4x12 | list order, not checked |
| 38 | 37 | Triple 4x12 | list order, not checked |
| 39 | 38 | UK T75 4x12 | list order, not checked |
| 40 | 39 | US King 4x12 | list order, not checked |
| 41 | 40 | Adam 1x15 | list order, not checked |
| 42 | 41 | Worker 1x15 | list order, not checked |
| 43 | 42 | Flip Top 1x15 | list order, not checked |
| 44 | 43 | US Bass 2x10 | list order, not checked |
| 45 | 44 | Mark 2x10 | list order, not checked |
| 46 | 45 | Adam 4x10 | list order, not checked |
| 47 | 46 | Ampage 4x10 | list order, not checked |
| 48 | 47 | Worker 4x10 | list order, not checked |
| 49 | 48 | Hacker 4x12 | list order, not checked |
| 50 | 49 | Ampage 8x10 | list order, not checked |
| 51 | 50 | Dreadnought 1 | list order, not checked |
| 52 | 51 | Dreadnought 2 | list order, not checked |
| 53 | 52 | Orchestal | list order, not checked |
| 54 | 53 | Jumbo | list order, not checked |
| 55 | 54 | Hum Bird | list order, not checked |
| 56 | 55 | Auditorium | list order, not checked |
| 57 | 56 | Classical | list order, not checked |
| 58 | 57 | Mandolin | list order, not checked |
| 59 | 58 | Fretless Bass | list order, not checked |
| 60 | 59 | Double Bass | list order, not checked |
| 61 | 60 | TJ 66 Alnico Sil | list order, not checked |
| 62 | 61 | TJ 66 Alnico Sil | list order, not checked |
| 63 | 62 | TJ 66 Alnico Sil | list order, not checked |
| 64 | 63 | TJ 69 G12M Green | list order, not checked |
| 65 | 64 | TJ 70 G12H Green | list order, not checked |
| 66 | 65 | TJ C12N e906 2 | list order, not checked |
| 67 | 66 | TJ C12N R121-SM5 | list order, not checked |
| 68 | 67 | TJ M75 e906 3 | list order, not checked |
| 69 | 68 | TJ M75 FAT-SM57 | list order, not checked |
| 70 | 69 | TJ M75 R121-SM54 | list order, not checked |

### EQ models

Rule: code = ID - 170. Checked at Guitar EQ 1 (code 0). The editor's EQ list has the same 7 models in this order.

| ID | Code | Name | Source |
| --- | --- | --- | --- |
| 170 | 0 | Guitar EQ 1 | pedal-proven |
| 171 | 1 | Guitar EQ 2 | list order, not checked |
| 172 | 2 | Bass EQ 1 | list order, not checked |
| 173 | 3 | Bass EQ 2 | list order, not checked |
| 174 | 4 | Para EQ | list order, not checked |
| 175 | 5 | Graphic EQ | list order, not checked |
| 176 | 6 | V-EQ | list order, not checked |

### DLY models

Rule: code = ID - 177. Checked at Slapback (ID 186, code 9). The editor's list order matches the ID order and has one more model at the end (2290 Mod), so 17 models.

| ID | Code | Name | Source |
| --- | --- | --- | --- |
| 177 | 0 | Sweetie | list order, not checked |
| 178 | 1 | Recaller | list order, not checked |
| 179 | 2 | Pure Eko | list order, not checked |
| 180 | 3 | Analog Eko | list order, not checked |
| 181 | 4 | Mag Eko | list order, not checked |
| 182 | 5 | Tube Eko | list order, not checked |
| 183 | 6 | Backmask | list order, not checked |
| 184 | 7 | Ping Pong | list order, not checked |
| 185 | 8 | Multi Head | list order, not checked |
| 186 | 9 | Slapback | pedal-proven |
| 187 | 10 | Vintage Rack | list order, not checked |
| 188 | 11 | Sweep Eko | list order, not checked |
| 189 | 12 | Trem Eko | list order, not checked |
| 190 | 13 | Lofi Eko | list order, not checked |
| 191 | 14 | Ring Eko | list order, not checked |
| 192 | 15 | Ekoverb | list order, not checked |
| - | 16 | 2290 Mod | in the editor, not in the ID list; code from the pattern, not checked |

### RVB models

Rule: code = ID - 193. Checked at Spring (ID 197, code 4). The editor shows the same order with one more model at the end (Cloud), so 11 models. In the editor's list Oceandeep, Sweet Space and Shimmer follow Northstar.

| ID | Code | Name | Source |
| --- | --- | --- | --- |
| 193 | 0 | Room | list order, not checked |
| 194 | 1 | Hall | list order, not checked |
| 195 | 2 | Church | list order, not checked |
| 196 | 3 | Plate | list order, not checked |
| 197 | 4 | Spring | pedal-proven |
| 198 | 5 | Izumi | list order, not checked |
| 199 | 6 | Northstar | list order, not checked |
| 200 | 7 | Oceandeep | list order, not checked |
| 201 | 8 | Sweet Space | list order, not checked |
| 202 | 9 | Shimmer | list order, not checked |
| - | 10 | Cloud | in the editor, not in the ID list; code from the pattern, not checked |

### NR models

Rule: code = ID - 107. Both checked. The editor's NR list has these 2 models.

| ID | Code | Name | Source |
| --- | --- | --- | --- |
| 107 | 0 | Smart Gate | pedal-proven |
| 108 | 1 | Fast Gate | pedal-proven |

### AMP models

The editor's AMP list has 60 models, in this screen order (checked against screenshots, read straight through). Only one code is known: Marshell 50 (screen 18) reads as code 55. The codes for the other amps are not known, and they do not follow the manufacturer's ID order, because the editor has eight amps the ID list lacks (Tweed Prince, Black Prince, Match 30 Clean and Sound Clone 6 to 10) and calls one Boger XT Blue M where the ID list says Red M. If the codes run in screen order from some start, screen 1 would be code 38; that is a guess from a single point and needs reads at screen 1 and screen 60 before it is used.

| Screen | Name | Code |
| --- | --- | --- |
| 1 | Tweed Lux | not read |
| 2 | Baseman Norm | not read |
| 3 | Black Twin | not read |
| 4 | Voxy 30HW Norm | not read |
| 5 | Jazz Clean | not read |
| 6 | Emperor Clean | not read |
| 7 | Superstar Clean | not read |
| 8 | Glacian Clean | not read |
| 9 | Tweed Prince | not read |
| 10 | Black Prince | not read |
| 11 | Baseman Bright | not read |
| 12 | Voxy 30HW TB | not read |
| 13 | Emperor Drive | not read |
| 14 | Superstar Drive | not read |
| 15 | Marshell 45 | not read |
| 16 | Marshell 45+ | not read |
| 17 | Marshell 45 Jump | not read |
| 18 | Marshell 50 | 55 (pedal-proven) |
| 19 | Marshell 50+ | not read |
| 20 | Marshell 50 Jump | not read |
| 21 | Hot Kitty Drive | not read |
| 22 | Messe IIC+ 1 | not read |
| 23 | Messe IIC+ 2 | not read |
| 24 | Messe IIC+ 3 | not read |
| 25 | Soloist 100 Crunch | not read |
| 26 | Marshell 800 | not read |
| 27 | Fryman B1 | not read |
| 28 | Fryman B2 | not read |
| 29 | Glacian Drive | not read |
| 30 | Marshell 900 | not read |
| 31 | Dizzle VH B | not read |
| 32 | Dizzle VH S | not read |
| 33 | Engle Saga 1 | not read |
| 34 | Engle Saga 2 | not read |
| 35 | Fryman HB | not read |
| 36 | Fryman HB+ | not read |
| 37 | Eddie 51 | not read |
| 38 | Soloist 100 Lead | not read |
| 39 | Messe IV Lead 1 | not read |
| 40 | Messe IV Lead 2 | not read |
| 41 | Messe IV Lead 3 | not read |
| 42 | Tangerine R100 | not read |
| 43 | Rector Dual V | not read |
| 44 | Rector Dual M | not read |
| 45 | Dizzle VH+ B | not read |
| 46 | Dizzle VH+ S | not read |
| 47 | Boger XT Blue M | not read |
| 48 | Alchemy Pre | not read |
| 49 | Ampage Classic | not read |
| 50 | Ampage Flip | not read |
| 51 | Voxy Bass | not read |
| 52 | Messe Bass 400 | not read |
| 53 | Acoustic Preamp 1 | not read |
| 54 | Acoustic Preamp 2 | not read |
| 55 | Match 30 Clean | not read |
| 56 | Sound Clone 6 | not read |
| 57 | Sound Clone 7 | not read |
| 58 | Sound Clone 8 | not read |
| 59 | Sound Clone 9 | not read |
| 60 | Sound Clone 10 | not read |

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

From the editor software's list, read off screenshots; 60 models, which matches the count the pedal shows. The codes are not known yet except for one: 90 Phaser (screen 47) reads as code 137. FX1 codes are not the FX2 ones. Classic PS, Magic T, Blues Butter, Dr. Blues, Precise Attack and Sound Clone 1 to 5 are not in the manufacturer's ID list above.

| Screen | Name |
| --- | --- |
| 1 | Comprosso |
| 2 | Squeezer |
| 3 | Affinity Boost |
| 4 | FET Boost |
| 5 | Enhancer |
| 6 | Smart Gate |
| 7 | Fast Gate |
| 8 | AC Sim |
| 9 | Toucher |
| 10 | Crier |
| 11 | Voxy Wah |
| 12 | Cry Wah |
| 13 | Bass Press |
| 14 | Clean Octa |
| 15 | Harmony |
| 16 | Telephone Line |
| 17 | Satisfaction |
| 18 | Path Filter |
| 19 | Bit Krusher |
| 20 | Ring Mod |
| 21 | Classic PS |
| 22 | Green Drive |
| 23 | Super Drive |
| 24 | Screamood |
| 25 | Zen Garden |
| 26 | Big Pie |
| 27 | Face Fuzz |
| 28 | Bend Fuzz |
| 29 | Black Tail |
| 30 | Smooth Dist |
| 31 | Governor |
| 32 | Crunchist |
| 33 | Bass Crusher |
| 34 | Solid Steel |
| 35 | Magic T |
| 36 | Blues Butter |
| 37 | Dr. Blues |
| 38 | Aozora Chorus |
| 39 | Grand Choruium |
| 40 | Liquid C |
| 41 | Choruium B |
| 42 | Detune |
| 43 | Jetter |
| 44 | Jetter B |
| 45 | Pulser |
| 46 | Grand Vibrato |
| 47 | 90 Phaser |
| 48 | Green Phaser |
| 49 | Revolver |
| 50 | Helicopter |
| 51 | Custom Trem |
| 52 | Sweller |
| 53 | Gated Boost |
| 54 | Pitch Shift |
| 55 | Precise Attack |
| 56 | Sound Clone 1 |
| 57 | Sound Clone 2 |
| 58 | Sound Clone 3 |
| 59 | Sound Clone 4 |
| 60 | Sound Clone 5 |
