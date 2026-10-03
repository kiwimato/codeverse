---
title: Reviving three end-of-life UniFi access points with OpenWrt and OpenWISP
description: Three first-generation UniFi APs, last patched in 2021, now run OpenWrt 25.12 and are managed from one self-hosted OpenWISP — central config, monitoring and roaming, no cloud and no license.
date: 2026-10-03
tags: homelab, opensource
draft: true
---

<!--
  TODO before publishing:
  - a screenshot of the OpenWISP dashboard with the three APs listed and monitoring data
  - optionally a photo of the three UniFi APs / the one being flashed over serial
-->

The house in Romania runs on three first-generation UniFi access points: a UAP, a
UAP-Pro and a UAP-Outdoor+. Good hardware, except Ubiquiti stopped at firmware
**4.3.28.11361 in February 2021** and marked them end-of-life a month later. The last
controller that still adopts them is 6.0.45, itself years old. So the choice was the
usual one for old-but-fine gear: landfill, or a current operating system. I flashed all
three to **OpenWrt 25.12** and put them under one self-hosted **OpenWISP**.

## The three access points

| Model | SoC | Flash / RAM | Band(s) |
|-------|-----|-------------|---------|
| UAP (BZ2) | Atheros AR7241 | 8 MB / 60 MB | 2.4 GHz |
| UAP-Pro (U7P) | Atheros AR9344 | 16 MB / 125 MB | 2.4 + 5 GHz |
| UAP-Outdoor+ (U2HSR) | Atheros AR7241 | 16 MB / 60 MB | 2.4 GHz |

All three are supported ath79 targets in OpenWrt, which is the only reason this is a
weekend project and not a reverse-engineering one.

## Why you cannot just flash them

Every guide says to drop the OpenWrt factory image onto the inverter — sorry, onto the
AP — with TFTP recovery or Ubiquiti's own `fwupdate.real`. On these, at this firmware,
both refuse it. Two reasons:

- Stock firmware from 4.0.15 onwards **dropped the `rootfs` partition**. The layout is
  just u-boot, its environment, a single `kernel` (or `jffs2`) partition, config and the
  radio EEPROM. The tools expect a partition that is not there.
- U-boot checks the **RSA signature trailer** (`ENDS`) that Ubiquiti appends to its own
  images. OpenWrt's image does not have it, so TFTP recovery and `fwupdate` reject it as
  not a valid UBNT image.

What does work is writing the OpenWrt **sysupgrade** image straight into the kernel
partition with OpenWrt's *own* `mtd` tool — the stock busybox `mtd` is too old. So the
procedure is: copy the sysupgrade image and a statically-usable `mtd` binary (pulled out
of the built OpenWrt rootfs, run through its musl loader) onto the AP, then:

```
mtd -e kernel write /tmp/openwrt.bin kernel     # BZ2
mtd -e jffs2  write /tmp/openwrt.bin jffs2      # Pro and Outdoor+
```

The stock u-boot still runs `ubntappinit; ubntboot`, and that quite happily boots the
OpenWrt uImage that now lives where the kernel used to be. If it had not, the recovery is
a TFTP of the stock image with reset held at power-on (the AP listens at 192.168.1.20).
I had a 3.3 V USB-serial adapter on the bench the whole time and never needed it.

## Building the image

Rather than take the generic download and configure each AP by hand, I built a
purpose-made image per model with OpenWrt's **ImageBuilder** (the official
`ath79-generic-25.12.5` container), so a freshly flashed AP comes up already configured
and already talking to OpenWISP.

It is a dumb access point, so most of OpenWrt comes out:

```
-dnsmasq -firewall4 -nftables -odhcpd -ppp ...
+wpad-mbedtls +usteer +iwinfo +openwisp-config +openwisp-monitoring
```

`usteer` is the interesting addition: it does **802.11k/v** steering so a client walking
through the house is nudged to the nearest AP instead of clinging to the first one it
saw. It needs the full `wpad-mbedtls`, not the `-basic` build, because only the full one
has the 802.11v (`WNM`) code compiled in — a detail that costs an afternoon if you miss
it. The config — hostname, radio channel, the `Fritzi` SSID and its key, 802.11k/v on,
the SSH keys, a root-password fallback — is baked in as a first-boot `uci-defaults`
script, generated per AP from the AP's own captured settings so the WiFi password never
gets typed anywhere.

## The flash itself, and what it taught me

Three things that are obvious in hindsight:

- **A backgrounded `mtd write` dies the instant the SSH session closes.** The first run
  looked like it worked and had done nothing; the kernel partition was untouched (its
  magic bytes were intact). Wrapping the write so it ignores `HUP` — `( trap "" HUP; mtd
  … ) & wait` — fixed it. Verify with a read-back of exactly the image's length, not a
  rounded block count, or you get a false mismatch and a needless scare.
- **The Outdoor+ comes back on a different MAC.** OpenWrt bridges both Ethernet ports and
  takes the second port's address, so the AP that was `80:…:d2:20` on the network is now
  `82:…:d2:20`. I spent a few minutes convinced it had not booted before I looked for the
  right neighbour.
- **Check the image is for the board before you write it.** When I derived the Pro's
  flash script from the BZ2's, it kept the BZ2 image path, and the dry run happily staged
  a UAP image onto the Pro — which would have bricked it. Both scripts now read the
  sysupgrade metadata and refuse to write unless it names the board they are pointed at.

The Outdoor+ also needed its transmit power capped to 10 dBm: its antenna and amplifier
add 10–11 dB, and the EU limit on 2.4 GHz is 20 dBm, so OpenWrt's default would have put
it well over.

## What OpenWISP actually buys

OpenWrt alone would mean three APs to SSH into one at a time. [OpenWISP](https://openwisp.org)
is the other half: a self-hosted controller, running in Docker on the house server, that
manages them as a fleet. What it gives, concretely:

- **One dashboard for three different models.** The old UniFi controller only ever spoke
  to UniFi hardware and was itself frozen at a 2021 release. OpenWISP does not care what
  the device is, only that it runs the agent.
- **Monitoring.** Each AP reports its associated WiFi clients, interface traffic, load,
  memory, disk, neighbours and uptime, with charts over time. This is the part you miss
  immediately when you leave a vendor controller.
- **Config templates with a safety net.** A template is written once and pushed to every
  AP; `merge_config` keeps each device's own bits, and `test_config` applies a change,
  checks the AP is still reachable, and **automatically rolls back** if a bad push would
  otherwise have locked you out. The agent polls every two minutes.
- **SSH keys and firmware, centrally.** Keys are distributed by a template; image
  upgrades are driven from the same dashboard instead of three manual `sysupgrade`s.
- **Roaming across the fleet.** With `usteer` on each AP, they coordinate: right after the
  flash, the UAP had already discovered the Pro as a steering peer on its own. One SSID,
  three APs, clients handed between them.

And because the whole stack is open source, a gap is something you can close yourself
rather than file and wait for. OpenWISP's WiFi-session view listed clients only by MAC
address; the data to show a hostname and IP was not there, so I added it — a small
DHCP/ARP snooper on the APs and a couple of fields on the server — and pushed it as
branches against the relevant [upstream issue](https://github.com/openwisp/openwisp-monitoring/issues/629).
Try that with a sealed appliance.

## What I would tell myself at the start

- First-gen UniFi APs are standard ath79 OpenWrt targets, but at stock 4.x you flash them
  with `mtd`, not TFTP or `fwupdate` — there is no `rootfs` partition and u-boot checks
  Ubiquiti's signature.
- Build per-model images with ImageBuilder so a flashed AP self-configures and joins the
  controller; do not hand-configure three boxes.
- `usteer` needs full `wpad-mbedtls` for 802.11v, and the Outdoor+'s TX power needs
  capping for EU limits.
- The reason to do any of this is OpenWISP: central config with automatic rollback,
  real monitoring, fleet-wide roaming and firmware — self-hosted, no license, on hardware
  the vendor had already written off.
