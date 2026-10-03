---
title: Trei access point-uri UniFi ieșite din suport, readuse la viață cu OpenWrt și OpenWISP
description: Trei AP-uri UniFi de primă generație, fără update din 2021, rulează acum OpenWrt 25.12 sub un OpenWISP self-hosted: config central, monitorizare, roaming.
date: 2026-10-03
tags: homelab, opensource
image: unifi-ap-gen1.jpg
---

Casa din România merge pe trei access point-uri UniFi de primă generație: un UAP, un
UAP-Pro și un UAP-Outdoor+. Hardware-ul e în regulă, dar Ubiquiti s-a oprit la firmware-ul
4.3.28.11361 în februarie 2021 și le-a declarat end-of-life o lună mai târziu. Ultimul
controller care le mai adoptă e 6.0.45, și și ăsta are deja câțiva ani. Rămâi cu alegerea
obișnuită pentru echipamente vechi care încă merg: la groapa de gunoi, sau cu un sistem de
operare actual pe ele. Le-am făcut flash la toate trei cu OpenWrt 25.12 și le-am pus sub
un singur OpenWISP self-hosted.

![Un AP UniFi rotund și alb, de primă generație, lângă cutia lui, adaptorul PoE și cablul de alimentare](unifi-ap-gen1.jpg "Un AP UniFi de primă generație, același model ca UAP-ul simplu de aici. Nu e unitatea mea: foto de [L3u](https://commons.wikimedia.org/wiki/File:Ubiquiti_Unifi_AP.jpg), CC0, via Wikimedia Commons.")

## Cele trei access point-uri

| Model | SoC | Flash / RAM | Bandă (benzi) |
|-------|-----|-------------|---------------|
| UAP (BZ2) | Atheros AR7241 | 8 MB / 60 MB | 2,4 GHz |
| UAP-Pro (U7P) | Atheros AR9344 | 16 MB / 125 MB | 2,4 + 5 GHz |
| UAP-Outdoor+ (U2HSR) | Atheros AR7241 | 16 MB / 60 MB | 2,4 GHz |

Toate trei sunt target-uri ath79 suportate în OpenWrt. Fără asta, ar fi fost un proiect
de reverse engineering, nu unul de weekend.

## De ce nu le poți face pur și simplu flash

Toate ghidurile îți spun să pui imaginea factory de OpenWrt pe AP prin TFTP recovery sau
cu `fwupdate.real`, tool-ul Ubiquiti. Pe AP-urile astea, cu firmware-ul ăsta, amândouă o
refuză, din două motive:

- Firmware-ul stock de la 4.0.15 încoace nu mai are partiția `rootfs`. Layout-ul e doar
  u-boot, environment-ul lui, o singură partiție `kernel` (sau `jffs2`), config și
  EEPROM-ul radio, iar tool-urile se așteaptă la o partiție care nu există.
- U-boot verifică semnătura RSA (`ENDS`) pe care Ubiquiti o adaugă la finalul propriilor
  imagini. Imaginea OpenWrt n-o are, așa că TFTP recovery și `fwupdate` o resping ca
  imagine UBNT invalidă.

Ce merge e să scrii imaginea sysupgrade de OpenWrt direct în partiția de kernel cu tool-ul
`mtd` *al OpenWrt*, pentru că `mtd`-ul din busybox-ul stock e prea vechi. Am copiat pe AP
imaginea sysupgrade și un binar `mtd` utilizabil static (binarul l-am scos din rootfs-ul
OpenWrt construit și l-am rulat prin loader-ul lui musl), apoi:

```
mtd -e kernel write /tmp/openwrt.bin kernel     # BZ2
mtd -e jffs2  write /tmp/openwrt.bin jffs2      # Pro and Outdoor+
```

U-boot-ul stock rulează în continuare `ubntappinit; ubntboot`, și ăsta pornește fără
probleme uImage-ul OpenWrt care stă acum unde era kernelul. Dacă n-ar fi mers, recovery-ul
e un TFTP cu imaginea stock, ținând reset apăsat la pornire (AP-ul ascultă pe
192.168.1.20). Am avut tot timpul pe masă un adaptor USB-serial de 3,3 V și nu mi-a
trebuit deloc.

## Construirea imaginii

Nu voiam să iau download-ul generic și să configurez fiecare AP de mână, așa că am
construit câte o imagine pentru fiecare model cu ImageBuilder-ul OpenWrt (containerul
oficial `ath79-generic-25.12.5`). Un AP proaspăt flash-uit pornește deja configurat și
deja vorbește cu OpenWISP.

Sunt simple access point-uri (dumb AP), așa că cea mai mare parte din OpenWrt iese
afară:

```
-dnsmasq -firewall4 -nftables -odhcpd -ppp ...
+wpad-mbedtls +usteer +iwinfo +openwisp-config +openwisp-monitoring
```

Adăugarea interesantă e `usteer`. Face steering 802.11k/v, așa că un client care se plimbă
prin casă e împins spre cel mai apropiat AP în loc să rămână agățat de primul pe care l-a
văzut. Are nevoie de `wpad-mbedtls` complet, nu de varianta `-basic`, pentru că doar cel
complet are compilat codul pentru 802.11v (`WNM`). Dacă scapi asta din vedere, pierzi o
după-amiază.

Configurația e inclusă în imagine ca script `uci-defaults` care rulează la primul boot:
hostname, canalul radio, SSID-ul `Fritzi` și cheia lui, 802.11k/v pornit, cheile SSH și o
parolă de root de rezervă. Scriptul e generat pentru fiecare AP din setările capturate de
pe AP-ul respectiv, așa că parola de WiFi nu e tastată nicăieri.

## Flash-ul propriu-zis și ce am învățat din el

Trei lucruri care par evidente după aceea:

- **Un `mtd write` pornit în background moare imediat ce se închide sesiunea SSH.** Prima
  rulare părea că a mers și nu făcuse nimic: partiția de kernel era neatinsă, cu magic
  bytes intacți. Am rezolvat împachetând scrierea ca `( trap "" HUP; mtd … ) & wait`, ca
  să ignore `HUP`. Verifică citind înapoi exact lungimea imaginii, nu un număr rotunjit de
  blocuri, altfel primești un mismatch fals și o sperietură inutilă.
- **Outdoor+ revine cu alt MAC.** OpenWrt face bridge între ambele porturi Ethernet și ia
  adresa celui de-al doilea port, așa că AP-ul care era `80:…:d2:20` în rețea e acum
  `82:…:d2:20`. Am stat câteva minute convins că nu bootase, până m-am uitat după vecinul
  corect.
- **Verifică dacă imaginea e pentru placa respectivă înainte s-o scrii.** Când am derivat
  scriptul de flash al Pro-ului din cel al BZ2-ului, a rămas calea către imaginea BZ2, iar
  dry run-ul a pregătit liniștit o imagine de UAP pentru Pro. Asta l-ar fi brick-uit. Acum
  ambele scripturi citesc metadatele sysupgrade și refuză să scrie dacă nu apare acolo
  placa pentru care rulează.

La Outdoor+ a mai trebuit să limitez puterea de emisie la 10 dBm. Antena și amplificatorul
lui adaugă 10 până la 11 dB, iar limita UE pe 2,4 GHz e 20 dBm, așa că valoarea implicită
din OpenWrt l-ar fi dus mult peste.

## Ce aduce OpenWISP

Doar cu OpenWrt ar trebui să intri prin SSH pe trei AP-uri, pe rând.
[OpenWISP](https://openwisp.org) e cealaltă jumătate: un controller self-hosted, care
rulează în Docker pe serverul din casă și le administrează ca pe o flotă.

![Lista de dispozitive din OpenWISP cu UAP-942c, UAP-Outdoor-d220 și UAP-Pro-10a6, toate pe backend-ul OpenWrt, cu starea OK și configurația aplicată](openwisp-devices.png "Toate trei AP-urile în OpenWISP: stare OK, configurație aplicată. Adresele MAC sunt blurate.")

- Ai un singur dashboard pentru trei modele diferite. Vechiul controller UniFi vorbea doar
  cu hardware UniFi și rămăsese el însuși blocat la o versiune din 2021. Pe OpenWISP nu-l
  interesează ce dispozitiv e, doar să ruleze agentul.
- Fiecare AP raportează clienții WiFi asociați, traficul pe interfețe, load-ul, memoria,
  discul, vecinii și uptime-ul, cu grafice în timp. Asta e partea care îți lipsește imediat
  când renunți la un controller de la producător.
- Template-urile de config le scrii o dată și le trimiți pe toate AP-urile. `merge_config`
  păstrează setările proprii ale fiecărui dispozitiv, iar `test_config` aplică o schimbare,
  verifică dacă AP-ul mai e accesibil și face rollback automat dacă un push greșit te-ar fi
  lăsat pe dinafară. Agentul face polling la fiecare două minute.
- Cheile SSH sunt distribuite printr-un template, iar upgrade-urile de imagine se fac din
  același dashboard, în loc de trei `sysupgrade` manuale.
- Cu `usteer` pe fiecare AP, AP-urile își coordonează singure roaming-ul. Imediat după
  flash, UAP-ul găsise deja Pro-ul ca peer de steering, fără ajutor, așa că clienții trec
  de la un AP la altul dintre cele trei pe un singur SSID.

Pentru că tot stack-ul e open source, am putut să completez singur ce lipsea. Lista de
sesiuni WiFi din OpenWISP arăta clienții doar după adresa MAC, iar datele pentru hostname
și IP nu existau. Le-am adăugat cu un mic snooper DHCP/ARP pe AP-uri și câteva câmpuri pe
server, și le-am trimis ca branch-uri pe
[issue-ul upstream](https://github.com/openwisp/openwisp-monitoring/issues/629)
corespunzător. Cu un aparat închis aș fi deschis o cerere și aș fi așteptat.

![Lista de sesiuni WiFi din OpenWISP, cu coloanele de hostname, adresă IP și producător completate pentru clienții de pe UAP-942c și UAP-Pro-10a6](openwisp-wifi-sessions.png "Sesiuni WiFi cu hostname-uri și adrese IP, care vin de la snooper. Invertorul (SUN2000) a trecut pe 3 octombrie de pe UAP-942c pe Pro. Adresele MAC sunt blurate.")

## Ce mi-aș fi spus mie la început

- AP-urile UniFi de primă generație sunt target-uri OpenWrt ath79 standard, dar pe
  firmware stock 4.x le faci flash cu `mtd`, nu prin TFTP sau `fwupdate`, pentru că nu
  există partiție `rootfs` și u-boot verifică semnătura Ubiquiti.
- Construiește imagini pentru fiecare model cu ImageBuilder, ca un AP flash-uit să se
  configureze singur și să intre în controller. Nu configura trei cutii de mână.
- `usteer` are nevoie de `wpad-mbedtls` complet pentru 802.11v, iar puterea de emisie a
  lui Outdoor+ trebuie limitată pentru normele UE.
- OpenWISP e motivul pentru care merită să faci toate astea. Îți dă configurație centrală
  cu rollback automat, monitorizare reală, roaming pe toată flota și upgrade-uri de
  firmware, self-hosted și fără licență, pe hardware pe care producătorul îl trecuse deja
  la pierderi.
