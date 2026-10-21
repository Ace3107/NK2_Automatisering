# NK2 STUD2 – Cisco automatisering

Prosjektet bruker **Python (pyserial)** til førstegangsoppsett av SSH via konsollkabel, og **Ansible fra WSL på lab-PC-en** til videre konfigurasjon av Cisco-utstyret.

## Kabling

| Fra | Til |
|---|---|
| Lab-PC → SW1 DIST | Gi1/0/1 (access VLAN 99) |
| SW1 Gi1/0/2 | R1 Gi0/0/1 (trunk VLAN 99) |
| SW1 Gi1/0/3 | R2 Gi0/1 (trunk VLAN 99) |
| R1 Gi0/0/0 | SW2 port 1 |
| R2 Gi0/0 | SW2 port 2 |
| SW2 port 3 | SW3 port 1 |

Portnavn på R2 og SW2/SW3 må verifiseres på utstyret. Linkene gjennom ruterne videresender **ikke** VLAN 99 automatisk.

## IP-plan

| Enhet | Management-IP |
|---|---|
| R1 – Cisco 4221 | `10.10.99.1/24` |
| R2 – Cisco 2901 | `10.10.99.2/24` |
| SW1 – Catalyst 3650 | `10.10.99.10/24` |
| SW2 – Catalyst 2960 | `10.10.99.11/24` |
| SW3 – Catalyst 1000 | `10.10.99.12/24` |

Management er planlagt på VLAN 99. Fra lab-PC-en er SW1, R1 og R2 tilgjengelige; tilkobling til SW2/SW3 gjennom ruterne må løses før Ansible kan nå dem fra lab-PC-en.

## Python: klargjør SSH

1. Koble **konsollkabel** fra PC til ønsket Cisco-enhet.
2. Installer pyserial: `python -m pip install pyserial` (på Windows).
3. Kjør Python-scriptet fra repoet, f.eks. `python cisco_ssh_config_v6.py` (bruk faktisk filnavn).
4. Oppgi COM-port, enhetstype, hostname, SSH-bruker/passord, VLAN **99**, management-IP og riktig interface. På router opprettes **802.1Q-subinterface**; på switch **VLAN-interface (SVI)** og valgte access-/trunkporter.
5. Verifiser på enheten: `show ip ssh` og `show ip interface brief`. Test ping og SSH fra lab-PC-en.

**Merk:** Enkelte IOS-versjoner krever `ip domain name stud2.local` (mellomrom), ikke `ip domain-name`. Kontroller output fra scriptet. Del aldri faktiske passord eller private nøkler i det offentlige GitHub-repoet.

## WSL: SSH-nøkler og eldre algoritmer

Cisco-enhetene bruker ulike SSH-algoritmer. Ved første SSH-tilkobling må **vertsnøkkelen (host key)** verifiseres og godtas; den lagres i `~/.ssh/known_hosts`. Dette er noe annet enn innloggingspassordet. Hvis RSA-vertsnøkkelen er regenerert, kontroller ny fingerprint før du oppdaterer den lagrede nøkkelen.

Ved feilmeldinger om **Diffie-Hellman / KEX, cipher, host key eller MAC** kan gamle IOS-enheter kreve egne algoritmeinnstillinger i WSL. Legg dem **kun på aktuelle lab-verter** i `~/.ssh/config`, ikke globalt:

```sshconfig
Host SW1 10.10.99.10
    HostName 10.10.99.10
    User admin
    KexAlgorithms +diffie-hellman-group14-sha1
    HostKeyAlgorithms +ssh-rsa
    MACs +hmac-sha1
    Ciphers +aes128-cbc

Host R1 10.10.99.1
    HostName 10.10.99.1
    User admin
    Ciphers +aes128-ctr
```

Eksemplene er basert på algoritmene som ble brukt ved feilsøking; tilpass per enhet. Test med `ssh admin@10.10.99.1` og `ssh admin@10.10.99.10`. **Ansible `network_cli` med Paramiko følger ikke nødvendigvis OpenSSH-filen**, så Ansible kan kreve egen SSH-tilpasning. Eldre algoritmer bør bare brukes i labben.

## Ansible fra WSL

```bash
sudo apt update
sudo apt install -y ansible python3-paramiko openssh-client
ansible-galaxy collection install -r requirements.yml
ansible-inventory -i hosts.yml --graph
ansible-playbook -i hosts.yml playbooks/01_test_tilkobling.yml --limit R1,R2,SW1 -k -K
```

Kjør fra prosjektmappen. `-k` spør om SSH-passord, `-K` om enable-passord. Ta backup med `02_backup_running_config.yml` før endringer. Kontroller faktiske porter/IP-er og ta backup før VLAN- eller HSRP-playbooks kjøres.
