# Ampero Mini protocol notes

All of this was captured from a real Mini (USB 84ef:0080, interface 3) on Oct 3,
2026 and checked against its screen, unless marked unproven.

## Transport

USB-MIDI 1.0 on interface 3: bulk OUT 0x03 (maxpacket 256), bulk IN 0x83
(maxpacket 64), one cable. Packets are 4 bytes: cable/CIN, then 3 data bytes.

* SysEx: CIN 4 for a non-final 3-byte chunk, 5/6/7 for the final 1/2/3 bytes.
* Program Change: `0C C0 PP 00`. Control Change: `0B B0 CC VV`.
* The pedal does not answer a standard Identity Request.
* It broadcasts SysEx on its own when you use it (heartbeat `00 02 06 05 ...`,
  counter `00 02 06 04 01 NN`, parameter changes `10 AA 00 02 ...`).

## SysEx frame

    F0 21 25 7F 4D 50 2D 32 <kind> <body> F7

kind `12` = data, `11` = query. No checksum. Body bytes are 7-bit.
This is not the Ampero II Stage / Stomp header (`21 25 4D 50 00 00 <ck>`), so
frames from those projects do not apply.

## Writes

A param write whose model code does not match the model the slot currently holds is ignored by the pedal (the call returns 200 and no byte changes). Set the model first and read it back.

| What | Body |
| --- | --- |
| model select | `10 AA 00 01 HH LL` (HH LL = model code, 14-bit as two 7-bit bytes) |
| parameter set | `10 AA 00 02 HH LL SS HI LO` (SS = param number in the manual's order, HI LO = value; only 0-127 seen) |
| save, frame A | `00 02 06 07 01 <idx>` |
| save, frame B | `10 00 00 00 01 <idx> <name, 18 bytes, NUL padded>` |

Slot AA: 01 FX1, 02 FX2, 03 AMP, 04 NR, 05 CAB, 06 EQ, 07 FX3, 08 DLY, 09 probably RVB
(Param writes to 04 and 07 were written and read back on the pedal. Model select on those two slots has not been tried on a pedal yet; their codes were read from the record by stepping through the lists.)

EQ slot (06) model codes: 0 Guitar EQ1, 1 Guitar EQ2, 2 Bass EQ1, 3 Bass EQ2,
4 Para EQ (15 params), 5 Graphic EQ (11), 6 V-EQ (5).

**Save works from the host.** The editor sends A and B in the same millisecond.
Sending both in one USB transfer (72 bytes) with the name TEST to index 75 made
the pedal show TEST on P26-1 after hopping patches (Oct 3, 2026, 9:11 PM EDT).
The pedal sends nothing back for a host save, so only its screen confirms it. A
save made on the pedal itself does broadcast
`10 00 00 00 01 <idx> <name>` then `00 02 06 07 01 <idx+1>`,
`00 02 06 05 00 00 00 78`, `00 02 06 04 01 <idx+1>`.
Earlier tries that sent B alone, or A and B one second apart, were not
distinguishable (they used the name already on the slot), so use the one-transfer
form. It saves the pedal's current edit buffer under that name.

**Never write** `10 06 00 00 00` (the enable-state marker the pedal broadcasts):
a host write of it crashed the pedal ("OFFON <= 1"). Use CC for block on/off.

## Plain MIDI (channel 1)

Block on/off, value 0 = off, 127 = on: 48 FX1, 49 FX2, 50 AMP, 51 NR, 52 CAB,
53 EQ, 54 FX3, 55 DLY, 56 RVB. 57 = back to the main screen, 58 = back (both are
navigation, not toggles). Program Change selects a patch, 0 based: PC 75 is P26-1.

Cross-check: the TouchOSC-Hotone-Ampero-template repo (no license, model not
stated) uses 48/49/53/54/55 for FX1/FX2/EQ/FX3/DLY, same as above, plus
CC 22-25 (arrow buttons) and CC 72 (Tuner, probably). CC 22-25 are patch navigation,
proven on a real Mini by reading `/api/history` after one poke each (edit buffer only,
nothing saved): CC 22 = bank down (3 patches back), CC 23 = bank up (3 forward),
CC 24 = patch down (1 back), CC 25 = patch up (1 forward). They do not scroll the model
list, so they cannot walk models. CC 72 is untested here.
CC 77 (lock) and 78 (all effects off) follow Hotone's Ampero II Stage list and
are not isolated on the Mini.

### CC sweep results (Mini, firmware V2.2)

Found by sending one CC at a time (value 127, or the value noted) through `POST /api/midi/cc`
and reading `/api/history` about 11 seconds later. Edit buffer only, nothing saved. Changes
revert when the patch is reloaded (patch down then up).

| CC | What it does |
| --- | --- |
| 7 | patch level, record byte 3, 0-99 (127 clamps to 99) |
| 8 | record byte 430, 0xff -> 0x7f. Meaning unknown |
| 11 | FX1 param 0 (record byte 99, 0-100) |
| 16 | AMP param 0 (record byte 165, 0-100) |
| 18 | DLY param 0 (record byte 330, 0-100) |
| 22 / 23 | bank down / bank up (3 patches) |
| 24 / 25 | patch down / patch up (1 patch) |
| 48-56 | block power, see above |
| 57 / 58 | back |
| 72 and 85 | FX1 on/off (127 on, 0 off) |
| 73 | bit 7 of record byte 395 (127 sets, 0 clears). Meaning unknown |
| 74 | low 7 bits of record byte 395 (0-127, 0x78 by default). Meaning unknown |
| 75 | sets record byte 408 to 1. Value 0 and a second 127 do not clear it. Meaning unknown |

No change in the record: CC 1-5, 9, 10, 12-15, 17, 19-21, 26-47, 59-71, 76-84, 86-119.
Not tried: 0, 6, 98-101, 120-127, and 77/78 (lock and all-effects-off, see above).
No CC steps a model list, and none found for the tuner or tap tempo. Model changes need the
sysex model select.

## Reading a patch

**The read returns the patch the pedal has selected.** On the real pedal, reads for
indexes 0, 1, 74 and 76 all answered with patch 75 (the selected one). The index in
the frames does not choose the patch. To read another patch, select it first
(Program Change), then read. The bridge refuses to label a read with an index the
pedal did not answer with.

What the editor does to "load" patch `<idx>` (all kind 12 except where noted):

    11  00 02 0a 00 00 00
    12  00 02 13 00 01 <idx> 01
    12  00 02 15 00 01 <idx> 00 <n> 01        n = 0..4
    11  00 00 05 01

The pedal answers with `00 02 12 ...` (header), five `00 02 14 00 01 <idx> 00 <n> <data>`
chunks and `00 02 16 00 01 <idx> 00 05` (trailer). The chunk data is nibble split
(two 4-bit values per byte). Joined and decoded, the record is 460 bytes:

    01 <idx> 00 3C <name, 18 bytes> ...

Only the index and the name are decoded. Models, parameters and block states are
in the rest of the record and are returned raw (`record_hex`).

### Record layout (460 bytes), tested live on P26-1

Name at offset 4 (18 bytes). Then nine block records, 33 bytes apart, in slot order. Each is
`<state> <model hi> <model lo> <unused> <param 0 lo> <param 0 hi> <param 1 lo> <param 1 hi> ...` with
state 01 = on, 00 = off, model = hi * 128 + lo, and param i value at `state offset + 4 + 2 * i`.

| Slot | State offset | Block |
| --- | --- | --- |
| 01 | 95 | FX1 |
| 02 | 128 | FX2 |
| 03 | 161 | AMP |
| 04 | 194 | NR |
| 05 | 227 | CAB |
| 06 | 260 | EQ |
| 07 | 293 | FX3 |
| 08 | 326 | DLY |
| 09 | 359 | RVB |

The last byte (459) is a checksum. The pedal recomputes it when you change anything, so do not write it.
When a model changes, the pedal resets that block's params to the model's defaults and updates copies
of the model code elsewhere in the record (FX2: offsets 41 to 90; AMP: 401 to 407). Those copies are
read-only state, not something to write.

Proven codes are in `docs/models.md`.

### Param write

`10 <slot> 00 02 <model hi> <model lo> <param> <value hi> <value lo>` is the editor's frame.
Through the bridge, `POST /api/param {slot, model_code, param, value}` (value 0-127) was checked on the
real pedal: FX2 Governor, Marshell 50, Slapback and Spring params all read back exactly. The model code in
the frame must be the one the block holds now. Slapback's time is 14 bits (130 ms was its default), so
values above 127 would need a wider write that the bridge does not send yet.

### Order of a preset write

1. Select the patch (Program Change) and wait about 300 ms.
2. Set every block on or off. Turn off whatever the preset does not use.
3. Set models, then params (a model change resets its params).
4. Read the record back and check every change.
5. Save, last. Never save before the checks pass. A save stores whatever is in the edit buffer.

### Example: "TREATY OAK" on P26-1

FX1, EQ, FX3 off. FX2 Governor (gain 35, volume 55, bass 50, mid 60, treble 55). AMP Marshell 50
(volume 55, presence 50, master 55, bass 45, mid 60, treble 55). CAB UK Black 4x12 (defaults).
DLY Slapback (mix 25, feedback 15, time 110). RVB Spring (mix 20, decay 35, tone 55). Every byte
read back as written, then one save.
