# Steg for steg fra konsollkabel til GitHub innlevering

Dette er arbeidsrekkefølgen for STUD1-eksemplet. Alle playbooks og variabelfiler følger med prosjektet; README har IP-planen, kablingen og alle kjørekommandoene. Tilpass portene før bruk.

## Steg 1 Opprett repo og åpne i VS Code

Pakk ut prosjektet. Opprett et tomt offentlig GitHub-repo uten forhåndslagde filer. Åpne prosjektmappen i VS Code. Installer Git og konfigurer ditt eget navn og e-post lokalt hvis dette ikke allerede er gjort.

Kjør i prosjektmappen, erstatt repo-URL:

```bash
git init
git add .
git commit -m "Legg til konsollbootstrap og Ansible for NK2"
git branch -M main
git remote add origin <REPO-URL>
git push -u origin main
```

GitHub-innlogging må være satt opp på maskinen. Det er ikke opprettet eller publisert noe GitHub-repo av dette prosjektforslaget.

## Steg 2 Kontroller utstyret før du skriver konfigurasjon

Merk to rutere R1/R2, øvre switch SW-MGMT, midtre SW-DIST og nedre SW-ACCESS. Skriv ned modeller og IOS-versjoner. Kontroller om ruternes faktiske navn er Gi0/0/0 og Gi0/0/1 eller noe annet. Endre host_vars og porttabellen i README samtidig.

Avtal STUD-side og bruk av rack med medstudenten. Avtal at forbindelsen mellom studentene holdes frakoblet til VLAN, EtherChannel, adresser og DHCP-eierskap er avklart.

## Steg 3 Installer på begge konsollmaskinene

Laptop og stasjonær kan hente samme kode med `git clone`. Python og konsollavhengighetene må installeres på begge. Bruk Windows-Python på maskinen som har COM-porten. Installer Ansible bare i laptopens Linux/WSL-miljø, som beskrevet i README.

Hvis du har samme repo i Windows og WSL, er dette to separate arbeidskopier. Commit/push/pull gjelder også mellom disse.

## Steg 4 Gjør YAML til din egen plan

Åpne `inventory/hosts.yml`, `group_vars/ios.yml` og alle fem host_vars-filer. Forklar for deg selv hvilken IP som brukes for SSH, hvilke porter som er trunk og hvilken ruter som er DHCP-server for hvert VLAN. Juster filer og dokumentasjon til det faktiske racket.

## Steg 5 Koble Ethernet og konfigurer SW-MGMT via konsoll

Koble laptopens Ethernet til øvre switch og begge rutere til de andre oppgitte portene. Kjør `setup_ssh.py` for SW-MGMT. Sett laptop-IP til 10.10.99.10/24. Test switchens SSH-IP 10.10.99.11.

## Steg 6 Konfigurer R1 og R2 via konsoll

Flytt konsollkabelen og kjør scriptet med riktig host_vars-fil for hver ruter. Scriptet setter management øverst og VLAN199-subinterface nederst. Test SSH til 10.10.99.1 og .2. Bruk den stasjonære hvis det er der konsollkabelen er tilgjengelig; laptopens Ethernet kan bli stående.

## Steg 7 Konfigurer SW-DIST og SW-ACCESS via konsoll

Flytt kabelen igjen og kjør scriptet for hver switch. Det oppretter management-SVI, default gateway og VLAN199-trunker. Legg inn laptopens rute til 10.10.199.0/24 via R1. Test SSH til .11 og .12 i dette nettet, også fra WSL.

## Steg 8 Bytt til Ansible på laptoppen

Konsollscriptet er nå ferdig. Laptopens nettverkstilkobling er nok til resten. Registrer host keys i WSL/Linux ved SSH-innlogging på alle fem. Kjør syntax-check og `01_precheck.yml`. Stopp og løs SSH/portproblemer hvis en enhet ikke nås.

## Steg 9 Kjør switchplaybooken

`02_switches.yml` oppretter VLAN10/20/199 på de nedre switchene, utvider trunklistene og setter accessporter. Den tar lokal backup før endringer og lagrer konfigurasjonen. Øvre switch har allerede management-oppsett fra Python; den får ikke klient-VLAN eller inter-VLAN-ruting.

## Steg 10 Kjør ruterplaybooken

`03_routers.yml` lager klient-subinterfaces, statiske ruter, DHCP-exclusions og DHCP-pooler. Poolene hentes fra host_vars-listene. Playbooken aktiverer også DHCP-tjenesten hvis den var deaktivert fra tidligere konfigurasjon.

## Steg 11 Test klienter og verifisering

Koble to testklienter til accessportene. Forny DHCP og test adresser/gateways slik README beskriver. Kjør `05_verify.yml` og les statusfilene. Fyll inn egne resultater og legg til skjermbilder uten passord.

## Steg 12 Test idempotens

Kjør `02_switches.yml` og `03_routers.yml` på nytt uten å endre variabler. Målet er changed=0 og ingen feil. Undersøk eventuell normalisering av kommandoer på den faktiske IOS-versjonen. Ikke anta at syntakskontroll beviser idempotens.

## Steg 13 Avtal og bygg EtherChannel

Når den andre siden er klar, samordne DHCP-eierskap og unike IP-er først. Kjør `04_etherchannel.yml` med aktiveringsvariabelen. Kontroller bundle og begge medlemsporter på begge sider. Test samme VLAN over forbindelsen og trekk ut én medlemskabel under ping.

## Steg 14 Oppdater Git når du bytter maskin

På maskinen der du endret filer:

```bash
git status
git add README.md docs inventory playbooks scripts tests requirements.txt requirements-console.txt collections ansible.cfg .gitignore
git commit -m "Tilpass porter og dokumenter racktest"
git push
```

På den andre maskinen, før du begynner å endre:

```bash
git pull --ff-only
```

Hvis pull stopper fordi du har lokale endringer, ta vare på dem og løs konflikten; ikke kast endringer blindt. Ikke last opp backups, passord eller resultater med sensitive konfigurasjonsdata.

## Steg 15 Lever repoet

Sjekk GitHub i nettleser: README vises, alle script/playbooks finnes og repoet er offentlig. Legg inn faktiske testresultater og din egen forklaring. Gi læreren labinnlogging separat. Lever den virkelige GitHub-lenken.
