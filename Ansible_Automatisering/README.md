# NK2 Arbeidskrav 2 – STUD2 – Cisco Python + Ansible

Dette prosjektet dekker **Del 2: Ansible-konfigurasjon** og beskriver hvordan Del 1 (Python/pyserial) blir grunnlaget. Playbooks er skrevet i YAML for `cisco.ios`-collection, og kjøres fra **WSL på MGMT-PC**, ikke på Cisco-enhetene. De har ikke vært testet på de faktiske IOS-versjonene eller fysisk rack.

## Kabling etter din beskrivelse (ikke etikettene i Packet Tracer-bildet)

| Fra | Port | Til | Port |
|---|---|---|---|
| MGMT-PC (Ansible/WSL) | Ethernet | SW1 DIST Catalyst 3650 | Gi1/0/1 (access VLAN 99) |
| SW1 | Gi1/0/2 (trunk VLAN 99) | R1 Cisco 4221 | Gi0/0/1 (Gi0/0/1.99) |
| SW1 | Gi1/0/3 (trunk VLAN 99) | R2 Cisco 2901 | Gi0/1 (bekreft faktisk navn) |
| R1 | Gi0/0/0 | SW2 Cisco 2960 | port 1 (bekreft faktisk navn) |
| R2 | Gi0/0 | SW2 | port 2 (bekreft faktisk navn) |
| SW2 | port 3 | SW3 Cisco 1000 | port 1 (bekreft faktisk navn) |

Management-plan: **R1 10.10.99.1; R2 10.10.99.2; SW1 10.10.99.10; SW2 10.10.99.11; SW3 10.10.99.12**, alle opprinnelig tenkt på VLAN 99. MGMT-PC er foreslått som 10.10.99.100/24. IP er ikke bekreftet for PC. R1 SSH er bekreftet fungerende.

**KRITISK:** R1 og R2 er rutere. De videresender *ikke* VLAN 99 transparent fra øvre til nedre porter. SW2 og SW3 er dermed **ikke automatisk tilgjengelige fra WSL**, selv om de konfigureres med 10.10.99.11 og .12. Behold R1/R2/SW1 som første Ansible-mål. Før endringer på SW2/SW3 må dere etablere et separat L2 management-kabelstrekk, eller designe rutet management med ulike subnett og korrekte returveier. HSRP på VLAN 10 er en separat klient-gateway-tjeneste, ikke løsningen på management-tilgangen.

## Arbeidskrav Del 1

Via Python + pyserial settes hostname, domene (`ip domain name` på IOS som krever mellomrom), lokal SSH-bruker, RSA-nøkler, SSH v2, VTY, VLAN 99 SVI/subinterface og nødvendige SW1 trunk-/access-porter. Dokumenter med skjermbilder av `show ip ssh`, `show ip interface brief` og ping/SSH fra WSL. Last Python-scriptet opp i repo separat. Ikke publiser ekte passord eller konfig-backuper.

## Installere i WSL

```bash
sudo apt update
sudo apt install -y ansible openssh-client
ansible-galaxy collection install -r requirements.yml
cd /sti/til/NK2_STUD2_Ansible
```

Når du bruker WSL under Windows kan prosjektet også ligge på `/mnt/c/...`, men det er ofte enklere å jobbe i Linux-hjemmekatalogen. Sjekk `ansible --version`.

## Før første Ansible-kjøring

1. Test `ping 10.10.99.1` og `ssh admin@10.10.99.1` fra WSL.
2. R1 fungerer allerede over SSH fra lab-PC, men dette bekrefter ikke automatisk WSL eller Ansible.
3. På eldre IOS kan SHA1/CBC være nødvendig **kun for lab**. Konfigurer eventuelt kompatibilitet per vert i `~/.ssh/config`, ikke globalt. OpenSSH SSH-konfig alene garanterer ikke at `network_cli`/libssh/paramiko bruker nøyaktig de samme algoritmene. Feilsøk transporten ved behov.
4. Oppdater `ansible_user` i `hosts.yml`. Ikke legg passord i repo. `-k` spør om SSH-passord, `-K` om enable-passord. Avhengig av Ansible-versjon og enable-oppsett kan du også bruke Ansible Vault for `ansible_password` og `ansible_become_password`.
5. Sjekk fysisk portkart og IOS-interface-navn med `show ip interface brief`, `show interfaces status`. Router R2-portene er spesielt viktige å bekrefte.
6. Behold strengt host-key-checking. Godkjenn verifiserte fingerprints ved første tilkobling.

## Rekkefølge og eksempler

```bash
# Lesing uten konfigurasjonsendring; start med R1
ansible-playbook playbooks/01_test_tilkobling.yml --limit R1 -k -K
ansible-playbook playbooks/03_verify_management.yml --limit R1,SW1 -k -K

# Backup (behandle som sensitiv)
ansible-playbook playbooks/02_backup_running_config.yml --limit R1,SW1 -k -K

# Opprett VLAN 10 på SW1 (bare hvis VLAN skal brukes der)
ansible-playbook playbooks/04_create_client_vlan.yml --limit SW1 -k -K -e allow_changes=true --check --diff

# HSRP plan: KUN etter at SW2 og begge ruternes nedlinker er kontrollert;
# sjekk virkelige interface/IP-planer først
ansible-playbook playbooks/07_configure_hsrp_vlan10.yml --limit R1,R2 -k -K -e allow_changes=true -e allow_hsrp_changes=true --check --diff

# Verifiser HSRP etter faktisk konfigurasjon
ansible-playbook playbooks/08_verify_hsrp.yml --limit R1,R2 -k -K

# Lagre aktiv konfigurasjon
ansible-playbook playbooks/09_save_config.yml --limit R1 -k -K -e allow_changes=true
```

`--check` gir ikke full garanti for nettverksmoduler og kan vise begrensede resultater; test fysiske endringer via konsoll når mulig.

## Playbooks

| Fil | Type | Innhold |
|---|---|---|
| `01_test_tilkobling.yml` | read-only | show version, IP, SSH |
| `02_backup_running_config.yml` | read-only | Lokal sikkerhetskopi av running-config |
| `03_verify_management.yml` | read-only | Sjekk management, VTY, trunk og VLAN |
| `04_create_client_vlan.yml` | endring (sperret) | Opprett VLAN 10 på valgte switcher |
| `05_configure_sw1_management_ports.yml` | endring (dobbel sperre) | SW1 access/trunk VLAN 99 |
| `06_configure_lower_switch_trunks.yml` | endring (dobbel sperre) | Klient-VLAN 10 på nedre switch-trunker |
| `07_configure_hsrp_vlan10.yml` | endring (dobbel sperre) | R1 Active priority 110, R2 standby priority 100, VIP 10.10.10.1 |
| `08_verify_hsrp.yml` | read-only | HSRP Active/Standby status |
| `09_save_config.yml` | endring (sperret) | write running-config til startup-config |
| `10_collect_documentation.yml` | read-only | Samle show-utskrifter til `outputs/` |
| `11_configure_access_client_ports.yml` | endring (dobbel sperre) | VLAN 10 på valgte SW3 klientporter |

## HSRP / VLAN 10 – forutsetninger

HSRP bruker **eget klientnett 10.10.10.0/24**, med R1 `.2`, R2 `.3` og virtuell gateway `.1`. Nedre routerporter til SW2 må ha `dot1Q 10` på subinterfaces, og trunk fra SW2 til SW3 må frakte VLAN 10. Dette prosjektet oppretter ikke DHCP, WAN, NAT, OSPF eller internett-tilgang. HSRP holder default-gateway tilgjengelig ved ruterfeil, men løser ikke resten av rutingen.

Etter endring må du teste klienter med gateway `10.10.10.1`, se `show standby brief`, og kontrollere faktisk failover. R2 er eldre IOS; hvis HSRP-kommandoer avvises, sjekk IOS-versjon og tilgjengelig syntaks med `standby ?`. Ikke endre management-tilgang ved et uhell.

## Oppgave 4: Når Ansible ikke strekker til

Python/pyserial er bootstrapping via konsoll når SSH/IP ikke finnes. Når SSH fungerer kan Ansible håndtere drift og konfig. For funksjoner som mangler i `cisco.ios`-moduler kan du bruke `cisco.ios.ios_config`, `cisco.ios.ios_command` eller en egen Python-hjelper. Ikke prøv å utføre COM-konsolltilgang over Ansible SSH. Dokumenter skillet og det dere tester.

## GitHub

```bash
git init
git add .
git commit -m "NK2 STUD2 Cisco Ansible grunnoppsett"
# Opprett offentlig GitHub-repo selv, og sett origin deretter
```

`.gitignore` hindrer lokale backuper og statusfiler fra å bli committet. Gå gjennom alle filer før publisering: ingen private nøkler, faktiske passord, tokens eller autentiseringsdata. Ved samarbeid må STUD1 og STUD2 koordinere porter, VLAN og utstyr før endringer.
