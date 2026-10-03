---
title: Talking Modbus to a Huawei SUN2000 over its own WiFi — and why NAT is not an option
description: Without a Smart Dongle, a Huawei SUN2000 only speaks Modbus-TCP on its own WiFi AP. Getting Home Assistant on it meant a login proxy and no NAT.
date: 2026-10-03
tags: homelab
draft: true
---

<!--
  Optional additions — each marked TODO below:
  - a photo of the inverter / the USB stick / the UniFi AP
  - a Home Assistant dashboard screenshot once data is flowing again
  - the outcome of the UAP-Pro cutover (last section) once it has run for a while
-->

The house in Romania has a Huawei SUN2000-8K-LC0 with a LUNA2000 battery and 11.8 kWp of
panels. Huawei's cloud, FusionSolar, shows what it produces — five-minute averages. I wanted live numbers in Home Assistant, and eventually the ability to tell
the battery *when* to charge. That means Modbus-TCP, locally.

The normal way to get it is Huawei's Smart Dongle, which exposes Modbus on the house LAN.
This inverter does not have one. What it does have is a built-in WiFi access point, meant
for the installer's phone during commissioning, and on that network the inverter listens
on port **6607**. This is the story of making that access point a permanent data link, and
of the limitations that only show up once you try.

## Getting onto the inverter's network

The inverter's AP is a closed little world: it hands the client an address in
`192.168.8.0/24`, the inverter itself is `192.168.8.1`, and there is no route anywhere else.
Home Assistant runs in Docker on an Unraid server in the house, which is on the normal LAN.
Something has to bridge the two.

The obvious plan is the one every network engineer reaches for first: put a WiFi stick in
the server, associate it with the inverter AP, and NAT the LAN through it. Anything that
wants the inverter sends packets to `192.168.8.1`, the server masquerades them out of
`wlan0`, done.

The TCP part of that plan works perfectly. The SYN goes out, the SYN-ACK comes back, the
handshake completes, and pings are a steady 2 ms. And then the inverter says nothing.
Every Modbus request is acknowledged at TCP level and never answered.

## The protocol is Modbus — with a Huawei login in front

Before blaming the network I had to rule out the protocol, because port 6607 is not plain
Modbus. It is standard Modbus-TCP framing, but on the WiFi AP the inverter refuses every
register read with an exception until the client has logged in. The login is a
Huawei-specific function code, `0x41`:

| step | PDU | meaning |
|------|-----|---------|
| 1 | `41 24 01 00` | ask for a 16-byte challenge |
| 2 | `41 25 <len> <client challenge> <user> <digest>` | log in as `installer` |

The digest is `HMAC-SHA256(key = SHA256(password), message = inverter's challenge)`. The
excellent [`huawei-solar`](https://github.com/wlcrs/huawei-solar-lib) Python library
implements all of this, and it is what the Home Assistant integration uses.

So with the right library and the right password, everything should have worked. Over
the NAT, it did not: the challenge request itself — eleven bytes — timed out every time.

## No NAT to the inverter

What finally worked was taking NAT out of the inverter-facing leg completely. The
WiFi stick was passed straight into a VM, the VM associated with the AP itself, and the
library ran *on the machine that owned the WiFi link*. Login succeeded on the first try,
and every register read after it.

From there the rule became: **the TCP connection that reaches the inverter must start on
the box that is associated with its access point.** Anything further away talks to a
*proxy* on that box, and the proxy opens a brand-new connection of its own. The inverter
never sees a forwarded or translated flow.

There is a second constraint hiding in the same tests, and to be fair to the evidence I
should name it: the inverter only answered a client at **`192.168.8.2`**. With a static
`.199` — association fine, TCP fine — it was just as silent as through the NAT. Some of
the failed NAT experiments ran from a different address, so the two effects are not
perfectly separated. In practice it does not matter, because the design that satisfies
both is the same one:

```
Home Assistant ──► proxy on the WiFi box :6607
                     │  fresh TCP, source 192.168.8.2
                     ▼
                   inverter 192.168.8.1:6607
```

Translated and forwarded flows were never answered, a fresh socket from `.2` always was,
and I stopped trying to be clever.

## The proxy has to log in, too

The first proxy was a one-line `socat`. Home Assistant still could not add the inverter,
and the reason is ordering: the integration's setup reads the model name to detect what
kind of device it is talking to — *before* it logs in. On this inverter that read is
refused, so detection fails and setup aborts.

The fix was to make the proxy do the login itself. For each incoming connection it opens a
new TCP connection to the inverter, performs the `0x41` challenge and login, and only then
starts piping bytes in both directions. Home Assistant receives a session that is already
authenticated: detection works, reads work, and because the session has installer rights,
writes (battery modes, time-of-use schedules) work too. It is under a hundred lines of
`asyncio`, supervised by a shell loop that restarts it if it ever exits.

## Limitations we hit along the way

**One Modbus session, total.** The inverter serves exactly one Modbus client at a time.
While Home Assistant holds the session, a second client — a test script, the FusionSolar
app on a phone connected to the same AP — either gets refused or knocks Home Assistant off.
The integration then logs *"the inverter only supports one Modbus connection at a time"*.
That warning appears on any interrupted read, so it is a clue rather than a diagnosis.

**The host's network tooling wants that interface.** Unraid's own wireless scripts start a
DHCP client on any WiFi interface. The inverter AP does not answer DHCP in the way it
expects, so the client gives up, assigns a `169.254.x.x` link-local address, and the static
`192.168.8.2` is gone. The fix was a small guard script that keeps `wlan0` out of the DHCP
daemon's configuration and puts the address back if anything removes it. (Whatever you do,
do not run `dhcpcd` by hand against `wlan0` on that box. It manages the main bridge, and I
took the whole server off the network finding that out.)

**A USB WiFi stick is a weak radio.** The cheap 2.4 GHz stick in the server spent bad days
between −67 and −73 dBm. That is enough to associate
and too little to stay associated. Link flaps look exactly like Modbus failures from Home
Assistant's side, so the first thing to check is always the radio: `iw dev wlan0 link`.

**The Modbus engine can wedge on its own — and a reboot may not fix it.** The most confusing
failure looks like this in a packet capture: the connection opens, the eleven-byte login
request goes out, the inverter *acknowledges it at TCP level* — and never replies. Not even a
plain register read without login gets the usual "log in first" exception back; the engine is
completely silent. This repeats every fifteen seconds for hours. The WiFi is fine, pings are
fine, DHCP still hands the stick its `192.168.8.2`, and there is no other client. To be sure
it was not my end, I tried every path to the inverter side by side — a raw socket, the `socat`
forwarder, and the login proxy — and they all timed out identically, so whatever was wrong
was on `192.168.8.1`.

The instinct is to reboot the inverter, and that instinct is where I lost the most time.
Switching it off and on from the app did nothing — and the giveaway was that the server's
WiFi client never reassociated, so the communication board had stayed up the whole time. So I
went further: a full cold shutdown, AC and DC isolated *and both batteries off* for several
minutes. This time the board really did restart — `wlan0` dropped and came back — and Modbus
was *still* silent.

What actually brought it back was not a reboot at all. I joined the inverter's own
`SUN2000-…` WiFi with a phone and logged into the SUN2000 app. The instant that management
session was established, Modbus started answering: first with the "log in first" exception it
had been withholding, and then, through the proxy, a clean installer login and live data in
Home Assistant.

The lesson has two halves. The SUN2000 app's local screen talks to the inverter over Huawei's
own management protocol, not Modbus — so the app working locally tells you the board is
healthy, not that Modbus-TCP is up. And when Modbus has gone fully silent, the thing that
wakes it is exactly that: a local management login from the app, not a power cycle. If it
happens again, I log into the app once and Home Assistant recovers on its own.

## Next: let an access point do it

All of this lives on a server with a USB stick hanging off it, which is the weakest part
of the chain. The house has three old first-generation UniFi access points, which have
recently been moved to OpenWrt and are managed with OpenWISP. One of them, a UAP-Pro, heard the
inverter at −56 dBm in a first test, against −63 dBm for the USB stick on a good day, so
the plan is to move the inverter link there.

The NAT rule decides how. The tempting version — associate the AP as a client and
masquerade the LAN through it — is exactly the setup that never got an answer. Instead, the
AP gets the same treatment as the server did:

- the 2.4 GHz radio associates with the inverter as a station, with a static
  `192.168.8.2` and **no gateway and no DNS** on that interface, so nothing on the inverter
  side can ever take over the AP's own default route;
- a `socat` on the AP listens on its LAN address, accepts only the Home Assistant server,
  and opens a fresh connection to `192.168.8.1:6607` *bound to* `192.168.8.2`;
- the server's login proxy just points at the AP instead of at `192.168.8.1`.

No forwarding, no masquerade — `ip_forward` stays off. The inverter still sees exactly one
fresh TCP connection from `.2`.

One OpenWrt detail mattered more than expected. A radio can serve an access point and a
station at the same time, but the AP follows the station: whenever the station loses its
upstream, the AP on that radio is taken down with it. The inverter's AP is not exactly
reliable, so sharing the radio would make the house WiFi on that AP blink every time the
inverter did. That 2.4 GHz radio is therefore dedicated to the inverter link; the 5 GHz
radio and the other two APs carry the house.

<!-- TODO: outcome of the cutover once it has run for a while -->

## What I would tell myself at the start

- If the inverter has no Smart Dongle, port 6607 on its own WiFi is real Modbus-TCP — with
  a mandatory installer login.
- Never NAT the leg that reaches the inverter. Proxy, and originate from `192.168.8.2`.
- Expect one Modbus session. Anything else that connects will cost you data.
- A TCP-level ACK with no Modbus reply means the inverter, not your network. Check whether
  the WiFi association survived your "restart" before trusting it.
- If Modbus goes *completely* silent — no reply even to an unauthenticated read — a power
  cycle may not revive it. A local login from the SUN2000 app does, because that is a
  different protocol that wakes the management stack. "The app works" is not proof Modbus is up.
