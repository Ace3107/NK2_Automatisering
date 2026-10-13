# Kontroller gjennomført før levering av prosjektforslaget

Kontrollene er utført lokalt uten tilgang til Cisco-racket.

| Kontroll | Resultat |
|---|---|
| Python unit tests | 8 av 8 bestått |
| Ansible inventory graph | To rutere og tre switcher i riktige grupper |
| Ansible leser ansible.cfg | Inventory, host-key-kontroll og timeouts registrert |
| site.yml syntax-check | Bestått |
| 04_etherchannel.yml syntax-check | Bestått |

Miljø for kontrollene: Python 3.12, ansible-core 2.19.14, cisco.ios 11.1.1, ansible.netcommon 8.2.0, pySerial 3.5. Collections-versjonene i prosjektet er de som ble brukt i syntakskontrollen.

Syntakskontroll og unit tests bekrefter ikke at en faktisk IOS-enhet aksepterer alle kommandoene. Bootstrap, SSH, DHCP, ruting, idempotens og EtherChannel må testes og dokumenteres på utstyret. Bruk TESTRESULTATER.md til dette.
