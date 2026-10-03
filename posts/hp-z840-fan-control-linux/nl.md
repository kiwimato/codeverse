---
title: De chassisventilatoren van een HP Z840 aansturen vanuit Linux
description: De ventilatorcontroller van de Z840 hangt aan de private SMBus van de embedded controller, waar lm-sensors niet bij kan. hpz-ecfan bereikt hem via de mailbox van de EC zelf.
date: 2026-09-30
tags: opensource, homelab
---

<!--
  Geschreven op basis van de README en docs/protocol.md van de repo zelf. Zie de
  Engelse versie voor de TODO's; houd beide talen gelijk als je iets toevoegt.
-->

Sommige problemen bestaan alleen omdat een fabrikant besloot dat jij ze niet hoefde op te
lossen. De HP Z840 is er zo een: een prima werkstation waarvan de chassisventilatoren
draaien op het profiel dat de BIOS bij het opstarten koos, zonder enige manier om daar
vanuit het besturingssysteem iets anders van te vinden.

Dus heb ik die manier geschreven. [`hpz-ecfan`](https://github.com/kiwimato/hpz-ecfan) is
een kleine Python-tool die de ventilatorcurve van Z-serie werkstations verzet vanuit
Linux — zonder kernelmodule, zonder herstart, zonder firmwarepatch.

## Waarom de normale gereedschappen niets zien

De voor de hand liggende aanpak strandt meteen. `lm-sensors` vindt geen
ventilatorcontroller. `fancontrol` heeft niets om aan te sturen. De `adt7475`-kernel­driver,
precies de juiste driver, koppelt nooit aan.

Dat ligt aan de topologie. De chip die de chassisventilatoren aanstuurt is een ON
Semiconductor **NCT7491** — een onderdeel uit de ADT7475-familie, uitgebreid beschreven in
een openbare datasheet. Maar hij hangt niet aan de SMBus die de PCH beheert. Hij hangt aan
de *private* bus van de Nuvoton embedded controller, en `i2c-i801` heeft daar geen route
naartoe. De chip zit er gewoon, volledig standaard, en volstrekt onbereikbaar.

HP's eigen ACPI en WMI laten een deel van het beeld zien — de `hp-wmi-sensors`-driver leest
moeiteloos temperaturen en toerentallen. De leeskant is openbaar. De schrijfkant niet.

## De mailbox

De schrijfkant bleek te achterhalen uit HP's `HhmDxe`-firmwaremodule, die de chip bij elke
POST programmeert. Die moet de NCT7491 op de een of andere manier bereiken, en het
mechanisme dat hij gebruikt is een kleine SMBus-proxy in het RAM-venster van de EC.

Dat venster zit op de I/O-poorten `0x800`–`0x8FE`, met paginaselectie via `0x8FF`. Pagina 0
bevat de proxy:

| byte | betekenis |
|------|-----------|
| `0xE5` | 7-bits apparaatadres |
| `0xE6` | terug te lezen bytes (1 bij lezen, 0 bij schrijven) |
| `0xE7` | te versturen bytes na het adres (1: register, 2: register + data) |
| `0xE8` | data: register bij lezen, met het resultaat op dezelfde plek terug; waarde bij schrijven |
| `0xE9` | register bij schrijven |
| `0xF0` | bit 0: schrijf 1 om te starten, de EC wist het bij voltooiing |

Lezen is `E5=dev, E8=reg, E7=1, E6=1, F0=1`, daarna pollen tot bit 0 van `F0` laag wordt en
het resultaat uit `E8` halen. Schrijven is `E5=dev, E8=val, E9=reg, E7=2, E6=0, F0=1` met
dezelfde poll. Dat is het hele protocol.

## Twee dingen die het protocol je niet geeft

**Er is geen foutvlag.** Een NACK op de bus eindigt precies als een succes: bit 0 van `F0`
wordt gewist en `E8` blijft staan op wat er al stond. Een mislukte lezing levert verouderde
data op die er volkomen geloofwaardig uitziet. De enige verdediging is elke schrijfactie
terugleggen en vergelijken — en dat doet de tool, zonder uitzondering.

**Er is geen arbitrage.** De mailbox is een handvol gedeelde bytes. Twee processen die
tegelijk door de reeks lopen, verweven hun schrijfacties en verminken elkaars databyte, en
door de ontbrekende foutvlag merkt geen van beide het. Elke transactie gaat daarom door een
`flock` op `/var/lock/ecmbox` (te overschrijven met `--lock` of `HPZ_EC_LOCK`). Dat is niet
optioneel.

## Falen richting koud

Het verleidelijke ontwerp is om de chip uit zijn automatische modus te halen en de
PWM-duty rechtstreeks aan te sturen. Dat is eenvoudiger te doorgronden en geeft nauwkeurige
controle. Het is ook de verkeerde keuze, want het maakt van een crashende daemon een
thermisch incident.

In plaats daarvan blijft de tool binnen de automatische regelkring van de chip en verzet
alleen de vorm van de curve: de bodem (`PWMmin`) of de knik (`Tmin`). De NCT7491 blijft
gewoon zelf temperatuurgestuurd regelen zoals de BIOS hem heeft ingesteld — hij rekent
alleen met andere getallen. Gaat de tool onderuit, wordt hij afgeschoten, of raakt de
machine het proces volledig kwijt, dan blijven de ventilatoren regelen. De THERM-limieten
blijven de hele tijd scherp staan.

De rest volgt dezelfde regel. De tool weigert te schrijven als de LOCK-bit van de chip
gezet is. Hij weigert überhaupt te draaien op een machine waarvan de DMI-productnaam geen
HP Z is, tenzij je `--force` meegeeft. Bij elke faalrichting die hij kan kiezen, kiest hij
de richting die op méér luchtstroom uitkomt in plaats van minder.

## Gebruik

Alleen de standaardbibliotheek, Python 3.9 of nieuwer, MIT-licentie:

```
git clone https://github.com/kiwimato/hpz-ecfan
cd hpz-ecfan && pip install .
```

Daarna, als root:

```
python3 -m hpz_ecfan.cli status
python3 -m hpz_ecfan.cli dump                 # registers 0x00-0x9F
python3 -m hpz_ecfan.cli set-min 3 0x60       # voorste ventilatoren (PWM3) naar 37% duty
python3 -m hpz_ecfan.cli set-min 1 0x80       # achterste ventilator 0 (PWM1)
python3 -m hpz_ecfan.cli set-tmin local 35    # laat de curve eerder beginnen
python3 -m hpz_ecfan.cli log --interval 30
```

Op de Z840 zijn tach1 en tach2 de achterste ventilatoren op PWM1 en PWM2; tach3 en tach4
zijn het voorste paar, allebei aangestuurd door PWM3. De tool heeft `/dev/port` nodig, dus
root of `CAP_SYS_RAWIO` — wat ook betekent dat hij prima draait vanuit een privileged
container.

Niets overleeft een stroomonderbreking: die zet zowel de EC als de chip terug op de
BIOS-standaarden. Een warme herstart doorloopt POST opnieuw, en die herschrijft de chip
sowieso. Wat je instelt is een wijziging tijdens de rit, wat een andere manier is om te
zeggen dat de machine nooit verder dan één herstart van zijn fabrieksgedrag af staat.

## Status

Live getest op een Z840 met BIOS M60 v02.56. Andere Z-serie borden delen vrijwel zeker
dezelfde EC en dezelfde mailbox, maar hebben hun ventilatoren mogelijk op andere
PWM-uitgangen zitten — draai `dump` en `status` en lees wat eruit komt voordat je iets
schrijft. Meldingen van andere borden zijn welkom.

De volledige protocolbeschrijving, inclusief het verificatieverslag, staat in
[`docs/protocol.md`](https://github.com/kiwimato/hpz-ecfan/blob/master/docs/protocol.md).
De registerkennis komt uit de openbare datasheet van ON Semiconductor en de leeskant uit
HP's eigen ACPI-tabellen; er wordt geen code van HP overgenomen.

**Repo:** [github.com/kiwimato/hpz-ecfan](https://github.com/kiwimato/hpz-ecfan)
