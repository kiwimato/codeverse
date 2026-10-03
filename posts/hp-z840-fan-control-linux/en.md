---
title: Driving the chassis fans on an HP Z840 from Linux
description: The Z840's fan controller sits on the embedded controller's private SMBus, out of reach of lm-sensors. hpz-ecfan talks to it through the EC's own mailbox.
date: 2026-09-30
tags: opensource, homelab
---

<!--
  Written from the repo's own README and docs/protocol.md. Optional additions if you
  want them — each marked TODO below:
  - what the machine actually does (Unraid host? workstation?) and how loud it was
  - whether you found the HhmDxe write side by dumping the firmware yourself
  - a `status` screenshot or a before/after noise figure
-->

The HP Z840 is a capable workstation, but its chassis fans run at whatever profile the
BIOS picked at boot, and HP gives you no way to change that from the operating system,
as if nobody would ever want to.

So I wrote it myself. [`hpz-ecfan`](https://github.com/kiwimato/hpz-ecfan) is a small Python
tool that moves the fan curve on Z-series workstations from Linux. It needs no kernel
module, no reboot and no firmware patch.

## Why the normal tools see nothing

`lm-sensors` finds no fan controller, so `fancontrol` has nothing to control. The
`adt7475` kernel driver, which is the right driver for this chip, never binds.

The chip driving the chassis fans is an ON Semiconductor **NCT7491**, an ADT7475-family
part documented in detail in a public datasheet. It does not sit on the SMBus that the
PCH owns, though. It sits on the *private* bus of the Nuvoton embedded controller, and
`i2c-i801` has no path to it, so a completely standard chip ends up out of reach.

HP's own ACPI and WMI expose some of it: the `hp-wmi-sensors` driver reads temperatures
and fan speeds without complaint. So reading is public, but writing is not.

## The mailbox

The write side could be recovered from HP's `HhmDxe` firmware module, which programs the
chip at every POST. It has to reach the NCT7491 somehow, and it does so through a small
SMBus proxy in the EC's RAM window.

That window is at I/O ports `0x800` to `0x8FE`, with the page selected through `0x8FF`.
Page 0 holds the proxy:

| byte | meaning |
|------|---------|
| `0xE5` | 7-bit device address |
| `0xE6` | bytes to read back (1 for a read, 0 for a write) |
| `0xE7` | bytes to send after the address (1: register, 2: register + data) |
| `0xE8` | data: register for a read, with the result returned in place; value for a write |
| `0xE9` | register for a write |
| `0xF0` | bit 0: write 1 to start, EC clears it on completion |

A read is `E5=dev, E8=reg, E7=1, E6=1, F0=1`, then poll until `F0` bit 0 goes low and take
the result out of `E8`. A write is `E5=dev, E8=val, E9=reg, E7=2, E6=0, F0=1` and the same
poll. There is nothing more to the protocol.

## Two things the protocol does not give you

First, there is no error flag. A NACK on the bus completes exactly like a success: `F0`
bit 0 clears, and `E8` keeps whatever was already in it. A failed read returns stale data
that looks perfectly plausible. The only defence is to read every write back and compare,
and the tool does that for every write.

Second, there is no arbitration. The mailbox is a handful of shared bytes. Two processes
stepping through the sequence at the same time will interleave their writes and corrupt
each other's data byte, and with no error flag neither will notice. So every transaction
takes an `flock` on `/var/lock/ecmbox` (override the path with `--lock` or
`HPZ_EC_LOCK`). The lock itself is not optional.

## Failing safe

Taking the chip out of its automatic mode and driving the PWM duty directly would be
simpler to reason about and would give precise control. But then a daemon crash becomes a
thermal event.

So the tool stays inside the chip's own automatic loop and only moves the shape of the
curve: the floor (`PWMmin`) or the knee (`Tmin`). The NCT7491 keeps regulating on
temperature exactly as the BIOS configured it, just with different numbers. If the tool
dies, gets killed, or the machine loses the process entirely, the fans keep regulating,
and the THERM limits stay armed throughout.

The rest of the design follows the same rule. The tool refuses to write if the chip's
LOCK bit is set, and refuses to run at all on a machine whose DMI product name is not an
HP Z unless you pass `--force`. Wherever it has a choice of how to fail, it picks the
option that ends with more airflow.

## Using it

Standard library only, Python 3.9 or newer, MIT licensed:

```
git clone https://github.com/kiwimato/hpz-ecfan
cd hpz-ecfan && pip install .
```

Then, as root:

```
python3 -m hpz_ecfan.cli status
python3 -m hpz_ecfan.cli dump                 # registers 0x00-0x9F
python3 -m hpz_ecfan.cli set-min 3 0x60       # front fans (PWM3) floor to 37% duty
python3 -m hpz_ecfan.cli set-min 1 0x80       # rear fan 0 (PWM1)
python3 -m hpz_ecfan.cli set-tmin local 35    # start the curve earlier
python3 -m hpz_ecfan.cli log --interval 30
```

On the Z840, tach1 and tach2 are the rear fans on PWM1 and PWM2; tach3 and tach4 are the
front pair, both driven by PWM3. It needs `/dev/port`, so root or `CAP_SYS_RAWIO`, which
also means it runs fine from a privileged container.
<!-- TODO: mention your own Unraid setup here if you want -->

Nothing survives a power cycle, which resets both the EC and the chip to BIOS defaults.
A warm reboot re-runs POST, and that rewrites the chip anyway. Everything you set is a
runtime change, so the machine is never more than a reboot away from its factory
behaviour.

## Status

I have tested it live on a Z840 with BIOS M60 v02.56. Other Z-series boards very likely
share the same EC and the same mailbox, but they may wire their fans to different PWM
outputs, so run `dump` and `status` and read the output before writing anything. Reports
from other boards are welcome.

The full protocol write-up, including the verification record, is in
[`docs/protocol.md`](https://github.com/kiwimato/hpz-ecfan/blob/master/docs/protocol.md).
Register-level knowledge comes from ON Semiconductor's public datasheet and the read side
from HP's own ACPI tables; none of HP's code is reproduced.

**Repo:** [github.com/kiwimato/hpz-ecfan](https://github.com/kiwimato/hpz-ecfan)
