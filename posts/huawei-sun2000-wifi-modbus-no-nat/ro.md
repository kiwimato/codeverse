---
title: Modbus cu un Huawei SUN2000 prin propriul lui WiFi, și de ce NAT-ul nu e o opțiune
description: Fără Smart Dongle, un Huawei SUN2000 vorbește Modbus-TCP doar pe AP-ul lui WiFi. Pentru Home Assistant a fost nevoie de un proxy cu login și fără NAT.
date: 2026-10-03
tags: homelab
image: inverter-and-battery.jpg
---

<!-- Notele sunt în en.md; ține cele trei limbi la fel când adaugi ceva. -->

Casa din România are un invertor Huawei SUN2000-8K-LC0 cu o baterie LUNA2000 și 11,8 kWp
de panouri. Cloud-ul Huawei, FusionSolar, arată ce produce, dar doar ca medii pe cinci
minute. Eu voiam valori live în Home Assistant și, mai târziu, să pot să-i spun bateriei
*când* să se încarce. Asta înseamnă Modbus-TCP, local.

![Un invertor Huawei SUN2000 alb pe un perete exterior, cu o baterie LUNA2000 așezată pe jos sub el](inverter-and-battery.jpg "SUN2000-8K-LC0 pe perete și bateria LUNA2000 sub el.")

Calea obișnuită e Smart Dongle-ul de la Huawei, care expune Modbus în rețeaua casei.
Invertorul ăsta nu are așa ceva. Are în schimb un access point WiFi integrat, gândit pentru
telefonul instalatorului la punerea în funcțiune, iar pe rețeaua aceea invertorul ascultă
pe portul **6607**. Mi-am propus să fac din access point-ul ăsta o legătură de date
permanentă și am dat de o serie de limitări care apar abia când chiar încerci.

## Cum ajungi în rețeaua invertorului

AP-ul invertorului e o lume mică și închisă: îi dă clientului o adresă din
`192.168.8.0/24`, invertorul însuși e `192.168.8.1` și nu există nicio rută în altă parte.
Home Assistant rulează în Docker pe un server Unraid din casă, care stă în LAN-ul obișnuit.
Trebuie ceva care să lege cele două rețele.

Planul evident e cel la care se gândește întâi orice inginer de rețea: pui un stick WiFi în
server, îl asociezi cu AP-ul invertorului și faci NAT din LAN prin el. Tot ce vrea să
vorbească cu invertorul trimite pachete la `192.168.8.1`, serverul le face masquerade pe
`wlan0` și gata.

Partea de TCP a planului merge perfect. SYN-ul pleacă, SYN-ACK-ul se întoarce, handshake-ul
se încheie, iar ping-urile stau constant la 2 ms. Apoi invertorul tace: fiecare request
Modbus primește ACK la nivel TCP și nu primește niciodată răspuns.

## Protocolul e Modbus, cu un login Huawei în față

Înainte să dau vina pe rețea trebuia să exclud protocolul, pentru că pe portul 6607 nu e
Modbus simplu. Folosește framing Modbus-TCP standard, dar pe AP-ul WiFi invertorul refuză
orice citire de registru cu o excepție până când clientul se autentifică. Login-ul e un
function code specific Huawei, `0x41`:

| pas | PDU | ce înseamnă |
|------|-----|---------|
| 1 | `41 24 01 00` | cere un challenge de 16 octeți |
| 2 | `41 25 <len> <client challenge> <user> <digest>` | login ca `installer` |

Digest-ul e `HMAC-SHA256(key = SHA256(password), message = inverter's challenge)`.
Excelenta bibliotecă Python [`huawei-solar`](https://github.com/wlcrs/huawei-solar-lib)
implementează toate astea, iar integrarea din Home Assistant o folosește.

Deci cu biblioteca potrivită și parola potrivită ar fi trebuit să meargă totul. Prin NAT n-a
mers: chiar și cererea de challenge, cu toți cei unsprezece octeți ai ei, dădea timeout de
fiecare dată.

## Fără NAT spre invertor

Ce a mers până la urmă a fost să scot complet NAT-ul de pe porțiunea dinspre invertor. Am
dat stick-ul WiFi direct unei VM, am lăsat VM-ul să se asocieze singur cu AP-ul și am rulat
biblioteca *pe mașina care deținea legătura WiFi*. Login-ul a reușit din prima, la fel și
toate citirile de registre de după.

De aici regula a devenit: **conexiunea TCP care ajunge la invertor trebuie să pornească de
pe mașina asociată cu access point-ul lui.** Orice e mai departe vorbește cu un *proxy* de
pe mașina aceea, iar proxy-ul deschide o conexiune nouă, a lui. Invertorul nu vede niciodată
un flux redirecționat sau translatat.

Aceleași teste au scos la iveală și a doua constrângere: invertorul răspundea doar unui
client cu adresa **`192.168.8.2`**. Cu un `.199` static, asocierea și TCP-ul erau în regulă,
iar invertorul tăcea la fel ca prin NAT. Unele dintre experimentele eșuate cu NAT au rulat
de pe altă adresă, așa că nu pot separa complet cele două efecte. În practică nu contează,
pentru că același design le rezolvă pe amândouă:

```
Home Assistant ──► proxy on the WiFi box :6607
                     │  fresh TCP, source 192.168.8.2
                     ▼
                   inverter 192.168.8.1:6607
```

Fluxurile translatate și redirecționate n-au primit niciodată răspuns, un socket nou de pe
`.2` a primit mereu, așa că m-am lăsat de șmecherii.

## Și proxy-ul trebuie să se autentifice

Primul proxy a fost un `socat` de o linie. Home Assistant tot nu putea adăuga invertorul, din
cauza ordinii pașilor: la configurare, integrarea citește numele modelului ca să-și dea seama
cu ce fel de dispozitiv vorbește, și face asta *înainte* de login. Invertorul ăsta refuză
citirea respectivă, așa că detecția eșuează și configurarea se oprește.

Soluția a fost ca proxy-ul să facă singur login-ul. Pentru fiecare conexiune care intră,
deschide o conexiune TCP nouă spre invertor, face challenge-ul și login-ul `0x41` și abia
apoi începe să paseze octeții în ambele direcții. Home Assistant primește o sesiune deja
autentificată, deci detecția și citirile merg. Sesiunea are drepturi de installer, așa că
merg și scrierile (modurile bateriei, programele time of use). Proxy-ul are sub o sută de
linii de `asyncio`, iar o buclă de shell îl repornește dacă se oprește vreodată.

## Limitări peste care am dat pe drum

### O singură sesiune Modbus, în total

Invertorul servește un singur client Modbus odată. Cât timp Home Assistant ține sesiunea, un
al doilea client (un script de test sau aplicația FusionSolar pe un telefon conectat la
același AP) fie e refuzat, fie îl dă afară pe Home Assistant. Integrarea scrie atunci în log
*„the inverter only supports one Modbus connection at a time”*. Avertismentul apare la orice
citire întreruptă, deci e un indiciu, iar cauza reală tot trebuie s-o cauți.

### Uneltele de rețea ale host-ului vor interfața aceea

Scripturile wireless ale Unraid pornesc un client DHCP pe orice interfață WiFi. AP-ul
invertorului nu răspunde la DHCP cum se așteaptă clientul ăsta, așa că el renunță, își pune
o adresă link-local `169.254.x.x`, iar `192.168.8.2` static dispare. Am rezolvat cu un mic
script de pază care ține `wlan0` în afara configurației daemon-ului DHCP și pune adresa la
loc dacă o șterge ceva. (Orice ai face, nu rula `dhcpcd` de mână pe `wlan0` pe mașina aceea.
El gestionează bridge-ul principal, iar eu am scos tot serverul din rețea până să aflu asta.)

### Un stick WiFi USB e un radio slab

Stick-ul ieftin de 2,4 GHz din server a avut zile proaste, între −67 și −73 dBm. Asta ajunge
ca să se asocieze și e prea puțin ca să rămână asociat. Din partea Home Assistant, o cădere a
legăturii arată exact ca o eroare Modbus, așa că primul lucru de verificat e mereu radioul:
`iw dev wlan0 link`.

### Motorul Modbus se poate bloca singur, și un reboot s-ar putea să nu-l repare

Cea mai derutantă defecțiune arată așa într-o captură de pachete: conexiunea se deschide,
cererea de login de unsprezece octeți pleacă, invertorul *o confirmă la nivel TCP* și apoi nu
mai răspunde deloc. Nici măcar o citire simplă de registru fără login nu primește înapoi
obișnuita excepție „autentifică-te întâi”; motorul tace complet. Asta se repetă la fiecare
cincisprezece secunde, ore în șir. WiFi-ul e în regulă, ping-urile sunt în regulă, DHCP-ul îi
dă în continuare stick-ului `192.168.8.2` și nu există alt client. Ca să fiu sigur că nu era
problema la mine, am încercat toate căile spre invertor una lângă alta: un socket simplu,
forwarder-ul `socat` și proxy-ul cu login. Toate au dat timeout la fel, deci ce era stricat
se afla pe `192.168.8.1`.

Primul instinct a fost să repornesc invertorul, și acolo am pierdut cel mai mult timp.
Oprirea și pornirea din aplicație n-au schimbat nimic. Ce m-a pus pe gânduri a fost că
clientul WiFi al serverului nu s-a reasociat niciodată, deci placa de comunicație rămăsese
pornită tot timpul. Așa că am mers mai departe: o oprire completă la rece, cu AC și DC
deconectate *și ambele baterii oprite* timp de câteva minute. De data asta placa chiar a
repornit (`wlan0` a căzut și a revenit), iar Modbus tot tăcea.

Până la urmă l-am readus fără niciun reboot. M-am conectat cu un telefon la WiFi-ul
`SUN2000-…` al invertorului și am intrat în aplicația SUN2000. În clipa în care s-a stabilit
sesiunea de management, Modbus a început să răspundă: întâi cu excepția „autentifică-te
întâi” pe care o tot reținuse, apoi, prin proxy, cu un login de installer curat și date live
în Home Assistant.

Ecranul local al aplicației SUN2000 vorbește cu invertorul prin protocolul de management
propriu al Huawei, care nu e Modbus. Dacă aplicația merge local, știi că placa e sănătoasă,
dar despre Modbus-TCP nu afli nimic. Iar când Modbus a amuțit de tot, îl trezește un login
local de management din aplicație, lucru pe care un power cycle nu-l face. Dacă se mai
întâmplă, intru o dată în aplicație și Home Assistant își revine singur.

## La ce folosește legătura

Cu sesiunea pornită, Home Assistant poate și să schimbe setări, pe lângă afișarea datelor.
Proxy-ul se autentifică cu drepturi de installer, așa că aceeași conexiune Modbus scrie
setările înapoi în invertor.

Prima folosire e bateria. Dintr-un singur dashboard setez modul de lucru (time of use, în
cazul meu), dacă bateria se poate încărca din rețea, puterea maximă de încărcare și de
descărcare, limitele de nivel de încărcare (SoC) la care se opresc încărcarea și descărcarea,
și programul time of use propriu-zis. Programul de mai jos descarcă bateria peste noapte și
dimineața, o încarcă între 13:00 și 16:30 și o descarcă din nou seara.

![Dashboard Home Assistant cu comenzi pentru baterie, un program time of use, un grafic al nivelului de încărcare pe șapte zile și un grafic de temperatură](ha-battery-control.png "Controlul bateriei în Home Assistant. Valorile din coloana din stânga se scriu în invertor. Observă golurile din jurul datelor de 2 și 3 octombrie.")

A doua folosire, mai puțin evidentă, e puterea reactivă. Invertorul se deconectează când
tensiunea rețelei în punctul de racordare ajunge la 253 V. Rețeaua locală e congestionată, iar
în jurul prânzului tensiunea la contorul meu urcă spre limita asta în majoritatea zilelor;
maximul orar a atins-o de mai multe ori numai în săptămâna asta. Înainte să ajungă acolo, o
curbă P(U) ar trebui să reducă puterea activă, iar o curbă Q(U) ar trebui să facă invertorul
să absoarbă putere reactivă. Asta trage tensiunea în jos și ține invertorul conectat, în loc
să intre într-o oprire de urgență. Ambele curbe sunt setări ale invertorului, deci le pot
regla din Home Assistant și pot urmări efectul pe același ecran.

![Dashboard Home Assistant cu tensiunea rețelei față de puterea activă și reactivă, plus tensiunea maximă și medie orară pe șapte zile, cu o linie de prag la 253 V](ha-grid-voltage.png "Tensiunea rețelei față de pragul de deconectare de 253 V. Invertorul merge pe curba Q-U.")

Faptul că totul trece prin WiFi-ul invertorului are un cost, și se vede în capturi. Legătura
cu AP-ul nu e mereu de încredere, iar când cade, cad și datele: graficul de temperatură are
goluri în jurul datelor de 2 și 3 octombrie, iar linia nivelului de încărcare pur și simplu
unește ultimul punct dinainte de gol cu primul de după. Un Smart Dongle în LAN-ul casei ar fi
probabil mai stabil. Deocamdată am decis să nu cumpăr unul, pentru că ce am e suficient de
stabil pentru mine.

## Următorul pas: să se ocupe un access point

Toate astea stau pe un server cu un stick USB atârnat de el, cea mai slabă verigă din lanț.
Casa are trei access point-uri UniFi vechi, din prima generație, trecute de curând pe OpenWrt
și administrate cu OpenWISP. Într-un prim test, unul dintre ele, un UAP-Pro, a prins
invertorul la −56 dBm, față de −63 dBm pentru stick-ul USB într-o zi bună, așa că planul e să
mut legătura cu invertorul acolo.

Regula fără NAT decide cum. Să asociezi AP-ul ca client și să faci masquerade din LAN prin el
e exact configurația care n-a primit niciodată răspuns, așa că AP-ul primește același
tratament ca serverul:

- radioul de 2,4 GHz se asociază cu invertorul ca station, cu `192.168.8.2` static și **fără
  gateway și fără DNS** pe interfața aceea, ca nimic din partea invertorului să nu poată
  prelua vreodată ruta default a AP-ului;
- un `socat` pe AP ascultă pe adresa lui din LAN, acceptă doar serverul Home Assistant și
  deschide o conexiune nouă spre `192.168.8.1:6607` *legată de* `192.168.8.2`;
- proxy-ul cu login de pe server țintește pur și simplu AP-ul în loc de `192.168.8.1`.

Nu există forwarding și nici masquerade; `ip_forward` rămâne oprit. Invertorul vede în
continuare exact o conexiune TCP nouă de pe `.2`.

Un detaliu de OpenWrt a contat mai mult decât mă așteptam. Un radio poate servi în același
timp un access point și un station, dar AP-ul depinde de station: de fiecare dată când
station-ul își pierde upstream-ul, AP-ul de pe radioul acela cade și el. AP-ul invertorului
nu e tocmai de încredere, așa că dacă ar fi împărțit radioul, WiFi-ul casei de pe AP-ul acela
ar clipi de fiecare dată când clipește cel al invertorului. De aceea radioul de 2,4 GHz e
dedicat legăturii cu invertorul, iar radioul de 5 GHz și celelalte două AP-uri duc rețeaua
casei.

Deocamdată am amânat mutarea, așa că stick-ul USB încă face treaba.

## Ce mi-aș fi spus mie la început

- Dacă invertorul n-are Smart Dongle, portul 6607 de pe WiFi-ul lui e Modbus-TCP adevărat, cu
  login de installer obligatoriu.
- Nu face niciodată NAT pe porțiunea care ajunge la invertor. Folosește un proxy și pornește
  conexiunea de pe `192.168.8.2`.
- Așteaptă-te la o singură sesiune Modbus. Orice alt client care se conectează te va costa
  date.
- Un ACK la nivel TCP fără răspuns Modbus înseamnă că problema e la invertor, iar rețeaua ta e
  în regulă. Înainte să ai încredere într-un „restart”, verifică dacă asocierea WiFi a
  rezistat.
- Dacă Modbus tace *complet* (niciun răspuns nici măcar la o citire fără autentificare), un
  power cycle s-ar putea să nu-l readucă. Un login local din aplicația SUN2000 îl readuce,
  pentru că e un alt protocol, care trezește stack-ul de management. Faptul că aplicația
  merge nu dovedește că Modbus funcționează.
