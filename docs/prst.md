# Hotone .prst files

`POST /api/import/prst` (and the Import button on the site) opens a `.prst` file and lists what is in it.
It does **not** load it onto the pedal. This page says why and what would change that.

## What is known

The outer container is documented by people who took apart the original Ampero and Ampero One files:

* [vguitarforums.com thread on the PRST format](https://www.vguitarforums.com/smf/index.php?topic=26671.0)
* [PatchOrganizer](https://github.com/ThibaultDucray/PatchOrganizer) (GPL, so its code is not used here; only the layout it describes)

A file is a 32 byte header starting `TSRP`, a table of (offset, size) pairs one per patch, one `MRAP`
block per patch with a 16 byte name at offset 12, and a 3 byte tail. Numbers are little endian. The
bridge reads exactly that and checks every offset stays inside the file. See `prst.py`.

## What is not known

How a Mini patch is stored inside the `MRAP` block. No `.prst` exported from a Mini editor was
available when this was written, and the original Ampero's body layout is a different device. The
bridge does not turn those bytes into settings by guessing, because a wrong guess writes a wrong
patch to a pedal. Files from this bridge (`/api/backup`) restore fine; they hold the Mini's own 460 byte
records (`docs/protocol.md`).

## How to close the gap

Export one patch from the Mini's editor as a `.prst`. On the pedal, select the same patch and read it with
`GET /api/patch/current`. Both describe the same settings, so comparing the `MRAP` body with `record_hex` shows
where each setting sits, the same way the record layout in `docs/protocol.md` was worked out. Once a file
and its record agree byte for byte, the importer can convert a `.prst` patch into a record and hand it
to the restore code, which already knows how to write and verify one.
