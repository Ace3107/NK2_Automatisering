# NK2 Arbeidskrav 2 Automatisering av Cisco IOS

Dette prosjektet er et løsningsforslag for STUD1. Python med pySerial etablerer SSH og en fungerende management-vei via konsollkabel. Ansible bruker deretter SSH for å sette opp VLAN, trunker, ruting og DHCP. En separat playbook setter opp avtalt LACP EtherChannel til STUD2.

**Status:** Dette er et forberedt eksempel, ikke en påstand om at racktesten er gjennomført. Faktiske modeller, IOS-versjoner, porter og testresultater må fylles inn før innlevering. Bytt ut beskrivelsene med dine egne observasjoner og forklar valg med egne ord. Oppgaven krever individuell README.

## Forutsetninger og valg

- Fysisk Cisco-utstyr med IOS eller IOS XE, RSA/SSH-støtte og konsolltilgang. Packet Tracer-skissen brukes som koblingsgrunnlag; koden kjøres mot det fysiske utstyret.
- Eksemplet bruker to ISR-rutere og tre switcher. Kontroller grensesnittnavnene før første kjøring. STUD2 har andre navn i skissen, og kan ikke bruke STUD1-filene uendret.
- Dedikert labutstyr med ryddig konfigurasjon. Scriptet nullstiller ikke enhetene. Det kan endre eksisterende innstillinger på portene i variabelfilene.
- Laptop med Ethernet, Python og Linux/WSL for Ansible. På en stasjonær Windows-PC trengs bare Python, Git og konsollavhengighetene når den brukes til konsollsteget.
- Lokal konsollinnlogging må være fullført. Enheten skal vise `Switch>` eller `Switch#` / tilsvarende ruterprompt. Avslutt initial setup-dialogen, og vent på oppstart før du kjører scriptet.
- Bruk samme labbruker, SSH-passord og enable secret på alle fem enhetene for de oppgitte Ansible-kommandoene. Oppgis ved kjøring og lagres ikke i repoet.
- DHCP er aktivert som standard på IOS. Ruterplaybooken kontrollerer `no service dhcp` og aktiverer tjenesten hvis den er deaktivert.

Jeg har valgt statisk ruting fordi dette eksemplet bare har to rutere. R1 eier gateway og DHCP for VLAN 10; R2 eier gateway og DHCP for VLAN 20. Dette er ikke gateway-redundans. Oppgaven krever ikke HSRP. Det er heller ikke konfigurert internett/NAT. DNS-adressen 1.1.1.1 i poolene er et eksempel og virker ikke uten en vei til internett; intern DNS kan settes i variabelfilene.

## IP og VLAN plan

| Nett | Formål | Gateway | DHCP-eier | DHCP-adresser |
|---|---|---|---|---|
| 10.10.99.0/24, VLAN 99 | Øvre management | 10.10.99.1 | R1 | .50–.254 |
| 10.10.199.0/24, VLAN 199 | Nedre management | 10.10.199.1 | R1 | .50–.254 |
| 192.168.10.0/24, VLAN 10 | Klientnett 10 | 192.168.10.1 | R1 | .50–.254 |
| 192.168.20.0/24, VLAN 20 | Klientnett 20 | 192.168.20.1 | R2 | .50–.254 |

Management er statisk under oppsettet. Poolene for VLAN 99 og 199 er også inkludert for å dekke ordlyden «DHCP for hvert VLAN»; de statiske adressene er ekskludert.

| Enhet | Management-IP | Rolle |
|---|---|---|
| Laptop | 10.10.99.10/24 | Ansible-kontroller, statisk IP |
| SW-MGMT | 10.10.99.11/24 | Øverste switch, lag 2, default gateway R1 |
| R1 | 10.10.99.1/24 | Nedre VLAN 199: 10.10.199.1, klient-VLAN 10 |
| R2 | 10.10.99.2/24 | Nedre VLAN 199: 10.10.199.2, klient-VLAN 20 |
| SW-DIST | 10.10.199.11/24 | Switch mellom rutere og access-switch |
| SW-ACCESS | 10.10.199.12/24 | Klientporter og eventuell EtherChannel |

Ruterne har to forskjellige management-nett på øvre og nedre grensesnitt. R1 når VLAN 20 via 10.10.99.2, og R2 når VLAN 10 via 10.10.99.1. VLAN 10 og 20 termineres i dot1Q-subinterfaces på ruterne. DHCP trenger ikke relay her: ruterens DHCP-server har et grensesnitt direkte i VLAN-et den betjener.

## Kabling for STUD1

Navnene under er prosjektets egne navn, ikke Packet Tracers standardnavn.

| Fra | Til | Oppsett |
|---|---|---|
| Laptop Ethernet | SW-MGMT Gi1/0/3 | Access VLAN 99 |
| SW-MGMT Gi1/0/1 | R1 Gi0/0/1 | Access VLAN 99 på switch |
| SW-MGMT Gi1/0/2 | R2 Gi0/0/1 | Access VLAN 99 på switch |
| R1 Gi0/0/0 | SW-DIST Fa0/3 | Trunk VLAN 10,20,199 |
| R2 Gi0/0/0 | SW-DIST Fa0/4 | Trunk VLAN 10,20,199 |
| SW-DIST Fa0/2 | SW-ACCESS Fa0/3 | Trunk VLAN 10,20,199 |
| SW-ACCESS Fa0/1 | Testklient i VLAN 10 | Access VLAN 10 |
| SW-ACCESS Fa0/2 | Testklient i VLAN 20 | Access VLAN 20 |
| SW-ACCESS Fa0/4 og Fa0/5 | Avtalte porter på STUD2 | Valgfri LACP Port-channel1 |

Skissen viser klienter på tvers av studentenes områder. Det er switchportens VLAN som bestemmer nettverket, ikke hvor klienten er tegnet. Klientene kan derfor testes lokalt først, og på tvers etter at EtherChannel fungerer.

## Filene i prosjektet

| Fil eller mappe | Bruk |
|---|---|
| `scripts/setup_ssh.py` | Konsolloppsett, brukerinput og management-forbindelse |
| `inventory/hosts.yml` | SSH-adressene til enhetene |
| `inventory/group_vars/ios.yml` | Felles tilkobling, VLAN og EtherChannel-aktivering |
| `inventory/host_vars/` | Enhetens porter, bootstrap-IP, gateways, DHCP og ruter |
| `playbooks/01_precheck.yml` | SSH-test, modell og IOS-versjon |
| `playbooks/02_switches.yml` | VLAN, trunker og klientporter |
| `playbooks/03_routers.yml` | Klient-subinterfaces, statiske ruter og DHCP |
| `playbooks/04_etherchannel.yml` | Avtalt EtherChannel til STUD2 |
| `playbooks/05_verify.yml` | Status, SSH 2-test og ping med feil ved manglende svar |
| `playbooks/site.yml` | Precheck, switcher, rutere og verifisering i rekkefølge |
| `playbooks/tasks/` | Gjenbrukbare oppgaver for switcher og rutere |
| `docs/STEG_FOR_STEG.md` | Detaljert arbeidsrekkefølge og Git-flyt |
| `docs/TESTRESULTATER.md` | Skjema for egne faktiske testresultater |
| `tests/test_project.py` | Lokale tester av kommandoer og variabler |

## 1 Hent prosjektet og installer avhengigheter

Opprett ditt eget offentlige GitHub-repo og last opp prosjektfilene. Bytt `<REPO-URL>` med den virkelige lenken.

På laptoppen i Ubuntu/WSL, fra en Linux-mappe som `~/nk2-automatisering`:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git openssh-client
# Dersom Python 3 er eldre enn 3.11: installer en støttet Python først.
git clone <REPO-URL> nk2-automatisering
cd nk2-automatisering
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
ansible-galaxy collection install -r collections/requirements.yml
ansible --version
ansible-galaxy collection list
```

Kjør alle Ansible-kommandoer fra repoets rotmappe. `ansible.cfg` finner inventory automatisk. Ansible 2.19 krever Python 3.11 eller nyere. Et Windows-filsystem som `/mnt/c/...` kan gjøre at Ansible ignorerer konfigurasjon i en skrivbar mappe; bruk derfor Linux-hjemmemappen.

På Windows-maskinen som har konsollkabelen:

```powershell
git clone <REPO-URL> nk2-automatisering
cd nk2-automatisering
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-console.txt
.\.venv\Scripts\python.exe -m serial.tools.list_ports -v
```

På Linux er tilsvarende portliste `python -m serial.tools.list_ports -v`. Bruk den faktiske porten. COM3 oversettes ikke automatisk til `/dev/ttyS3`. USB-adaptere vises ofte som `/dev/ttyUSB0` eller `/dev/ttyACM0`. Ved permission denied på Ubuntu: legg brukeren i `dialout` med `sudo usermod -aG dialout "$USER"` og logg ut og inn. Detaljer avhenger av distro.

## 2 Tilpass variabler før du kobler opp

1. Kontroller portene fysisk og med `show ip interface brief` i konsollen.
2. Endre grensesnittnavnene i `inventory/host_vars/` hvis racket avviker fra tabellen.
3. Hvis IP-planen endres, oppdater også inventory, ruterens next-hop, DHCP-poolene, testmålene og laptop-IP/ruten.
4. Kontroller at management ikke overlapper andre labnett.
5. La `shared_etherchannel_enabled: false` stå til nabostudentens oppsett er avklart.

Bruker og passord er input. Porter, VLAN og adresser ligger i YAML fordi de skal kunne versjoneres og endres uten å skrive om oppgavene. Ikke legg passord i offentlige YAML-filer. Ved behov for forskjellige passord per enhet kan du senere bruke Ansible Vault.

## 3 Kjør Python via konsoll på alle enhetene

Koble Ethernet som i tabellen. Koble konsollkabelen til én enhet om gangen. Åpne en terminal for å kontrollere riktig port/baudrate og IOS-prompt, og **lukk terminalen igjen** før Python åpner porten.

Windows-eksempel, bytt COM3 til faktisk port og kjør de fem kommandoene mens kabelen flyttes:

```powershell
.\.venv\Scripts\python.exe scripts/setup_ssh.py --host inventory/host_vars/SW-MGMT.yml --port COM3
.\.venv\Scripts\python.exe scripts/setup_ssh.py --host inventory/host_vars/R1.yml --port COM3
.\.venv\Scripts\python.exe scripts/setup_ssh.py --host inventory/host_vars/R2.yml --port COM3
.\.venv\Scripts\python.exe scripts/setup_ssh.py --host inventory/host_vars/SW-DIST.yml --port COM3
.\.venv\Scripts\python.exe scripts/setup_ssh.py --host inventory/host_vars/SW-ACCESS.yml --port COM3
```

Linux-eksempel:

```bash
python scripts/setup_ssh.py --host inventory/host_vars/R1.yml --port /dev/ttyUSB0
```

Scriptet spør om SSH-bruker, SSH-passord og nytt enable secret. Dersom enheten står i bruker-EXEC og krever et eksisterende enable-passord, spør det om dette separat. Baudrate er 9600 som standard; bruk `--baud 115200` bare når enhetens konsoll er satt til dette.

Scriptet oppretter hostname, domene og lokal privilege-15-bruker, management-IP og nødvendig VLAN/trunk for VLAN 199, RSA-nøkler hvis de mangler, SSH versjon 2, lokal VTY-innlogging og lagrer konfigurasjonen. Eksisterende RSA-nøkler beholdes; kontroller at de er minst 2048 bit. Scriptet oppdager VTY-ranges i running-config og setter lokal innlogging og kun SSH på alle disse. Det stopper ved kjente IOS-feil og timeout. Det ruller ikke tilbake kommandoer som allerede er utført. Ikke kjør bootstrap igjen etter full Ansible-konfigurasjon uten grunn: bootstrap setter trunkens tillatte liste tilbake til bare management-VLAN.

**Python og Ansible henger sammen gjennom management-IP-ene:** Python etablerer både SSH og nettverksveien som inventory bruker. Uten dette kan ikke Ansible gjøre sitt første SSH-kall. Det er ikke nødvendig å finne på en ekstra Python-løsning for VLAN/DHCP når IOS-modulene kan gjøre jobben.

## 4 Sett laptop-IP og kontroller SSH

Sett Ethernet på laptoppen til `10.10.99.10`, maske `255.255.255.0`. Gateway kan være `10.10.99.1` hvis Ethernet bare brukes til lab. Hvis Wi-Fi brukes til internett samtidig, la Ethernet-default-gateway stå tom og legg inn en egen labrute.

Windows PowerShell som administrator, for labruten:

```powershell
route add 10.10.199.0 mask 255.255.255.0 10.10.99.1
```

På en ren Linux-laptop, etter at Ethernet har fått IP:

```bash
sudo ip route replace 10.10.199.0/24 via 10.10.99.1
```

På Windows/WSL2 settes fysisk Ethernet og labruten i Windows. Test fra WSL også, siden Ansible kjører der. På kompatibel Windows 11 kan WSL mirrored networking brukes om standard NAT ikke når labnettet. Ikke legg blindt Windows-ruten på WSLs virtuelle Ethernet; verifiser med `ip route get 10.10.199.11` og SSH.

Fra Linux/WSL-miljøet som kjører Ansible, logg inn på alle fem én gang. Bytt `labadmin` med brukeren du valgte og bekreft enhetens host key etter kontroll:

```bash
ssh labadmin@10.10.99.1
ssh labadmin@10.10.99.2
ssh labadmin@10.10.99.11
ssh labadmin@10.10.199.11
ssh labadmin@10.10.199.12
```

Skriv `exit` på hver enhet før neste innlogging. Dette registrerer host keys i riktig miljø; en innlogging i Windows fyller ikke nødvendigvis WSLs known_hosts. Ved nyinstallert enhet med endret nøkkel, kontroller at det er riktig enhet før du fjerner den gamle nøkkelen med `ssh-keygen -R <IP>`.

## 5 Kjør Ansible i rekkefølge

```bash
source .venv/bin/activate
ansible-inventory --graph
ansible-playbook playbooks/site.yml --syntax-check
ansible-playbook playbooks/01_precheck.yml -u labadmin -k -K
ansible-playbook playbooks/02_switches.yml -u labadmin -k -K
ansible-playbook playbooks/03_routers.yml -u labadmin -k -K
ansible-playbook playbooks/05_verify.yml -u labadmin -k -K
```

`-u` velger SSH-bruker, `-k` spør om SSH-passord, og `-K` spør om enable secret. Tilkoblingen er `network_cli`, og become-metoden er `enable`, ikke Linux-sudo på Cisco-enheten.

Samlet kjøring ved senere bruk:

```bash
ansible-playbook playbooks/site.yml -u labadmin -k -K
```

Backup av running-config tas før endringer og lagres i `backups/`. Status lagres i `results/`. Begge er ignorert av Git; backup kan inneholde passordhash og skal ikke publiseres. Endret running-config lagres som startup-config. Konfigurasjon er additiv: gamle VLAN, gamle pooler og gamle ruter fjernes ikke automatisk når du sletter dem fra YAML.

## 6 Sett opp EtherChannel etter avtale

Denne playbooken er skilt fra `site.yml` fordi den endrer en forbindelse til nabostudentens utstyr. Uten en naboswitch kan du teste egen side; du kan ikke dokumentere en fungerende tosidig EtherChannel alene uten å koble opp en ekstra switch.

Avtal medlemsporter, VLAN-listen `10,20,199`, native VLAN (default 1 på begge i dette eksemplet), LACP active/active eller active/passive, og unike management-IP-er. Bruk aldri klientinnstillinger med PortFast/BPDU Guard på EtherChannel. Rydd eventuell gammel channel-group-konfigurasjon på de avtalte portene før første kjøring.

**DHCP-eierskap må avtales:** I det selvstendige STUD1-eksemplet betjener R1 VLAN 10 og R2 VLAN 20. Hvis STUD2 skal eie VLAN 20 etter sammenkobling, må STUD1s VLAN20-gateway/pool fjernes eller endres før forbindelsen aktiveres. To rutere må ikke bruke samme gateway-IP, og pooler må ikke dele overlappende adresser. Å redigere YAML fjerner ikke gammel konfigurasjon. Utfør eksplisitt avtalt migrering via konsoll/egen endringsplaybook først. På et felles VLAN 199 må alle SVI- og ruteradresser også være unike.

Etter avtale og ferdig konfigurert andre ende:

```bash
ansible-playbook playbooks/04_etherchannel.yml -u labadmin -k -K -e shared_etherchannel_enabled=true
ansible-playbook playbooks/05_verify.yml -u labadmin -k -K
```

Kontroller `show etherchannel summary` på begge ender. For et lag-2-bundle forventes `Po1(SU)` og to medlemsporter merket `(P)`. Ping mellom klienter i samme VLAN på hver side tester at trafikk passerer. EtherChannel er ikke verifisert bare fordi playbooken er grønn.

## Hvordan læreren kan teste

Læreren trenger labtilgang, oppgitt brukernavn/passord via en separat kanal, riktig Ethernet-IP/rute og de fysiske enhetene. GitHub-repoet alene inneholder ikke et kjørende nettverk.

1. Clone repoet, installer avhengigheter og collections, og sammenlign faktisk kabling/portnavn med tabellen.
2. Ved test fra ukonfigurerte enheter: gå gjennom konsollsteget på alle fem. Ved test av eksisterende oppsett: hopp over bootstrap og test SSH direkte.
3. Kjør `01_precheck.yml`. Alle fem skal nås; modell og versjon skal passe filene.
4. Kjør `site.yml`. Forvent `unreachable=0` og `failed=0`. Dette beviser ikke alene klient-DHCP eller EtherChannel.
5. Sett én klient på hver accessport og velg DHCP. På Windows brukes `ipconfig /release`, `ipconfig /renew` og `ipconfig /all`. VLAN10-klienten skal få 192.168.10.50–254 /24, gateway .1; VLAN20-klienten 192.168.20.50–254 /24, gateway .1 i sitt nett. `show ip dhcp binding` på riktig ruter skal vise klientens adresse/MAC. Tom binding før en klient har spurt er normalt.
6. Ping egen gateway fra begge klienter, deretter den andre VLAN-gatewayen og den andre klienten. Klientens brannmur må tillate ICMP for klient-til-klient-testen. Manglende internett/DNS er ikke feil ved denne isolerte labløsningen.
7. Kjør `05_verify.yml`. Playbooken krever SSH 2 og 100 % svar på definerte pingmål. Undersøk også statusfilene manuelt: riktige access-VLAN, trunklisten og forventede ruter/DHCP-pooler.
8. Kjør switch- og ruterplaybookene en gang til. Uendret konfigurasjon skal normalt gi `changed=0`. Ved stadig endring: kontroller oppgaven mot den eksakte teksten i `show running-config`, siden IOS-versjoner kan normalisere kommandoer forskjellig. Lokale rapportfiler i verify er ikke en del av konfigurasjonsidempotensen.
9. Dersom EtherChannel inngår: kjør steg 6 ovenfor, verifiser `SU`/`P` på begge ender og ping mellom klienter i samme VLAN over linken. Trekk ut én medlemskabel, gjenta ping og observer at port-channel fortsatt er oppe. Sett kabelen tilbake.
10. Dokumenter resultatene i `docs/TESTRESULTATER.md` med dato, modell, IOS-versjon, kommando og observasjon. Ikke kryss av tester som ikke er gjennomført.

CLI-kommandoer læreren kan bruke i privilegert EXEC:

```text
show ip ssh
show running-config | section line vty
show crypto key mypubkey rsa
show ip interface brief
show vlan brief
show interfaces trunk
show etherchannel summary
show ip route
show ip dhcp pool
show ip dhcp binding
show startup-config
```

VLAN/trunk/EtherChannel-kommandoene brukes på switcher; route/DHCP på rutere. Kontroller alle VTY-ranges hvis enheten har flere enn 0–4. Det skal stå `login local` og `transport input ssh` på hver range som scriptet fant.

## Feilsøking og vedlikehold

| Symptom | Kontroller |
|---|---|
| Konsollport opptatt | Lukk PuTTY/Tera Term/andre prosesser |
| Ingen IOS-prompt | Riktig port, baudrate, driver, setup-dialog og innlogging |
| IOS avviser kommando | Modell, fullstendig portnavn og støtte for syntaksen |
| SVI down/down | VLAN finnes, SVI aktivert og minst én aktiv port fører VLAN-et |
| Øvre SSH virker, nedre ikke | Laptoprute, R1 subinterface199, trunk199 og SVI/default gateway |
| SSH host key-feil | Registrer riktig nøkkel i WSL/Linux, kontroller før nøkkelbytte |
| Eldre SSH-algoritmer avvist | Kontroller IOS-versjon og støtte; oppdater IOS der mulig. Eventuelle labunntak må begrenses til aktuell enhet og dokumenteres |
| DHCP mangler | VLAN-port, trunk, riktig subinterface, pool, service dhcp, ledige adresser |
| Ping virker bare én vei | Returrute og klientbrannmur |
| EtherChannel ikke samlet | Samme trunk/native/allowed-oppsett, riktig LACP og medlemsporter på begge ender |
| Gjentatt changed | Sammenlign fulle kommandoer med IOS sin running-config |

For å legge til en ny enhet: legg den i inventory, opprett en host_vars-fil med riktig rolle og adresser, kjør bootstrap på den, og test med `--limit <enhet>`. Testmål og VLAN må også tilpasses.

## Lokale kodekontroller

Disse kan kjøres uten racket etter at avhengighetene er installert:

```bash
python -m unittest discover -s tests -v
ansible-playbook playbooks/site.yml --syntax-check
ansible-playbook playbooks/04_etherchannel.yml --syntax-check
```

Testene kontrollerer blant annet at inventory stemmer med bootstrap-IP, at management-nettene ikke overlapper, at poolene har én eier, og at konsollscriptet avviser feil input og kjente IOS-feil. De erstatter ikke test på fysisk utstyr.

## Referanser

- Oppgavedokument: NK2 Arbeidskrav 2 Automatisering, vedlagt av studenten.
- pySerial: https://pyserial.readthedocs.io/en/latest/shortintro.html
- Cisco IOS collection: https://docs.ansible.com/projects/ansible/latest/collections/cisco/ios/index.html
- ios_config og idempotens: https://docs.ansible.com/projects/ansible/latest/collections/cisco/ios/ios_config_module.html
- IOS network_cli og enable: https://docs.ansible.com/projects/ansible/latest/network/user_guide/platform_ios.html

Avhengighetene i prosjektet er låst til angitte collections og et avgrenset ansible-core-versjonsområde. Før innlevering skal de faktiske installerte versjonene og racktestene dokumenteres.
