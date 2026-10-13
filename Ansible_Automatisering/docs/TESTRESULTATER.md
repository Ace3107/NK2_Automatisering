# Resultater fra faktisk racktest

Status ved opprettelse: **Ikke gjennomført på fysisk utstyr**. Tabellen fylles ut av studenten. Ikke presenter lokale kodekontroller som en racktest.

Student: [fyll inn]  
Dato og rack: [fyll inn]  
STUD-side og eventuell medstudent: [fyll inn]  
Git commit testet: [fyll inn]  
Python, Ansible og collections-versjoner: [fyll inn]

| Enhet | Faktisk modell | IOS-versjon | Avvik fra eksempelporter |
|---|---|---|---|
| R1 | Ikke registrert | Ikke registrert | Ikke registrert |
| R2 | Ikke registrert | Ikke registrert | Ikke registrert |
| SW-MGMT | Ikke registrert | Ikke registrert | Ikke registrert |
| SW-DIST | Ikke registrert | Ikke registrert | Ikke registrert |
| SW-ACCESS | Ikke registrert | Ikke registrert | Ikke registrert |

| Test | Forventet | Faktisk resultat og bevis |
|---|---|---|
| Python alle fem | Ingen feil, SSH mulig | Ikke testet |
| Alle VTY-ranges | login local, kun SSH | Ikke testet |
| SSH fra WSL/Linux | Alle fem adresser nås | Ikke testet |
| VLAN/trunker | Riktig portplan og VLAN-liste | Ikke testet |
| DHCP VLAN10 | 192.168.10.50–254, /24, gateway .1 | Ikke testet |
| DHCP VLAN20 | 192.168.20.50–254, /24, gateway .1 | Ikke testet |
| DHCP management | Pooler og exclusions 99/199 på R1 | Ikke testet |
| Ruting og klientping | Begge retninger virker | Ikke testet |
| verify-playbook | failed=0 og unreachable=0 | Ikke testet |
| Andre konfigurasjonskjøring | changed=0 eller forklart avvik | Ikke testet |
| EtherChannel begge ender | SU og to P-medlemmer | Ikke testet |
| Én EtherChannel-kabel ute | Trafikk fortsetter etter eventuell konvergens | Ikke testet |
| Lagret konfigurasjon | Endringene finnes i startup-config | Ikke testet |

## Individuell forståelse

Beskriv med egne ord hvorfor Python må kjøres før Ansible, hvorfor de to management-nettene er forskjellige, hva dot1Q-subinterfaces gjør, og hvordan DHCP-eierskap er avtalt. Oppgi minst ett faktisk problem du møtte, hvordan du fant årsaken og hva du endret. Hvis du ikke møtte problemer, skriv det uten å finne på en hendelse.
