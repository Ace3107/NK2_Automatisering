#!/usr/bin/env python3
"""Configure SSH and management VLAN on Cisco IOS switches and routers via console."""
import getpass
import ipaddress
import re
import sys
import time

import serial

BAUDRATE = 9600
RSA_BITS = 2048
ERROR_PATTERNS = (
    r"% Invalid input", r"% Incomplete command", r"% Ambiguous command",
    r"% Error", r"% Failed", r"% Unrecognized", r"% Cannot", r"% Not supported",
)


def ask(label, default=None):
    suffix = f" [{default}]" if default is not None else ""
    answer = input(f"{label}{suffix}: ").strip()
    return answer if answer else default


def read_serial(ser, timeout=4, quiet_time=0.5):
    """Samme leseprinsipp som originalscriptet, uavhengig av CLI-prompt."""
    data = bytearray()
    start = time.monotonic()
    last_data = start
    while time.monotonic() - start < timeout:
        if ser.in_waiting:
            data.extend(ser.read(ser.in_waiting))
            last_data = time.monotonic()
        else:
            if data and time.monotonic() - last_data >= quiet_time:
                break
            time.sleep(0.05)
    return data.decode(errors="ignore")


def command(ser, cmd, timeout=4, secret=False, check=True, accept_question=False):
    print(f"\n>>> {'[skjult]' if secret else cmd}")
    # Ikke tøm inputbuffer før hver kommando: behold oppførselen fra originalscriptet.
    ser.write((cmd + "\r\n").encode())
    ser.flush()
    output = read_serial(ser, timeout=timeout)
    if secret:
        print("[Svar mottatt, skjult av hensyn til passord]")
    elif output:
        print(output.rstrip())
    if check and any(re.search(pattern, output, re.IGNORECASE) for pattern in ERROR_PATTERNS):
        raise RuntimeError(f"Cisco avviste kommandoen: {('[skjult]' if secret else cmd)}\n{'' if secret else output}")
    return output


def enable_mode(ser, enable_password):
    """Bruk originalscriptets tolerante enable-sekvens, men ikke fortsett uten #."""
    ser.write(b"\r\n")
    time.sleep(0.5)
    output = read_serial(ser, timeout=2)
    if output:
        print(output)
    if output.rstrip().endswith("#"):
        return
    output = command(ser, "enable")
    if "password" in output.lower():
        if not enable_password:
            raise RuntimeError("Enable-passord kreves.")
        output = command(ser, enable_password, secret=True)
    if not output.rstrip().endswith("#"):
        raise RuntimeError("Kunne ikke bekrefte enable-mode (#). Konsollrespons: " + repr(output[-250:]))


def parse_interfaces(value):
    """Accept comma-separated IOS interface names, without CLI separators."""
    ports = []
    for raw in value.split(","):
        port = raw.strip()
        if not port:
            continue
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9/.-]*", port):
            raise ValueError(f"Ugyldig portnavn: {port!r}")
        if port.lower() not in {p.lower() for p in ports}:
            ports.append(port)
    return ports


def confirm(label, default="nei"):
    while True:
        value = ask(f"{label} (ja/nei)", default).strip().lower()
        if value in ("ja", "j", "yes", "y"):
            return True
        if value in ("nei", "n", "no"):
            return False
        print("Skriv ja eller nei.")


def main():
    print("=== Cisco SSH og management VLAN via konsoll | VERSJON 4 - ORIGINAL SERIAL + TRUNKPORTER ===")
    print(f"Scriptfil: {__file__}")
    com_port = ask("COM-port", "COM3")
    kind = ask("Enhetstype (switch/router)").lower()
    if kind not in ("switch", "router"):
        sys.exit("Velg switch eller router.")
    hostname = ask("Hostname")
    domain = ask("Domain name", "lab.local")
    username = ask("SSH-brukernavn", "admin")
    ssh_password = getpass.getpass("SSH-passord: ")
    old_enable = getpass.getpass("Eksisterende enable-passord (Enter hvis ingen): ")
    new_enable = getpass.getpass("Nytt enable secret (Enter for å beholde eksisterende): ")
    vlan_text = ask("Management VLAN", "99")
    vlan = int(vlan_text)
    if not 1 <= vlan <= 4094:
        sys.exit("VLAN-ID må være 1–4094.")
    ip_text = ask("Management-IP")
    mask_text = ask("Nettmaske", "255.255.255.0")
    iface_ip = ipaddress.IPv4Interface(f"{ip_text}/{mask_text}")
    if not ssh_password or not hostname or not domain:
        sys.exit("Hostname, domenenavn og SSH-passord er påkrevd.")
    if kind == "switch":
        access_port = ask("Access-port til management-PC (Enter for å hoppe over)", "")
        if access_port:
            parsed = parse_interfaces(access_port)
            if len(parsed) != 1:
                sys.exit("Oppgi nøyaktig én access-port.")
            access_port = parsed[0]
        trunk_ports = []
        print(f"\n--- EKSTRA PORTER FOR MANAGEMENT VLAN {vlan} ---")
        print("Du kan legge til trunkporter mot R1, R2 eller andre switcher.")
        if confirm(f"Vil du konfigurere flere porter som trunk for VLAN {vlan}?"):
            trunk_ports = parse_interfaces(ask(
                "Trunkporter (kommaseparert, f.eks. Gi0/0/2, Gi0/0/3)"
            ))
            if not trunk_ports:
                sys.exit("Du valgte trunkporter, men oppga ingen porter.")
            if access_port and access_port.lower() in {p.lower() for p in trunk_ports}:
                sys.exit("Samme port kan ikke være både access-port og trunkport.")
    else:
        router_port = ask("Fysisk router-port mot trunk til switch (f.eks. GigabitEthernet0/0/1)")
        if "." in router_port:
            sys.exit("Oppgi fysisk interface uten .VLAN. Scriptet lager subinterfacet.")
    print("\nPlanlagt konfigurasjon:")
    print(f"Type: {kind}; hostname: {hostname}; VLAN: {vlan}; IP: {iface_ip}")
    if kind == "router":
        print(f"Fysisk port: {router_port}; subinterface: {router_port}.{vlan} (802.1Q tagget)")
        print("NB: Motstående switchport må være TRUNK og tillate VLAN-et.")
        print("NB: Ikke bruk samme IP-subnett på andre rutede interface på denne routeren.")
    else:
        print(f"SVI: Vlan{vlan}; PC-port: {access_port or '(ingen)'}")
        print(f"Trunkporter (802.1Q): {', '.join(trunk_ports) if trunk_ports else '(ingen)'}")
        if trunk_ports:
            print("OBS: Porter som velges som trunk, endres fra eventuell access-modus.")
            print("Management-VLAN legges til i allowed-listen uten å fjerne eksisterende VLAN.")
    if ask("Kjør konfigurasjonen? (ja/nei)", "nei").lower() != "ja":
        return

    enable_cbc = confirm("Aktiver eldre CBC-kryptering for lab?")
    save_config = confirm("Lagre konfigurasjonen med write memory?", default="ja")

    with serial.Serial(com_port, BAUDRATE, timeout=0.2, write_timeout=5) as ser:
        time.sleep(2)
        enable_mode(ser, old_enable)

        # Disable paging (EXEC mode)
        command(ser, "terminal length 0", check=False)
        command(ser, "configure terminal")
        command(ser, "no ip domain-lookup")
        command(ser, f"hostname {hostname}")
        command(ser, f"ip domain-name {domain}")
        if new_enable:
            command(ser, f"enable secret {new_enable}", secret=True)
        command(ser, f"username {username} privilege 15 secret {ssh_password}", secret=True)

        if kind == "switch":
            command(ser, f"vlan {vlan}")
            command(ser, f"name MANAGEMENT_{vlan}")
            command(ser, "exit")
            command(ser, f"interface Vlan{vlan}")
            command(ser, f"ip address {iface_ip.ip} {iface_ip.netmask}")
            command(ser, "no shutdown")
            command(ser, "exit")
            if access_port:
                command(ser, f"interface {access_port}")
                command(ser, "switchport mode access")
                command(ser, f"switchport access vlan {vlan}")
                command(ser, "spanning-tree portfast")
                command(ser, "no shutdown")
                command(ser, "exit")
            for trunk_port in trunk_ports:
                command(ser, f"interface {trunk_port}")
                command(ser, "switchport mode trunk")
                # Preserve other VLANs already permitted on the trunk.
                command(ser, f"switchport trunk allowed vlan add {vlan}")
                command(ser, "no shutdown")
                command(ser, "exit")
        else:
            command(ser, f"interface {router_port}")
            command(ser, "no shutdown")
            command(ser, "exit")
            command(ser, f"interface {router_port}.{vlan}")
            command(ser, f"encapsulation dot1Q {vlan}")
            command(ser, f"ip address {iface_ip.ip} {iface_ip.netmask}")
            command(ser, "no shutdown")
            command(ser, "exit")

        command(ser, "ip ssh version 2")
        command(ser, "ip ssh time-out 60")
        command(ser, "ip ssh authentication-retries 3")
        # Reuse existing keys where possible. Avoid replacing keys without explicit approval.
        command(ser, "end")
        keys = command(ser, "show crypto key mypubkey rsa", check=False)
        if "Key name:" not in keys and "Key name" not in keys:
            command(ser, "configure terminal")
            key_output = command(ser, f"crypto key generate rsa modulus {RSA_BITS}", timeout=30, accept_question=True)
            if "replace" in key_output.lower() or "yes/no" in key_output.lower():
                raise RuntimeError("Eksisterende RSA-nøkkel krever bekreftelse. Avbrutt for å unngå utilsiktet erstatning.")
            command(ser, "end")
        command(ser, "configure terminal")
        # CBC is legacy and should only be enabled when explicitly needed for this lab.
        if enable_cbc:
            command(ser, "ip ssh server algorithm encryption aes128-cbc 3des-cbc aes192-cbc aes256-cbc")
        # Many Cisco IOS platforms support 0-15; fail fast if not.
        command(ser, "line vty 0 15")
        command(ser, "login local")
        command(ser, "transport input ssh")
        command(ser, "exec-timeout 15 0")
        command(ser, "exit")
        command(ser, "end")

        command(ser, "show ip ssh")
        command(ser, "show ip interface brief")
        if kind == "switch":
            command(ser, "show vlan brief")
            command(ser, "show interfaces trunk")
        command(ser, "show running-config | section line vty")
        if save_config:
            command(ser, "write memory", timeout=30)
    print(f"\nFerdig. Test ping til {iface_ip.ip}, deretter SSH-port 22.")


if __name__ == "__main__":
    try:
        main()
    except (serial.SerialException, RuntimeError, TimeoutError, ValueError) as error:
        print(f"\n[STOPPET] {error}")
        sys.exit(1)
