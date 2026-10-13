#!/usr/bin/env python3
"""Bootstrap Cisco IOS via serial. No passwords are stored or printed.

The host YAML describes both SSH and the minimum path needed for Ansible.
Use on dedicated lab equipment with verified interface names.
"""
import argparse
import getpass
import ipaddress
import re
import sys
import time
from pathlib import Path

import serial
import yaml

PROMPT = re.compile(r'(?m)^[\w.-]+(?:\([\w.-]+\))?[>#]\s*$')
ERROR = re.compile(r'%\s*(?:Invalid input|Incomplete command|Ambiguous command|Error|Bad|Unrecognized|Cannot|Unable)', re.I)


def safe(value, label):
    text = str(value)
    if not text or re.search(r'[\s?\x00-\x1f\x7f]', text):
        raise ValueError(f'{label}: tom verdi, mellomrom, kontrolltegn og ? er ikke tillatt.')
    return text


def bootstrap_commands(host, user, password, enable_secret):
    """Pure function: validates input and generates device-specific commands."""
    name = safe(host['hostname'], 'hostname')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,62}', name):
        raise ValueError('Hostname må starte med en bokstav og bruke bokstaver, tall og bindestrek.')
    for val, label in [(host['domain'], 'domain'), (user, 'user'), (password, 'password'), (enable_secret, 'enable')]:
        safe(val, label)
    m = host['management']
    ipaddress.IPv4Interface(f"{m['ip']}/{m['mask']}")
    cmds = ['configure terminal', f'hostname {name}', f"ip domain-name {host['domain']}",
            f'username {user} privilege 15 secret {password}', f'enable secret {enable_secret}']
    if host['device_type'] == 'switch':
        v = int(m['vlan'])
        if not 1 <= v <= 4094:
            raise ValueError('Ugyldig VLAN')
        ipaddress.IPv4Address(m['gateway'])
        if host.get('routed_switch'):
            cmds += ['no ip routing']
        cmds += [f'vlan {v}', 'exit', f'interface Vlan{v}', f"ip address {m['ip']} {m['mask']}",
                 'no shutdown', 'exit', f"ip default-gateway {m['gateway']}"]
        for port in host.get('bootstrap_access_ports', []):
            cmds += [f"interface {safe(port, 'port')}", 'switchport mode access',
                     f'switchport access vlan {v}', 'no shutdown', 'exit']
        for port in host.get('trunk_ports', []):
            cmds += [f"interface {safe(port, 'port')}", 'switchport mode trunk',
                     f'switchport trunk allowed vlan {v}', 'no shutdown', 'exit']
    elif host['device_type'] == 'router':
        lower = host['lower_mgmt']
        ipaddress.IPv4Interface(f"{lower['ip']}/{lower['mask']}")
        parent = safe(host['lower_parent'], 'lower interface')
        cmds += [f"interface {safe(m['interface'], 'management interface')}",
                 f"ip address {m['ip']} {m['mask']}", 'no shutdown', 'exit',
                 f'interface {parent}', 'no ip address', 'no shutdown', 'exit',
                 f"interface {parent}.{int(lower['vlan'])}", f"encapsulation dot1Q {int(lower['vlan'])}",
                 f"ip address {lower['ip']} {lower['mask']}", 'exit']
    else:
        raise ValueError('device_type må være switch eller router')
    cmds += ['end']
    return cmds


class Console:
    def __init__(self, port):
        self.port = port

    def wait(self, timeout=15):
        end = time.monotonic() + timeout
        output = ''
        while time.monotonic() < end:
            output += self.port.read(self.port.in_waiting or 1).decode(errors='replace').replace('\r', '')
            if PROMPT.search(output):
                return output
        raise TimeoutError('Ingen IOS-prompt. Sjekk konsollport, baudrate og enhetens konsolltilstand.')

    def command(self, command, timeout=15):
        self.port.reset_input_buffer()
        self.port.write((command + '\r').encode())
        output = self.wait(timeout)
        if ERROR.search(output):
            # Never echo command/output here: they may contain credentials.
            raise RuntimeError('IOS avviste en kommando. Kontroller modell, grensesnitt og IOS-syntaks i konsollen.')
        return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='YAML i inventory/host_vars')
    parser.add_argument('--port', help='COM3, /dev/ttyUSB0 eller faktisk konsollport')
    parser.add_argument('--baud', type=int, help='Overstyr console_baud')
    args = parser.parse_args()
    host = yaml.safe_load(Path(args.host).read_text(encoding='utf-8'))
    port = args.port or input('Konsollport: ').strip()
    user = input('Ny SSH-bruker: ').strip()
    password = getpass.getpass('Nytt SSH-passord: ')
    secret = getpass.getpass('Nytt enable secret: ')
    cmds = bootstrap_commands(host, user, password, secret)
    with serial.Serial(port, args.baud or host.get('console_baud', 9600), timeout=0.2,
                       bytesize=8, parity='N', stopbits=1, xonxoff=False, rtscts=False, dsrdtr=False) as conn:
        console = Console(conn)
        conn.write(b'\r')
        initial = console.wait()
        if initial.rstrip().endswith('>'):
            conn.write(b'enable\r')
            # enable can ask for an existing password; this must not be the new secret.
            end = time.monotonic() + 15
            output = ''
            while time.monotonic() < end:
                output += conn.read(conn.in_waiting or 1).decode(errors='replace').replace('\r', '')
                if 'Password:' in output:
                    conn.write((getpass.getpass('Eksisterende enable-passord: ') + '\r').encode())
                    output = console.wait()
                    break
                if PROMPT.search(output):
                    break
            if not output.rstrip().endswith('#'):
                raise RuntimeError('Kunne ikke få privilegert EXEC-prompt.')
        elif '(config' in initial:
            console.command('end')
        console.command('terminal length 0')
        for number, command in enumerate(cmds, 1):
            console.command(command)
            print(f'Bootstrap {number}/{len(cmds)} OK')
        keys = console.command('show crypto key mypubkey rsa')
        if 'Key name:' not in keys:
            console.command('configure terminal')
            console.command('crypto key generate rsa modulus 2048', timeout=120)
            console.command('end')
        else:
            print('Eksisterende RSA-nøkler beholdes. Kontroller nøkkelstørrelsen manuelt.')
        vty_config = console.command('show running-config | section line vty')
        ranges = re.findall(r'(?m)^line vty (\d+(?: \d+)?)', vty_config) or ['0 4']
        console.command('configure terminal')
        console.command('ip ssh version 2')
        for vty_range in ranges:
            for command in [f'line vty {vty_range}', 'login local', 'transport input ssh', 'exit']:
                console.command(command)
        console.command('end')
        console.command('write memory', timeout=30)
        # README includes a manual verification of all detected VTY ranges.
        print(f"Ferdig: {host['hostname']} / {host['management']['ip']}. Test SSH fra laptoppen.")


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, serial.SerialException, RuntimeError, TimeoutError) as error:
        print(f'Stoppet: {error}', file=sys.stderr)
        sys.exit(1)
