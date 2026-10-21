#!/usr/bin/env python3
"""Cisco IOS SSH + VLAN via console. Switch trunks and router secondary links.

Requires: pip install pyserial
Routers use routed 802.1Q subinterfaces. Each routed link must have its own
IPv4 subnet; this script deliberately rejects overlapping subnets.
"""
import getpass
import ipaddress
import re
import sys
import time
import serial

BAUDRATE = 9600
RSA_BITS = 2048
IOS_ERRORS = re.compile(
    r"(?im)^\s*%\s*(?:Invalid input|Incomplete command|Ambiguous command|Error|"
    r"Failed|Unrecognized|Cannot|Not supported|Unknown command)\b"
)


def ask(label, default=None):
    suffix = f" [{default}]" if default is not None else ""
    answer = input(f"{label}{suffix}: ").strip()
    return answer if answer else default


def yes_no(label, default=False):
    while True:
        answer = input(f"{label} ({'JA/nei' if default else 'ja/NEI'}): ").strip().lower()
        if not answer:
            return default
        if answer in ('ja', 'j', 'yes', 'y'):
            return True
        if answer in ('nei', 'n', 'no'):
            return False
        print("Svar ja eller nei.")


def port_name(text):
    text = text.strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9/-]*", text):
        raise ValueError(f"Ugyldig fysisk port: {text!r}")
    return text


def ports_list(text):
    result = []
    for item in text.split(','):
        if item.strip():
            port = port_name(item)
            if port.lower() not in {p.lower() for p in result}:
                result.append(port)
    return result


def ipv4_config(label):
    address = ask(f"{label} IP-adresse")
    mask = ask(f"{label} nettmaske", "255.255.255.0")
    interface = ipaddress.IPv4Interface(f"{address}/{mask}")
    if interface.ip == interface.network.network_address or (
        interface.network.prefixlen < 31 and interface.ip == interface.network.broadcast_address
    ):
        raise ValueError("Kan ikke bruke nettverksadresse eller broadcastadresse som interface-IP.")
    return interface


def read_console(ser, timeout=5, quiet_time=0.65):
    chunks = bytearray()
    start = time.monotonic()
    last = start
    while time.monotonic() - start < timeout:
        available = ser.in_waiting
        if available:
            chunks.extend(ser.read(available))
            last = time.monotonic()
        elif chunks and time.monotonic() - last >= quiet_time:
            break
        else:
            time.sleep(0.05)
    return chunks.decode('utf-8', errors='replace').replace('\x08', '')


def send(ser, cmd, *, timeout=5, secret=False, required=True):
    print('\n>>> ' + ('[skjult]' if secret else cmd))
    ser.write((cmd + '\r\n').encode('utf-8'))
    ser.flush()
    result = read_console(ser, timeout=timeout)
    if not secret:
        print(result.rstrip() if result else '[Ingen respons]')
    # Escape sequences from some terminals are ignored for error matching.
    cleaned = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', result)
    if IOS_ERRORS.search(cleaned):
        if required:
            raise RuntimeError('Cisco avviste kommandoen: ' + ('[skjult]' if secret else cmd) +
                               ('' if secret else '\n' + cleaned[-700:]))
        print('[ADVARSEL] Kommandoen støttes ikke, fortsetter.')
    elif not result.strip():
        raise RuntimeError('Ingen respons etter kommando: ' + ('[skjult]' if secret else cmd))
    return result


def ensure_enable(ser, password):
    ser.write(b'\r\n')
    ser.flush()
    received = read_console(ser, timeout=4)
    print(received.rstrip())
    if re.search(r'\(config[^)]*\)#\s*$', received, re.I):
        send(ser, 'end')
        return
    if re.search(r'[#]\s*$', received):
        return
    if re.search(r'(?:username|login|password)\s*:', received, re.I):
        raise RuntimeError('Enheten venter på innlogging i konsollen. Logg inn først.')
    received = send(ser, 'enable')
    if re.search(r'password\s*:', received, re.I):
        if not password:
            raise RuntimeError('Enable-passord er påkrevd.')
        received = send(ser, password, secret=True)
    if not re.search(r'#\s*$', received):
        raise RuntimeError('Kunne ikke bekrefte enable mode. Siste respons: ' + repr(received[-200:]))


def enter_interface(ser, interface):
    send(ser, f'interface {interface}')


def configure_router_link(ser, port, vlan, address):
    enter_interface(ser, port)
    send(ser, 'no shutdown')
    send(ser, 'exit')
    enter_interface(ser, f'{port}.{vlan}')
    send(ser, f'encapsulation dot1Q {vlan}')
    send(ser, f'ip address {address.ip} {address.netmask}')
    send(ser, 'no shutdown')
    send(ser, 'exit')


def main():
    print('=== CISCO SSH CONFIG V5 | SWITCH TRUNK + ROUTER EKSTRAPORTER ===')
    print('Script:', __file__)
    com = ask('COM-port', 'COM3')
    kind = ask('Type (switch/router)').lower()
    if kind not in ('switch', 'router'):
        raise ValueError('Velg switch eller router')
    hostname = ask('Hostname')
    domain = ask('Domene', 'lab.local')
    username = ask('SSH-bruker', 'admin')
    password = getpass.getpass('SSH-passord: ')
    enable_old = getpass.getpass('Eksisterende enable-passord (Enter hvis ingen): ')
    enable_new = getpass.getpass('Nytt enable secret (Enter for uendret): ')
    vlan = int(ask('Management VLAN-ID', '99'))
    if not 1 <= vlan <= 4094:
        raise ValueError('VLAN-ID må være mellom 1 og 4094')
    address = ipv4_config('Management')
    if not hostname or not username or not password or not domain:
        raise ValueError('Hostname, brukernavn, domenenavn og SSH-passord er påkrevd')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*', hostname):
        raise ValueError('Ugyldig hostname')
    if not re.fullmatch(r'[A-Za-z0-9.-]+', domain):
        raise ValueError('Ugyldig domenenavn')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', username):
        raise ValueError('Ugyldig brukernavn')
    if any(ch in password for ch in '\r\n') or any(ch in enable_new for ch in '\r\n'):
        raise ValueError('Passord kan ikke inneholde linjeskift')

    access_ports = []
    trunk_ports = []
    extras = []
    if kind == 'switch':
        raw = ask('Access-porter i management VLAN (kommaseparert, Enter for ingen)', '')
        access_ports = ports_list(raw)
        if yes_no('Konfigurere trunkporter som tillater management VLAN?'):
            trunk_ports = ports_list(ask('Trunkporter (kommaseparert, f.eks. Gi0/0/2, Gi0/0/3)'))
        if not trunk_ports and not access_ports:
            print('OBS: Ingen fysiske switchporter endres.')
        if {p.lower() for p in access_ports} & {p.lower() for p in trunk_ports}:
            raise ValueError('Samme port kan ikke være både access og trunk.')
    else:
        primary = port_name(ask('Fysisk ruterport mot DIST1 (trunk)'))
        used = {primary.lower()}
        networks = [address.network]
        print('\nEkstra ruterporter kan konfigureres med EGET subnett,')
        print('eller aktiveres UTEN IP. Ikke legg samme /24 på to rutede porter.')
        while yes_no('Legge til en ekstra fysisk ruterport?'):
            port = port_name(ask('Fysisk ruterport (mot f.eks. Layer 2-switch)'))
            if port.lower() in used:
                raise ValueError('Porten er allerede oppgitt.')
            used.add(port.lower())
            mode = ask('Modus: (1) eget VLAN subinterface + IP / (2) kun no shutdown', '1')
            if mode == '1':
                extra_vlan = int(ask('VLAN-ID på denne forbindelsen', str(vlan)))
                if not 1 <= extra_vlan <= 4094:
                    raise ValueError('Ugyldig VLAN-ID')
                extra_ip = ipv4_config(f'{port}.{extra_vlan}')
                if any(extra_ip.network.overlaps(n) for n in networks):
                    raise ValueError(
                        f'Subnett {extra_ip.network} overlapper eksisterende {networks}. '
                        'Bruk eget subnett eller en støttet Layer 2 bridge/BDI-løsning.'
                    )
                networks.append(extra_ip.network)
                extras.append(('subinterface', port, extra_vlan, extra_ip))
            elif mode == '2':
                extras.append(('no_ip', port, None, None))
            else:
                raise ValueError('Velg modus 1 eller 2')

    print('\n--- KONFIGURASJONSPLAN ---')
    print('Enhet:', kind, hostname, '| management:', address, '| VLAN:', vlan)
    if kind == 'switch':
        print('Accessporter:', access_ports)
        print('Trunkporter:', trunk_ports)
    else:
        print('Primær:', f'{primary}.{vlan}', address)
        for mode, port, v, ip in extras:
            print('Ekstra:', f'{port}.{v} -> {ip}' if mode == 'subinterface' else f'{port} -> no shutdown, ingen IP')
        print('NB: Ulike subnett krever routing for å nå den andre switchen over SSH.')
    if not yes_no('Kjør konfigurasjonen?'):
        print('Avbrutt uten endringer.')
        return
    legacy = yes_no('Bruke eldre CBC-kryptering (kun lab)?')
    save = yes_no('Lagre med write memory etter verifisering?', True)

    with serial.Serial(com, BAUDRATE, timeout=0.2, write_timeout=5) as ser:
        time.sleep(1.5)
        ensure_enable(ser, enable_old)
        send(ser, 'terminal length 0', required=False)
        send(ser, 'configure terminal')
        # no ip domain-lookup omitted: optional and rejected by some IOS/platform images.
        send(ser, f'hostname {hostname}')
        send(ser, f'ip domain name {domain}')
        if enable_new:
            send(ser, f'enable secret {enable_new}', secret=True)
        send(ser, f'username {username} privilege 15 secret {password}', secret=True)

        if kind == 'switch':
            send(ser, f'vlan {vlan}')
            send(ser, f'name MANAGEMENT_{vlan}')
            send(ser, 'exit')
            enter_interface(ser, f'Vlan{vlan}')
            send(ser, f'ip address {address.ip} {address.netmask}')
            send(ser, 'no shutdown')
            send(ser, 'exit')
            for port in access_ports:
                enter_interface(ser, port)
                send(ser, 'switchport mode access')
                send(ser, f'switchport access vlan {vlan}')
                send(ser, 'spanning-tree portfast', required=False)
                send(ser, 'no shutdown')
                send(ser, 'exit')
            for port in trunk_ports:
                enter_interface(ser, port)
                send(ser, 'switchport mode trunk')
                send(ser, f'switchport trunk allowed vlan add {vlan}')
                send(ser, 'no shutdown')
                send(ser, 'exit')
        else:
            configure_router_link(ser, primary, vlan, address)
            for mode, port, secondary_vlan, secondary_ip in extras:
                if mode == 'subinterface':
                    configure_router_link(ser, port, secondary_vlan, secondary_ip)
                else:
                    enter_interface(ser, port)
                    send(ser, 'no shutdown')
                    send(ser, 'exit')

        send(ser, 'ip ssh version 2')
        send(ser, 'ip ssh time-out 60', required=False)
        send(ser, 'ip ssh authentication-retries 3', required=False)
        send(ser, 'end')
        key_output = send(ser, 'show crypto key mypubkey rsa', timeout=8, required=False)
        if not re.search(r'(?i)key name\s*:', key_output):
            send(ser, 'configure terminal')
            # Device may ask for confirmation or key size. Stop rather than answering blindly.
            rsa_result = send(ser, f'crypto key generate rsa modulus {RSA_BITS}', timeout=25)
            if re.search(r'(?i)(replace|yes/no|\[yes\])', rsa_result):
                raise RuntimeError('RSA spurte om nøkkel-erstatning. Kontroller manuelt før du fortsetter.')
            send(ser, 'end')
        send(ser, 'configure terminal')
        if legacy:
            send(ser, 'ip ssh server algorithm encryption aes128-cbc 3des-cbc aes192-cbc aes256-cbc', required=False)
        # Older IOS may have only 5 VTY lines; prefer 0-4 and separately configure 5-15 if present.
        send(ser, 'line vty 0 4')
        send(ser, 'login local')
        send(ser, 'transport input ssh')
        send(ser, 'exec-timeout 15 0')
        send(ser, 'exit')
        vty_extra = send(ser, 'line vty 5 15', required=False)
        if not IOS_ERRORS.search(vty_extra):
            send(ser, 'login local')
            send(ser, 'transport input ssh')
            send(ser, 'exec-timeout 15 0')
            send(ser, 'exit')
        send(ser, 'end')
        send(ser, 'show ip ssh', required=False)
        send(ser, 'show ip interface brief')
        if kind == 'switch':
            send(ser, 'show vlan brief', required=False)
            send(ser, 'show interfaces trunk', required=False)
        send(ser, 'show running-config | section line vty', required=False)
        if save:
            send(ser, 'write memory', timeout=25)
    print('\nFERDIG. Test ping og TCP port 22 til management-IP.')
    if extras:
        print('Husk routing/default-gateway for subnett bak ruterne.')


if __name__ == '__main__':
    try:
        main()
    except (serial.SerialException, OSError, ValueError, RuntimeError) as exc:
        print('\n[STOPPET]', exc)
        sys.exit(1)
