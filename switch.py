import serial
import time
import getpass
import sys


# ============================================================
# INNSTILLINGER
# ============================================================

BAUDRATE = 9600
RSA_BITS = 2048


# ============================================================
# SERIAL-FUNKSJONER
# ============================================================

def read_serial(ser, timeout=4, quiet_time=0.5):
    data = bytearray()

    start = time.time()
    last_data = time.time()

    while time.time() - start < timeout:

        if ser.in_waiting:
            data.extend(ser.read(ser.in_waiting))
            last_data = time.time()

        else:
            if data and time.time() - last_data >= quiet_time:
                break

            time.sleep(0.05)

    return data.decode(errors="ignore")


def send_command(
    ser,
    command,
    timeout=4,
    show_command=True
):
    if show_command:
        print(f"\n>>> {command}")
    else:
        print("\n>>> [skjult kommando]")

    ser.write((command + "\r\n").encode())
    ser.flush()

    output = read_serial(
        ser,
        timeout=timeout
    )

    if output:
        print(output)

    return output


def send_hidden(
    ser,
    value,
    timeout=4
):
    print("\n>>> [skjult]")

    ser.write((value + "\r\n").encode())
    ser.flush()

    output = read_serial(
        ser,
        timeout=timeout
    )

    if output:
        print(output)

    return output


# ============================================================
# ENABLE MODE
# ============================================================

def enable_mode(
    ser,
    enable_password
):
    ser.write(b"\r\n")
    time.sleep(0.5)

    output = read_serial(
        ser,
        timeout=2
    )

    if output:
        print(output)

    if output.rstrip().endswith("#"):
        print("[OK] Allerede i enable mode.")
        return True

    output = send_command(
        ser,
        "enable"
    )

    if "password" in output.lower():

        if not enable_password:
            print("[FEIL] Enable-passord kreves.")
            return False

        output = send_hidden(
            ser,
            enable_password
        )

    if output.rstrip().endswith("#"):
        print("[OK] Enable mode aktiv.")
        return True

    print(
        "[ADVARSEL] Kunne ikke sikkert "
        "bekrefte enable mode."
    )

    return True


# ============================================================
# START
# ============================================================

print("""
==================================================
         CISCO SSH CONFIGURATION TOOL
==================================================

Scriptet konfigurerer:

- Hostname
- Domain name
- Lokal SSH-bruker
- Management VLAN
- Management IP
- Access-port for test-PC
- RSA 2048
- SSH version 2
- CBC-kryptering
- SHA1 KEX for eldre IOS
- VTY SSH

==================================================
""")


# ============================================================
# INPUT
# ============================================================

com_port = input(
    "COM-port (f.eks. COM3): "
).strip()


device_type = input(
    "Enhetstype (switch/router): "
).strip().lower()


if device_type not in [
    "switch",
    "router"
]:
    print("Skriv switch eller router.")
    sys.exit(1)


hostname = input(
    "Hostname (f.eks. SW1): "
).strip()


domain_name = input(
    "Domain name (f.eks. amuove.local): "
).strip()


username = input(
    "SSH-brukernavn: "
).strip()


ssh_password = getpass.getpass(
    "SSH-passord: "
)


old_enable = getpass.getpass(
    "Eksisterende enable-passord "
    "(Enter hvis ingen): "
)


new_enable = getpass.getpass(
    "Nytt enable secret: "
)


# ============================================================
# SWITCH INPUT
# ============================================================

if device_type == "switch":

    management_vlan = input(
        "Management VLAN (f.eks. 99): "
    ).strip()

    management_ip = input(
        "Management-IP "
        "(f.eks. 192.168.0.2): "
    ).strip()

    subnet_mask = input(
        "Subnet mask "
        "(f.eks. 255.255.255.0): "
    ).strip()

    access_port = input(
        "Port test-PC er koblet til "
        "(f.eks. GigabitEthernet1/0/1): "
    ).strip()


# ============================================================
# ROUTER INPUT
# ============================================================

else:

    router_interface = input(
        "Router-interface "
        "(f.eks. GigabitEthernet0/0): "
    ).strip()

    management_ip = input(
        "IP-adresse: "
    ).strip()

    subnet_mask = input(
        "Subnet mask: "
    ).strip()


# ============================================================
# SERIAL CONNECTION
# ============================================================

print("\n========================================")
print(" Kobler til Cisco via console")
print("========================================")


try:

    ser = serial.Serial(
        port=com_port,
        baudrate=BAUDRATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.2
    )

except Exception as error:

    print(
        f"[FEIL] Kunne ikke åpne {com_port}"
    )

    print(error)

    sys.exit(1)


time.sleep(2)

print(
    f"[OK] Tilkoblet {com_port}"
)


# ============================================================
# ENABLE
# ============================================================

if not enable_mode(
    ser,
    old_enable
):
    ser.close()
    sys.exit(1)


# ============================================================
# GLOBAL CONFIG
# ============================================================

send_command(
    ser,
    "configure terminal"
)


send_command(
    ser,
    "no ip domain-lookup"
)


# ============================================================
# HOSTNAME
# ============================================================

send_command(
    ser,
    f"hostname {hostname}"
)


# ============================================================
# DOMAIN NAME
# ============================================================

send_command(
    ser,
    f"ip domain-name {domain_name}"
)


# ============================================================
# ENABLE SECRET
# ============================================================

send_command(
    ser,
    f"enable secret {new_enable}",
    show_command=False
)


# ============================================================
# SSH USER
# ============================================================

send_command(
    ser,
    f"username {username} "
    f"privilege 15 "
    f"secret {ssh_password}",
    show_command=False
)


# ============================================================
# SWITCH CONFIGURATION
# ============================================================

if device_type == "switch":

    print("\n========================================")
    print(" Management VLAN")
    print("========================================")


    # --------------------------------------------------------
    # CREATE VLAN
    # --------------------------------------------------------

    send_command(
        ser,
        f"vlan {management_vlan}"
    )

    send_command(
        ser,
        f"name MANAGEMENT_{management_vlan}"
    )

    send_command(
        ser,
        "exit"
    )


    # --------------------------------------------------------
    # MANAGEMENT SVI
    # --------------------------------------------------------

    send_command(
        ser,
        f"interface vlan {management_vlan}"
    )

    send_command(
        ser,
        f"ip address "
        f"{management_ip} "
        f"{subnet_mask}"
    )

    send_command(
        ser,
        "no shutdown"
    )

    send_command(
        ser,
        "exit"
    )


    # --------------------------------------------------------
    # ACCESS PORT FOR SSH TEST PC
    # --------------------------------------------------------

    print("\n========================================")
    print(" Access-port for SSH-PC")
    print("========================================")


    send_command(
        ser,
        f"interface {access_port}"
    )

    send_command(
        ser,
        "switchport"
    )

    send_command(
        ser,
        "switchport mode access"
    )

    send_command(
        ser,
        f"switchport access vlan "
        f"{management_vlan}"
    )

    send_command(
        ser,
        "spanning-tree portfast"
    )

    send_command(
        ser,
        "no shutdown"
    )

    send_command(
        ser,
        "exit"
    )


# ============================================================
# ROUTER CONFIGURATION
# ============================================================

else:

    print("\n========================================")
    print(" Router-interface")
    print("========================================")


    send_command(
        ser,
        f"interface {router_interface}"
    )

    send_command(
        ser,
        f"ip address "
        f"{management_ip} "
        f"{subnet_mask}"
    )

    send_command(
        ser,
        "no shutdown"
    )

    send_command(
        ser,
        "exit"
    )


# ============================================================
# SSH VERSION 2
# ============================================================

print("\n========================================")
print(" SSH CONFIGURATION")
print("========================================")


send_command(
    ser,
    "ip ssh version 2"
)


send_command(
    ser,
    "ip ssh time-out 60"
)


send_command(
    ser,
    "ip ssh authentication-retries 3"
)


# ============================================================
# RSA
# ============================================================

print("\n========================================")
print(" RSA KEY")
print("========================================")


rsa_output = send_command(
    ser,
    f"crypto key generate rsa "
    f"modulus {RSA_BITS}",
    timeout=15
)


# Dersom RSA-key allerede finnes
if "replace" in rsa_output.lower():

    send_command(
        ser,
        "yes",
        timeout=15
    )


# ============================================================
# SSH ENCRYPTION
#
# Dette er oppsettet dere har fått fra læreren.
#
# ============================================================

print("\n========================================")
print(" SSH CBC encryption")
print("========================================")


send_command(
    ser,
    "ip ssh server algorithm encryption "
    "aes128-cbc "
    "3des-cbc "
    "aes192-cbc "
    "aes256-cbc"
)

# ============================================================
# VTY
# ============================================================

print("\n========================================")
print(" VTY CONFIGURATION")
print("========================================")


send_command(
    ser,
    "line vty 0 15"
)


send_command(
    ser,
    "login local"
)


send_command(
    ser,
    "transport input ssh"
)


send_command(
    ser,
    "exec-timeout 15 0"
)


send_command(
    ser,
    "exit"
)


# ============================================================
# END CONFIG
# ============================================================

send_command(
    ser,
    "end"
)


# ============================================================
# VERIFY SSH
# ============================================================

print("\n========================================")
print(" SSH VERIFICATION")
print("========================================")


send_command(
    ser,
    "show ip ssh",
    timeout=5
)


# ============================================================
# VERIFY INTERFACES
# ============================================================

send_command(
    ser,
    "show ip interface brief",
    timeout=5
)


if device_type == "switch":

    send_command(
        ser,
        "show vlan brief",
        timeout=5
    )

    send_command(
        ser,
        "show interfaces status",
        timeout=5
    )


# ============================================================
# VERIFY VTY
# ============================================================

send_command(
    ser,
    "show running-config | section line vty",
    timeout=5
)


# ============================================================
# SAVE
# ============================================================

print("\n========================================")
print(" SAVE CONFIG")
print("========================================")


send_command(
    ser,
    "write memory",
    timeout=10
)


# ============================================================
# CLOSE SERIAL
# ============================================================

ser.close()


# ============================================================
# RESULT
# ============================================================

print("""
==================================================
                    FERDIG
==================================================
""")


print(
    f"Hostname:        {hostname}"
)

print(
    f"SSH IP:          {management_ip}"
)

print(
    f"SSH bruker:      {username}"
)


if device_type == "switch":

    print(
        f"Management VLAN: {management_vlan}"
    )

    print(
        f"Access-port:     {access_port}"
    )


print("""
SSH-serveren er konfigurert med:

aes128-cbc
3des-cbc
aes192-cbc
aes256-cbc
""")


print(
    "Test først:\n"
    f"ping {management_ip}"
)


print(
    "\nHvis du tester fra en annen Cisco-enhet:\n"
)


print(
    f"ssh -l {username} "
    f"-c aes128-cbc "
    f"{management_ip}"
)


print(
    "\nHvis du tester fra Windows OpenSSH "
    "og får KEX-feil:\n"
)


print(
    f"ssh "
    f"-o KexAlgorithms=+diffie-hellman-group14-sha1 "
    f"-o HostKeyAlgorithms=+ssh-rsa "
    f"-c aes128-cbc "
    f"{username}@{management_ip}"
)