---
title: Drie afgedankte UniFi-accesspoints nieuw leven in met OpenWrt en OpenWISP
description: Drie eerste-generatie UniFi-AP's, laatst gepatcht in 2021, draaien nu OpenWrt 25.12 onder self-hosted OpenWISP: centrale config, monitoring, roaming.
date: 2026-10-03
tags: homelab, opensource
draft: true
---

<!--
  TODO voor publicatie:
  - een screenshot van het OpenWISP-dashboard met de drie APs en monitoringdata
  - eventueel een foto van de drie UniFi-APs / de AP die via serieel geflasht wordt
-->

Het huis in Roemenië draait op drie eerste-generatie UniFi-accesspoints: een UAP, een
UAP-Pro en een UAP-Outdoor+. Prima hardware, maar Ubiquiti stopte bij firmware
4.3.28.11361 in februari 2021 en verklaarde ze een maand later end-of-life. De laatste
controller die ze nog adopteert is 6.0.45, en die is zelf ook al jaren oud. Dan heb je
de gebruikelijke keuze voor oud spul dat het nog prima doet: de container in, of een
actueel besturingssysteem erop. Ik heb alle drie geflasht naar OpenWrt 25.12 en onder één
self-hosted OpenWISP gezet.

## De drie accesspoints

| Model | SoC | Flash / RAM | Band(en) |
|-------|-----|-------------|----------|
| UAP (BZ2) | Atheros AR7241 | 8 MB / 60 MB | 2,4 GHz |
| UAP-Pro (U7P) | Atheros AR9344 | 16 MB / 125 MB | 2,4 + 5 GHz |
| UAP-Outdoor+ (U2HSR) | Atheros AR7241 | 16 MB / 60 MB | 2,4 GHz |

Alle drie zijn ondersteunde ath79-targets in OpenWrt. Zonder dat was dit een
reverse-engineeringproject geworden in plaats van een weekendklus.

## Waarom je ze niet zomaar flasht

Elke handleiding zegt: zet de OpenWrt factory-image op de AP met TFTP-recovery of
Ubiquiti's eigen `fwupdate.real`. Op deze AP's, met deze firmware, weigeren ze het allebei,
om twee redenen:

- Stock firmware vanaf 4.0.15 heeft geen `rootfs`-partitie meer. De indeling is alleen
  u-boot, zijn environment, één `kernel`- (of `jffs2`-)partitie, config en de radio-EEPROM,
  en de tools verwachten een partitie die er niet is.
- U-boot controleert de RSA-handtekening (`ENDS`) die Ubiquiti aan zijn eigen images
  plakt. De image van OpenWrt heeft die niet, dus TFTP-recovery en `fwupdate` wijzen hem af
  als geen geldige UBNT-image.

Wat wél werkt, is de OpenWrt-sysupgrade-image rechtstreeks in de kernel-partitie
schrijven met OpenWrt's *eigen* `mtd`-tool, want de `mtd` uit de stock-busybox is te oud.
Ik kopieerde de sysupgrade-image en een bruikbare `mtd`-binary naar de AP (die binary
haal je uit de gebouwde OpenWrt-rootfs en start je via zijn musl-loader), en dan:

```
mtd -e kernel write /tmp/openwrt.bin kernel     # BZ2
mtd -e jffs2  write /tmp/openwrt.bin jffs2      # Pro en Outdoor+
```

De stock-u-boot draait nog steeds `ubntappinit; ubntboot`, en die start probleemloos de
OpenWrt-uImage die nu staat waar eerst de kernel stond. Had dat niet gewerkt, dan is de
redding een TFTP van de stock-image met reset ingedrukt bij het inschakelen (de AP luistert
op 192.168.1.20). Ik had de hele tijd een 3,3V-USB-serieeladapter klaarliggen en heb hem
nooit nodig gehad.

## De image bouwen

Ik had geen zin om de generieke download te pakken en elke AP met de hand te
configureren, dus bouwde ik per model een eigen image met OpenWrt's ImageBuilder (de
officiële container `ath79-generic-25.12.5`). Een vers geflashte AP komt dan meteen
geconfigureerd op en praat al met OpenWISP.

Het zijn domme AP's, dus het meeste van OpenWrt gaat eruit:

```
-dnsmasq -firewall4 -nftables -odhcpd -ppp ...
+wpad-mbedtls +usteer +iwinfo +openwisp-config +openwisp-monitoring
```

`usteer` is de interessante toevoeging. Het doet 802.11k/v-steering, zodat een client die
door het huis loopt naar de dichtstbijzijnde AP wordt geduwd in plaats van te blijven hangen
aan de eerste die hij zag. Het heeft de volledige `wpad-mbedtls` nodig, niet de `-basic`,
want alleen de volledige heeft de 802.11v-code (`WNM`) ingebouwd. Mis je dat, dan ben je
een middag kwijt.

De config zit erin gebakken als een `uci-defaults`-script dat bij de eerste boot draait:
hostname, radiokanaal, de `Fritzi`-SSID en zijn sleutel, 802.11k/v aan, de SSH-sleutels en
een root-wachtwoord als terugval. Dat script wordt per AP gegenereerd uit de eigen
vastgelegde instellingen van die AP, zodat het wifi-wachtwoord nergens wordt ingetypt.

## Het flashen zelf, en wat het me leerde

Drie dingen die achteraf voor de hand liggen:

- **Een `mtd write` op de achtergrond sterft zodra de SSH-sessie sluit.** De eerste poging
  leek te werken en had niets gedaan: de kernel-partitie was ongemoeid en de magic bytes
  klopten nog. De write verpakken als `( trap "" HUP; mtd … ) & wait`, zodat hij `HUP`
  negeert, loste het op. Verifieer met een teruglezing van precies de lengte van de image,
  niet een afgerond aantal blokken, anders krijg je een valse mismatch en een onnodige
  schrik.
- **De Outdoor+ komt terug op een ander MAC-adres.** OpenWrt bridget beide ethernetpoorten
  en neemt het adres van de tweede poort, dus de AP die op het netwerk `80:…:d2:20` was, is
  nu `82:…:d2:20`. Ik was een paar minuten overtuigd dat hij niet geboot was, tot ik naar de
  juiste buur keek.
- **Controleer dat de image voor het bord is vóór je schrijft.** Toen ik het flash-script
  van de Pro afleidde van dat van de BZ2, bleef het BZ2-imagepad staan, en de dry run zette
  vrolijk een UAP-image klaar voor de Pro. Dat had hem gebrickt. Beide scripts lezen nu de
  sysupgrade-metadata en weigeren te schrijven tenzij die het bord noemt waar ze op gericht
  zijn.

De Outdoor+ moest ook zijn zendvermogen naar 10 dBm. Zijn antenne en versterker voegen
10 tot 11 dB toe en de EU-limiet op 2,4 GHz is 20 dBm, dus met de standaard van OpenWrt
zat hij er ruim overheen.

## Wat OpenWISP toevoegt

Met alleen OpenWrt moet je op drie AP's één voor één inloggen via SSH.
[OpenWISP](https://openwisp.org) is de andere helft: een self-hosted controller, in Docker
op de huisserver, die ze als vloot beheert.

- Je hebt één dashboard voor drie verschillende modellen. De oude UniFi-controller sprak
  alleen met UniFi-hardware en was zelf bevroren op een release uit 2021. OpenWISP maakt
  het niet uit wat het apparaat is, alleen dat het de agent draait.
- Elke AP rapporteert zijn verbonden wifi-clients, interfaceverkeer, load, geheugen,
  schijf, buren en uptime, met grafieken over tijd. Dit is het stuk dat je meteen mist als
  je een vendor-controller verlaat.
- Een config-template schrijf je één keer en push je naar elke AP. `merge_config` houdt de
  eigen stukjes van elk apparaat, en `test_config` past een wijziging toe, controleert of de
  AP nog bereikbaar is, en rolt automatisch terug als een slechte push je anders zou
  buitensluiten. De agent pollt elke twee minuten.
- SSH-sleutels worden via een template verspreid, en image-upgrades draai je vanuit
  hetzelfde dashboard in plaats van drie handmatige `sysupgrade`s.
- Met `usteer` op elke AP regelen de AP's het roamen onderling. Direct na het flashen had
  de UAP de Pro al uit zichzelf als steering-peer gevonden, dus clients gaan op één SSID
  tussen de drie AP's over.

Omdat de hele stack open source is, kon ik een gat zelf dichten. De wifi-sessieweergave
van OpenWISP toonde clients alleen op MAC-adres, en de data om een hostname en IP te laten
zien zat er niet in. Ik heb dat toegevoegd met een kleine DHCP/ARP-snooper op de AP's en
een paar velden op de server, en het als branches gepusht tegen het bijbehorende
[upstream-issue](https://github.com/openwisp/openwisp-monitoring/issues/629). Bij een
dichtgetimmerd apparaat had ik een verzoek ingediend en afgewacht.

## Wat ik mezelf aan het begin had willen vertellen

- Eerste-generatie UniFi-AP's zijn gewone ath79-OpenWrt-targets, maar op stock 4.x flash je
  ze met `mtd`, niet met TFTP of `fwupdate`, want er is geen `rootfs`-partitie en u-boot
  controleert de handtekening van Ubiquiti.
- Bouw per model een image met ImageBuilder, zodat een geflashte AP zichzelf configureert
  en bij de controller komt. Configureer geen drie bakjes met de hand.
- `usteer` heeft de volledige `wpad-mbedtls` nodig voor 802.11v, en het zendvermogen van de
  Outdoor+ moet omlaag voor de EU-limieten.
- OpenWISP is de reden om dit allemaal te doen. Je krijgt centrale config met automatische
  rollback, echte monitoring, roaming over de hele vloot en firmware-upgrades, self-hosted
  en zonder licentie, op hardware die de fabrikant al had afgeschreven.
