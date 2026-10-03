---
title: Driving the chassis fans on an HP Z840 from Linux
description: The Z840's fan controller hangs off the embedded controller's private SMBus, where lm-sensors cannot see it. hpz-ecfan reaches it through the EC's own mailbox instead.
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

Some problems only exist because a vendor decided you did not need to solve them. The HP
Z840 is one of those: a capable workstation whose chassis fans run at whatever profile
the BIOS picked at boot, with no way to say otherwise from the operating system.

So I wrote one. [`hpz-ecfan`](https://github.com/kiwimato/hpz-ecfan) is a small Python
tool that moves the fan curve on Z-series workstations from Linux — no kernel module, no
reboot, no firmware patch.

## Why the normal tools see nothing

The obvious approach fails immediately. `lm-sensors` finds no fan controller. `fancontrol`
has nothing to control. The `adt7475` kernel driver, which is exactly the right driver,
never binds.

The reason is topology. The chip driving the chassis fans is an ON Semiconductor
**NCT7491** — an ADT7475-family part, thoroughly documented in a public datasheet. But it
does not sit on the SMBus that the PCH owns. It sits on the *private* bus of the Nuvoton
embedded controller, and `i2c-i801` has no path to it. The chip is right there, fully
standard, and completely unreachable.

HP's own ACPI and WMI expose part of the picture — the `hp-wmi-sensors` driver will happily
read temperatures and fan speeds. The read side is public. The write side is not.

## The mailbox

The write side turned out to be recoverable from HP's `HhmDxe` firmware module, which
programs the chip at every POST. It has to reach the NCT7491 somehow, and the mechanism it
uses is a small SMBus proxy living in the EC's RAM window.

That window sits at I/O ports `0x800`–`0x8FE`, page-selected through `0x8FF`. Page 0
contains the proxy:

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
poll. That is the entire protocol.

## Two things the protocol does not give you

**There is no error flag.** A NACK on the bus completes exactly like a success: `F0` bit 0
clears, and `E8` is left holding whatever was already there. A failed read returns stale
data that looks perfectly plausible. The only defence is to read every write back and
compare — which the tool does, without exception.

**There is no arbitration.** The mailbox is a handful of shared bytes. Two processes
stepping through the sequence at the same time will interleave their writes and corrupt
each other's data byte, and because of the missing error flag, neither will notice. Every
transaction therefore goes through an `flock` on `/var/lock/ecmbox` (override with
`--lock` or `HPZ_EC_LOCK`). It is not optional.

## Failing toward cold

The tempting design is to take the chip out of its automatic mode and drive the PWM duty
directly. It is simpler to reason about and it gives precise control. It is also the wrong
choice, because it makes a daemon crash into a thermal event.

Instead the tool stays inside the chip's own automatic loop and moves the shape of the
curve: the floor (`PWMmin`) or the knee (`Tmin`). The NCT7491 goes on doing its own
temperature-driven regulation exactly as the BIOS configured it — it is just working from
different numbers. If the tool dies, gets killed, or the machine loses the process
entirely, the fans keep regulating. The THERM limits stay armed throughout.

Everything else follows the same rule. The tool refuses to write if the chip's LOCK bit is
set. It refuses to run at all on a machine whose DMI product name is not an HP Z unless
you pass `--force`. Every failure direction it can choose, it chooses the one that ends
with more airflow rather than less.

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
front pair, both driven by PWM3. It needs `/dev/port`, so root or `CAP_SYS_RAWIO` — which
also means it runs fine from a privileged container.
<!-- TODO: mention your own Unraid setup here if you want -->

Nothing survives a power cycle: that resets both the EC and the chip to BIOS defaults. A
warm reboot re-runs POST, which rewrites the chip anyway. Whatever you set is a runtime
change, which is another way of saying the machine is never more than a reboot away from
its factory behaviour.

## Status

Tested live on a Z840 with BIOS M60 v02.56. Other Z-series boards very likely share the
same EC and the same mailbox, but may well wire their fans to different PWM outputs — run
`dump` and `status` and read what you get before writing anything. Reports from other
boards are welcome.

The full protocol write-up, including the verification record, is in
[`docs/protocol.md`](https://github.com/kiwimato/hpz-ecfan/blob/master/docs/protocol.md).
Register-level knowledge comes from ON Semiconductor's public datasheet and the read side
from HP's own ACPI tables; none of HP's code is reproduced.

**Repo:** [github.com/kiwimato/hpz-ecfan](https://github.com/kiwimato/hpz-ecfan)
