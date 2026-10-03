---
title: Controlul ventilatoarelor de carcasă pe un HP Z840 din Linux
description: Controllerul de ventilatoare din Z840 stă pe SMBus-ul privat al embedded controllerului, unde lm-sensors nu ajunge. hpz-ecfan îl comandă prin mailboxul din EC.
date: 2026-09-30
tags: opensource, homelab
---

<!-- Notele TODO sunt în en.md; ține cele trei limbi la fel când adaugi ceva. -->

HP Z840 e o stație de lucru serioasă, dar ventilatoarele de carcasă merg pe profilul ales
de BIOS la pornire, iar HP nu-ți dă nicio cale să-l schimbi din sistemul de operare, de
parcă n-ar avea nimeni vreodată nevoie de așa ceva.

Așa că mi-am scris singur una. [`hpz-ecfan`](https://github.com/kiwimato/hpz-ecfan) e un
tool mic în Python care mută curba ventilatoarelor pe stațiile de lucru din seria Z,
direct din Linux. N-ai nevoie de niciun modul de kernel, de reboot sau de patch de firmware.

## De ce uneltele obișnuite nu văd nimic

`lm-sensors` nu găsește niciun controller de ventilatoare, deci `fancontrol` n-are ce
controla. Driverul de kernel `adt7475`, care e exact driverul potrivit pentru cipul ăsta,
nu se atașează niciodată.

Cipul care comandă ventilatoarele de carcasă e un ON Semiconductor **NCT7491**, din
familia ADT7475, documentat în detaliu într-un datasheet public. Numai că nu stă pe
SMBus-ul controlat de PCH. Stă pe busul *privat* al embedded controllerului Nuvoton, iar
`i2c-i801` nu are cum să ajungă la el, așa că un cip cât se poate de standard ajunge să
fie de neatins.

O parte din el e expusă prin ACPI-ul și WMI-ul HP: driverul `hp-wmi-sensors` citește fără
probleme temperaturile și turațiile ventilatoarelor. Citirea e deci publică, scrierea nu.

## Mailboxul

Partea de scriere se putea recupera din modulul de firmware `HhmDxe` al HP, care
programează cipul la fiecare POST. Modulul trebuie să ajungă cumva la NCT7491 și o face
printr-un mic proxy SMBus aflat în fereastra de RAM a EC-ului.

Fereastra ocupă porturile I/O de la `0x800` până la `0x8FE`, iar pagina se selectează prin
`0x8FF`. Proxy-ul e în pagina 0:

| byte | semnificație |
|------|--------------|
| `0xE5` | adresa dispozitivului, pe 7 biți |
| `0xE6` | câți bytes se citesc înapoi (1 la citire, 0 la scriere) |
| `0xE7` | câți bytes se trimit după adresă (1: registrul, 2: registrul + data) |
| `0xE8` | date: registrul la citire, cu rezultatul întors pe loc; valoarea la scriere |
| `0xE9` | registrul la scriere |
| `0xF0` | bitul 0: scrii 1 ca să pornești, EC-ul îl șterge când termină |

Tot protocolul înseamnă două secvențe. O citire e `E5=dev, E8=reg, E7=1, E6=1, F0=1`, apoi
faci polling până când bitul 0 din `F0` coboară la zero și iei rezultatul din `E8`. O
scriere e `E5=dev, E8=val, E9=reg, E7=2, E6=0, F0=1`, cu același polling.

## Două lucruri pe care protocolul nu ți le dă

În primul rând, nu există niciun flag de eroare. Un NACK pe bus se termină exact ca un
succes: bitul 0 din `F0` se șterge, iar în `E8` rămâne ce era deja acolo. O citire eșuată
îți întoarce date vechi care arată perfect plauzibil. Singura apărare e să citești înapoi
fiecare scriere și să compari, iar tool-ul face asta la fiecare scriere.

În al doilea rând, nu există arbitrare. Mailboxul e doar o mână de bytes partajați. Două
procese care parcurg secvența în același timp își amestecă scrierile și își strică unul
altuia byte-ul de date, iar fără flag de eroare niciunul nu observă. De aceea fiecare
tranzacție ia un `flock` pe `/var/lock/ecmbox`. Calea o poți schimba cu `--lock` sau
`HPZ_EC_LOCK`, dar la lock în sine nu poți renunța.

## Fail-safe

Ar fi mai simplu de urmărit, și ai avea control precis, dacă ai scoate cipul din modul
automat și ai comanda direct duty-ul PWM. Atunci însă un crash al daemonului devine o
problemă termică.

Așa că tool-ul rămâne în bucla automată a cipului și mută doar forma curbei: pragul de jos
(`PWMmin`) sau cotul (`Tmin`). NCT7491 reglează mai departe după temperatură exact cum l-a
configurat BIOS-ul, doar cu alte valori. Dacă tool-ul crapă, e omorât sau mașina pierde
procesul cu totul, ventilatoarele continuă să se regleze singure, iar limitele THERM rămân
armate tot timpul.

Restul designului urmează aceeași regulă. Tool-ul refuză să scrie dacă bitul LOCK al
cipului e setat și refuză să ruleze deloc pe o mașină al cărei DMI product name nu e un
HP Z, dacă nu-i dai `--force`. Oriunde poate alege cum să eșueze, alege varianta care se
termină cu mai mult aer prin carcasă.

## Cum îl folosești

Doar biblioteca standard, Python 3.9 sau mai nou, licență MIT:

```
git clone https://github.com/kiwimato/hpz-ecfan
cd hpz-ecfan && pip install .
```

Apoi, ca root:

```
python3 -m hpz_ecfan.cli status
python3 -m hpz_ecfan.cli dump                 # registers 0x00-0x9F
python3 -m hpz_ecfan.cli set-min 3 0x60       # front fans (PWM3) floor to 37% duty
python3 -m hpz_ecfan.cli set-min 1 0x80       # rear fan 0 (PWM1)
python3 -m hpz_ecfan.cli set-tmin local 35    # start the curve earlier
python3 -m hpz_ecfan.cli log --interval 30
```

Pe Z840, tach1 și tach2 sunt ventilatoarele din spate, pe PWM1 și PWM2; tach3 și tach4
sunt perechea din față, comandate amândouă de PWM3. Tool-ul are nevoie de `/dev/port`, deci
de root sau de `CAP_SYS_RAWIO`, ceea ce înseamnă că merge fără probleme și dintr-un
container privilegiat.

Nimic nu supraviețuiește unui power cycle, care resetează atât EC-ul, cât și cipul la
valorile implicite din BIOS. Un reboot la cald rulează din nou POST-ul, care oricum
rescrie cipul. Tot ce setezi e o schimbare la runtime, deci mașina e mereu la un singur
reboot distanță de comportamentul din fabrică.

## Status

L-am testat live pe un Z840 cu BIOS M60 v02.56. Celelalte plăci din seria Z folosesc
foarte probabil același EC și același mailbox, dar s-ar putea să aibă ventilatoarele
legate la alte ieșiri PWM, așa că rulează `dump` și `status` și citește ce iese înainte să
scrii ceva. Rapoartele de pe alte plăci sunt binevenite.

Descrierea completă a protocolului, inclusiv jurnalul de verificare, e în
[`docs/protocol.md`](https://github.com/kiwimato/hpz-ecfan/blob/master/docs/protocol.md).
Informațiile despre registre vin din datasheet-ul public al ON Semiconductor, iar partea
de citire din tabelele ACPI ale HP; din codul HP nu e reprodus nimic.

**Repo:** [github.com/kiwimato/hpz-ecfan](https://github.com/kiwimato/hpz-ecfan)
