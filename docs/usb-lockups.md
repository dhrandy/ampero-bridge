# Why the bridge used to lock up, and what stops it now

The original bridge held an ALSA MIDI port open. On Oct 3, 2026 that took the
whole Dell with it: the bridge process sat in D-state, `docker stop` hung behind
it, and only a reboot cleared it. This page records what is known, what is
reasoned, and what the rewrite does about it.

## What happened (verified on the box)

* Kernel 6.1 on the Dell. The stuck task was in `snd_use_lock_sync_helper`
  (sound/core/seq/seq_lock.c). That function loops until a sequencer client's
  use count drops to zero. If a write to the Mini never completes, the count
  never drops, and anything that needs the client to go away (closing the
  port, unplugging the device, the USB hub worker) waits forever.
  Source: https://raw.githubusercontent.com/torvalds/linux/v6.1/sound/core/seq/seq_lock.c
* A D-state task cannot be killed. No signal, no `docker kill`. This is a
  kernel wait, not an application bug, so application code can only avoid
  getting there.
* dmesg on the Mini shows `interface 3 ... bulk endpoint 0x83 has invalid
  maxpacket 64` and `endpoint 0x3 ... maxpacket 256`. The Mini's USB descriptors
  are a little off, which is the kind of thing that makes the stock snd-usb-audio
  MIDI path stall.

## Known causes of a wedged USB-MIDI container

1. **A held kernel MIDI client (ALSA sequencer or rawmidi) across the pedal's
   lifetime.** Blocking reads and writes on it have no timeout and the close path
   waits for them. This was ours. Fix: do not use ALSA at all.
2. **`--device /dev/bus/usb/BBB/DDD` pins one device node.** After a replug or a
   power cycle the pedal comes back as a new device number, and the container
   keeps pointing at the old node. Every open fails (ENODEV) until the container
   is recreated. See https://github.com/moby/moby/issues/35359 and
   https://github.com/moby/moby/issues/19763 (new nodes are not visible in the
   container with `--device`).
3. **Blocking transfers with no timeout.** A libusb or rawmidi read with
   timeout 0 never returns if the device goes quiet.
4. **A process that never exits when its device is gone.** With no healthcheck
   and no watchdog, the container stays "Up" while serving errors forever.
5. **A kernel driver fighting the process for the interface.** `snd-usb-audio`
   owns the interface until it is detached.

## What this repo does

| Cause | Mitigation |
| --- | --- |
| 1. kernel MIDI client | No `/dev/snd`, no ALSA, no rtmidi. Only libusb (`usbmidi.py`). The container cannot open an ALSA port, so it cannot hit this path. |
| 2. stale device node | Compose bind-mounts the whole `/dev/bus/usb` directory, not one node, and allows char major 189 with `device_cgroup_rules` (https://github.com/moby/moby/pull/22563, https://binary-manu.github.io/binary-is-better/docker/access-usb-devices-from-unprivileged-docker-containers). Every lookup starts a fresh libusb context. libusb caches its device list and only hotplug events refresh it, which a container never receives, so a long-lived context goes stale after a replug. A fresh one rescans the bus, so a new device number is found with no restart. |
| 3. blocking transfers | Every read and write has a timeout (`AMPERO_USB_TIMEOUT_MS`, 1 s). A whole request has a deadline. No transfer waits without a limit. |
| 4. stuck forever | `usbmidi.Link` runs a watchdog thread. If a request is still running after `AMPERO_HARD_DEADLINE_S` (20 s), it logs and exits the process with code 70. `restart: unless-stopped` starts a fresh one. `/health` is also a Docker healthcheck. |
| 5. driver conflict | The interface is detached from the kernel, claimed, used, released. snd-usb-audio is left detached by default (re-binding on every request would churn the ALSA MIDI device). `AMPERO_USB_REATTACH=1` hands it back. |

Also: requests are serialized. A caller that cannot get the pedal within 3 s
gets HTTP 503 `PedalBusy`, so a slow request does not pile up threads. A client
that stalls is dropped after 10 s. Unplugged pedal is HTTP 503 immediately.

Writes are also paced (v2.7.2). On Oct 4, 2026 a Mini stopped on a firmware assert
("Record the error and restart", `ParaNum <= GetParaNum(Paratype, Effect)`, audio.c line 2269)
during an evening of heavy use. The cause was not proven and the bridge's
own writes were not shown to be the trigger, but a pedal that is given time between writes is
the safer bet. All writes (`/api/midi/cc`, `/api/patch/select`, `/api/block`,
`/api/model`, `/api/param`, `/api/patch/save`) go out one at a time with `AMPERO_WRITE_GAP_S`
(0.5 s) between them. A save waits `AMPERO_WRITE_SAVE_GAP_S` (3 s) after the last write, and
the next write waits that long after the save. If more than `AMPERO_WRITE_QUEUE_MAX` (30)
writes are in line, the extra ones get HTTP 429 with `Retry-After` and nothing is sent.
Health, history and refused requests are not delayed. A read that touches the
pedal (`/api/patch/current`, the history poller) does not join the line and does not count
toward the 429 limit, but since v2.7.4 it waits until no write is on the wire and the quiet
time after the last write is over (3 s after a save), so nothing reaches the pedal inside
that window. The USB lock alone did not do this: it keeps two requests from overlapping but
lets the next one start the moment the last one ends. A read right behind a save or write is
one possible contributor to the Oct 4 assert; that is a guess, not a finding.

## What cannot be fixed in application code

If the kernel itself blocks inside a USB URB cancel (a D-state task), no process
can leave that state. The watchdog will try to exit and may not get to. What
this design does is avoid the known path to that state, keep every wait bounded,
and keep ALSA out of the container. If a D-state ever shows up again, capture
`cat /proc/<pid>/stack` and `dmesg` before rebooting and open an issue with them.

A host-side udev rule is a possible extra layer (stop the container when the
pedal is removed, start it when it returns). It is not needed for the above and
is not installed, since the homelab rule is compose-only.

## Hardware notes

* A bad host SysEx write crashed the pedal itself ("OFFON <= 1"). The bridge
  never exposes a bypass write over SysEx; blocks switch with CC (see README).
* The pedal does not echo host writes. A write only shows on its screen.
