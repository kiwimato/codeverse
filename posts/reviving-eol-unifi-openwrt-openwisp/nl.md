---
title: Drie afgedankte UniFi-accesspoints nieuw leven in met OpenWrt en OpenWISP
description: Drie eerste-generatie UniFi-accesspoints, voor het laatst gepatcht in 2021, draaien nu OpenWrt 25.12 en worden beheerd vanuit één self-hosted OpenWISP — centrale config, monitoring en roaming, geen cloud en geen licentie.
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
UAP-Pro en een UAP-Outdoor+. Prima hardware, alleen stopte Ubiquiti bij firmware
**4.3.28.11361 in februari 2021** en verklaarde ze een maand later end-of-life. De laatste
controller die ze nog adopteert is 6.0.45, zelf ook al jaren oud. Dus de keuze was de
gebruikelijke voor oud-maar-goed spul: de container in, of een actueel besturingssysteem.
Ik heb alle drie geflasht naar **OpenWrt 25.12** en onder één self-hosted **OpenWISP**
gezet.

## De drie accesspoints

| Model | SoC | Flash / RAM | Band(en) |
|-------|-----|-------------|----------|
| UAP (BZ2) | Atheros AR7241 | 8 MB / 60 MB | 2,4 GHz |
| UAP-Pro (U7P) | Atheros AR9344 | 16 MB / 125 MB | 2,4 + 5 GHz |
| UAP-Outdoor+ (U2HSR) | Atheros AR7241 | 16 MB / 60 MB | 2,4 GHz |

Alle drie zijn ondersteunde ath79-targets in OpenWrt, en dat is de enige reden dat dit een
weekendklus is en geen reverse-engineeringproject.

## Waarom je ze niet zomaar flasht

Elke handleiding zegt: zet de OpenWrt factory-image op de AP met TFTP-recovery of
Ubiquiti's eigen `fwupdate.real`. Op deze AP's, met deze firmware, weigeren ze het allebei.
Twee redenen:

- Stock firmware vanaf 4.0.15 **liet de `rootfs`-partitie vallen**. De indeling is alleen
  u-boot, zijn environment, één `kernel`- (of `jffs2`-)partitie, config en de radio-EEPROM.
  De tools verwachten een partitie die er niet is.
- U-boot controleert de **RSA-handtekening** (`ENDS`) die Ubiquiti aan zijn eigen images
  plakt. De image van OpenWrt heeft die niet, dus TFTP-recovery en `fwupdate` wijzen hem af
  als geen geldige UBNT-image.

Wat wél werkt, is de OpenWrt **sysupgrade**-image rechtstreeks in de kernel-partitie
schrijven met OpenWrt's *eigen* `mtd`-tool — de `mtd` uit de stock-busybox is te oud. De
procedure is dus: kopieer de sysupgrade-image en een bruikbare `mtd`-binary (uit de
gebouwde OpenWrt-rootfs gehaald, gestart via zijn musl-loader) naar de AP, en dan:

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

In plaats van de generieke download te pakken en elke AP met de hand te configureren, bouwde
ik per model een eigen image met OpenWrt's **ImageBuilder** (de officiële container
`ath79-generic-25.12.5`), zodat een vers geflashte AP meteen geconfigureerd opkomt en al
met OpenWISP praat.

Het is een domme AP, dus het meeste van OpenWrt gaat eruit:

```
-dnsmasq -firewall4 -nftables -odhcpd -ppp ...
+wpad-mbedtls +usteer +iwinfo +openwisp-config +openwisp-monitoring
```

`usteer` is de interessante toevoeging: het doet **802.11k/v**-steering zodat een client die
door het huis loopt naar de dichtstbijzijnde AP wordt geduwd in plaats van te blijven hangen
aan de eerste die hij zag. Het heeft de volledige `wpad-mbedtls` nodig, niet de `-basic`,
want alleen de volledige heeft de 802.11v-code (`WNM`) ingebouwd — een detail dat je een
middag kost als je het mist. De config — hostname, radiokanaal, de `Fritzi`-SSID en zijn
sleutel, 802.11k/v aan, de SSH-sleutels, een root-wachtwoord als terugval — zit erin gebakken
als een `uci-defaults`-script dat bij de eerste boot draait, per AP gegenereerd uit de eigen
vastgelegde instellingen van die AP, zodat het wifi-wachtwoord nergens wordt ingetypt.

## Het flashen zelf, en wat het me leerde

Drie dingen die achteraf voor de hand liggen:

- **Een `mtd write` op de achtergrond sterft zodra de SSH-sessie sluit.** De eerste poging
  leek te werken en had niets gedaan; de kernel-partitie was ongemoeid (de magic bytes
  klopten nog). De write zo verpakken dat hij `HUP` negeert — `( trap "" HUP; mtd … ) &
  wait` — loste het op. Verifieer met een teruglezing van precies de lengte van de image,
  niet een afgerond aantal blokken, anders krijg je een valse mismatch en een onnodige
  schrik.
- **De Outdoor+ komt terug op een ander MAC-adres.** OpenWrt bridget beide ethernetpoorten
  en neemt het adres van de tweede poort, dus de AP die op het netwerk `80:…:d2:20` was, is
  nu `82:…:d2:20`. Ik was een paar minuten overtuigd dat hij niet geboot was, tot ik naar de
  juiste buur keek.
- **Controleer dat de image voor het bord is vóór je schrijft.** Toen ik het flash-script
  van de Pro afleidde van dat van de BZ2, bleef het BZ2-imagepad staan, en de dry run zette
  vrolijk een UAP-image klaar voor de Pro — wat hem gebrickt zou hebben. Beide scripts lezen
  nu de sysupgrade-metadata en weigeren te schrijven tenzij die het bord noemt waar ze op
  gericht zijn.

De Outdoor+ moest ook zijn zendvermogen naar 10 dBm, want zijn antenne en versterker voegen
10–11 dB toe en de EU-limiet op 2,4 GHz is 20 dBm — met de standaard van OpenWrt zat hij er
ruim overheen.

## Wat OpenWISP echt oplevert

Alleen OpenWrt zou drie AP's betekenen waar je één voor één op in moet SSH'en.
[OpenWISP](https://openwisp.org) is de andere helft: een self-hosted controller, in Docker
op de huisserver, die ze als vloot beheert. Wat het concreet geeft:

- **Eén dashboard voor drie verschillende modellen.** De oude UniFi-controller sprak alleen
  met UniFi-hardware en was zelf bevroren op een release uit 2021. OpenWISP maakt het niet
  uit wat het apparaat is, alleen dat het de agent draait.
- **Monitoring.** Elke AP rapporteert zijn verbonden wifi-clients, interfaceverkeer, load,
  geheugen, schijf, buren en uptime, met grafieken over tijd. Dit is het stuk dat je meteen
  mist als je een vendor-controller verlaat.
- **Config-templates met een vangnet.** Een template schrijf je één keer en push je naar
  elke AP; `merge_config` houdt de eigen stukjes van elk apparaat, en `test_config` past een
  wijziging toe, controleert of de AP nog bereikbaar is, en **rolt automatisch terug** als
  een slechte push je anders zou buitensluiten. De agent pollt elke twee minuten.
- **SSH-sleutels en firmware, centraal.** Sleutels worden via een template verspreid;
  image-upgrades draai je vanuit hetzelfde dashboard in plaats van drie handmatige
  `sysupgrade`s.
- **Roaming over de vloot.** Met `usteer` op elke AP werken ze samen: direct na het flashen
  had de UAP de Pro al uit zichzelf als steering-peer ontdekt. Eén SSID, drie AP's, clients
  die tussen ze doorgegeven worden.

En omdat de hele stack open source is, is een ontbrekend stuk iets wat je zelf kunt dichten
in plaats van melden en afwachten. De wifi-sessieweergave van OpenWISP toonde clients alleen
op MAC-adres; de data om een hostname en IP te laten zien zat er niet in, dus heb ik dat
toegevoegd — een kleine DHCP/ARP-snooper op de AP's en een paar velden op de server — en als
branches gepusht tegen het bijbehorende
[upstream-issue](https://github.com/openwisp/openwisp-monitoring/issues/629). Probeer dat
maar eens met een dichtgetimmerd apparaat.

## Wat ik mezelf aan het begin had willen vertellen

- Eerste-generatie UniFi-AP's zijn gewone ath79-OpenWrt-targets, maar op stock 4.x flash je
  ze met `mtd`, niet met TFTP of `fwupdate` — er is geen `rootfs`-partitie en u-boot
  controleert de handtekening van Ubiquiti.
- Bouw per model een image met ImageBuilder zodat een geflashte AP zichzelf configureert en
  bij de controller komt; configureer geen drie bakjes met de hand.
- `usteer` heeft de volledige `wpad-mbedtls` nodig voor 802.11v, en het zendvermogen van de
  Outdoor+ moet omlaag voor de EU-limieten.
- De reden om dit allemaal te doen is OpenWISP: centrale config met automatische rollback,
  echte monitoring, roaming over de hele vloot en firmware — self-hosted, geen licentie, op
  hardware die de fabrikant al had afgeschreven.
