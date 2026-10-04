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

| What | Body |
| --- | --- |
| model select | `10 AA 00 01 HH LL` (HH LL = model code, 14-bit as two 7-bit bytes) |
| parameter set | `10 AA 00 02 HH LL SS HI LO` (SS = param number in the manual's order, HI LO = value; only 0-127 seen) |
| save, frame A | `00 02 06 07 01 <idx>` |
| save, frame B | `10 00 00 00 01 <idx> <name, 18 bytes, NUL padded>` |

Slot AA: 01 FX1, 02 FX2, 03 AMP, 05 CAB, 06 EQ, 08 DLY, 09 probably RVB
(04 and 07 are probably NR and FX3, never seen).

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
CC 22-25 (arrow buttons) and CC 72 (Tuner, probably). Those are untested here.
CC 77 (lock) and 78 (all effects off) follow Hotone's Ampero II Stage list and
are not isolated on the Mini.

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

### Record layout found on the real pedal (P26-1, tested live)

Byte offsets in the 460-byte record, confirmed by changing one thing and diffing:

| What | Offset | Values |
| --- | --- | --- |
| FX1 block state | 95 | 01 on, 00 off |
| FX2 block state | 128 | 01 on |
| FX2 model code | 130 | on-screen model number minus 1 (05 Big Pi = 04, 08 Black Tail = 07, 10 Governor = 09) |
| EQ block state | 260 | 01 on, 00 off |
| RVB block state | 359 | 01 on, 00 off |
| last byte | 459 | checksum, changes with every edit; the pedal recomputes it |

When the FX2 model changes, eight copies of the model code at offsets 41, 48, 55, 62,
69, 76, 83 and 90 change with it, and FX2's parameters reset to the new model's
defaults. A host `POST /api/model` (`10 02 00 01 00 NN`, NN = number minus 1) gave a
record identical to picking the model on the pedal. The pedal sends no reply to the
write, so read the record back to check it.

### Order of a preset write

1. Select the patch (Program Change) and wait about 300 ms.
2. Set every block on or off. Turn off whatever the preset does not use.
3. Set models and parameters.
4. Read the record back and check each change.
5. Save, last. Never save before the checks pass.
