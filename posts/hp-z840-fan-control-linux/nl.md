---
title: De chassisventilatoren van een HP Z840 aansturen vanuit Linux
description: De ventilatorcontroller van de Z840 zit op de private SMBus van de embedded controller, buiten bereik van lm-sensors. hpz-ecfan praat ermee via de EC-mailbox.
date: 2026-09-30
tags: opensource, homelab
---

<!--
  Geschreven op basis van de README en docs/protocol.md van de repo zelf. Zie de
  Engelse versie voor de TODO's; houd beide talen gelijk als je iets toevoegt.
-->

De HP Z840 is een prima werkstation, maar de chassisventilatoren draaien op het profiel
dat de BIOS bij het opstarten koos. Vanuit het besturingssysteem kun je daar niets aan
veranderen; HP ging er blijkbaar van uit dat niemand dat zou willen.

Dus heb ik het zelf gebouwd. [`hpz-ecfan`](https://github.com/kiwimato/hpz-ecfan) is een
kleine Python-tool die vanuit Linux de ventilatorcurve van Z-serie werkstations verzet.
Je hebt er geen kernelmodule, herstart of firmwarepatch voor nodig.

## Waarom de normale gereedschappen niets zien

`lm-sensors` vindt geen ventilatorcontroller, dus `fancontrol` heeft niets om aan te
sturen. De `adt7475`-kerneldriver, de juiste driver voor deze chip, bindt nooit.

De chip achter de chassisventilatoren is een ON Semiconductor **NCT7491**, een onderdeel
uit de ADT7475-familie met een uitgebreide openbare datasheet. Alleen hangt hij niet aan
de SMBus van de PCH, maar aan de *private* bus van de Nuvoton embedded controller, en
`i2c-i801` kan daar niet bij. Een doodgewone chip dus, waar Linux toch niet aan kan komen.

Via HP's eigen ACPI en WMI kom je een eind: de `hp-wmi-sensors`-driver leest zonder
problemen temperaturen en toerentallen uit. Lezen is dus openbaar, schrijven niet.

## De mailbox

Hoe je schrijft, viel te achterhalen uit HP's `HhmDxe`-firmwaremodule, die de chip bij
elke POST programmeert. Die module moet de NCT7491 ook ergens bereiken, en dat doet hij
via een kleine SMBus-proxy in het RAM-venster van de EC.

Dat venster zit op de I/O-poorten `0x800` tot en met `0x8FE`, met paginaselectie via
`0x8FF`. In pagina 0 zit de proxy:

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
dezelfde poll. Meer zit er niet in het protocol.

## Twee dingen die het protocol je niet geeft

Ten eerste is er geen foutvlag. Een NACK op de bus eindigt precies zoals een succes: bit 0
van `F0` wordt gewist en in `E8` blijft staan wat er al stond. Een mislukte read geeft dus
oude data terug die er heel geloofwaardig uitziet. Je kunt je alleen indekken door elke
write terug te lezen en te vergelijken, en dat doet de tool bij elke write.

Ten tweede is er geen arbitrage. De mailbox is een handvol gedeelde bytes. Lopen twee
processen tegelijk door de reeks, dan lopen hun writes door elkaar en overschrijven ze
elkaars databyte, en omdat er geen foutvlag is merkt geen van beide dat. Elke transactie
neemt daarom een `flock` op `/var/lock/ecmbox` (het pad pas je aan met `--lock` of
`HPZ_EC_LOCK`). Die lock zelf is niet optioneel.

## Veilig falen

Je zou de chip uit zijn automatische modus kunnen halen en de PWM-duty zelf rechtstreeks
aansturen. Dat is makkelijker te overzien en je hebt precieze controle, maar dan wordt een
crashende daemon een thermisch incident.

De tool blijft daarom binnen de automatische regelkring van de chip en verzet alleen de
vorm van de curve: de bodem (`PWMmin`) of de knik (`Tmin`). De NCT7491 regelt gewoon zelf
op temperatuur, zoals de BIOS hem heeft ingesteld, alleen met andere getallen. Crasht de
tool, wordt hij gekilld of raakt de machine het proces helemaal kwijt, dan blijven de
ventilatoren gewoon regelen. De THERM-limieten blijven al die tijd actief.

Voor de rest geldt dezelfde regel. De tool schrijft niets als de LOCK-bit van de chip
gezet is, en draait helemaal niet op een machine waarvan de DMI-productnaam geen HP Z is,
tenzij je `--force` meegeeft. Overal waar hij kan kiezen hoe hij faalt, kiest hij de kant
met meer luchtstroom.

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
root of `CAP_SYS_RAWIO`. Daardoor draait hij ook prima in een privileged container.

Niets overleeft een stroomonderbreking, want die zet zowel de EC als de chip terug op de
BIOS-standaarden. Een warme herstart doorloopt POST opnieuw en herschrijft de chip toch al.
Alles wat je instelt is een runtime-wijziging, dus de machine is altijd maar één herstart
verwijderd van zijn fabrieksgedrag.

## Status

Ik heb het live getest op een Z840 met BIOS M60 v02.56. Andere Z-serie borden hebben
vrijwel zeker dezelfde EC en dezelfde mailbox, maar hun ventilatoren kunnen op andere
PWM-uitgangen zitten. Draai dus eerst `dump` en `status` en kijk wat eruit komt voordat je
iets schrijft. Meldingen van andere borden zijn welkom.

De volledige protocolbeschrijving, inclusief het verificatieverslag, staat in
[`docs/protocol.md`](https://github.com/kiwimato/hpz-ecfan/blob/master/docs/protocol.md).
De registerkennis komt uit de openbare datasheet van ON Semiconductor en de leeskant uit
HP's eigen ACPI-tabellen; er wordt geen code van HP overgenomen.

**Repo:** [github.com/kiwimato/hpz-ecfan](https://github.com/kiwimato/hpz-ecfan)
