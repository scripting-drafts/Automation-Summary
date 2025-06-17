import time
import socket
import threading
import sys
from scapy.all import ARP, Ether, srp
from colorama import Fore, Style, init

init(autoreset=True)

LOG_FILE = "wifi_log.txt"

# ------------------------
# Logging Setup
# ------------------------

class Logger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

# Replace stdout with logger
sys.stdout = Logger(LOG_FILE)

# ------------------------
# Network Scanning Functions
# ------------------------

def scan_network(subnet):
    """Fast ARP scan for active devices on the network."""
    arp = ARP(pdst=subnet)
    ether = Ether(dst="ff:ff:ff:ff:ff:ff")
    packet = ether / arp
    result = srp(packet, timeout=2, verbose=False)[0]

    devices = {}
    for _, received in result:
        ip = received.psrc
        mac = received.hwsrc
        devices[mac] = {"ip": ip, "hostname": "Resolving..."}
    return devices

def resolve_hostnames(devices):
    """Try to resolve hostnames in the background."""
    def resolver(mac, ip):
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except:
            hostname = "Unknown"
        devices[mac]["hostname"] = hostname

    for mac, info in devices.items():
        if info["hostname"] == "Resolving...":
            thread = threading.Thread(target=resolver, args=(mac, info["ip"]))
            thread.daemon = True
            thread.start()

def display_devices(devices):
    print("\n📡 Current Devices on Network:")
    print("-" * 60)
    print(f"{'IP Address':<16} {'MAC Address':<18} {'Hostname'}")
    print("-" * 60)
    for mac, info in devices.items():
        print(f"{info['ip']:<16} {mac:<18} {info['hostname']}")
    print("-" * 60)

def print_device_event(event_type, mac, info):
    symbol = "+" if event_type == "joined" else "-"
    color = Fore.GREEN if event_type == "joined" else Fore.RED
    print(color + f"[{symbol}] {event_type.upper():7} | {info['ip']} ({mac}) - {info['hostname']}")

def monitor_network(subnet, interval=10):
    print(f"🌐 Monitoring devices on {subnet} every {interval} seconds...\n")

    known_devices = scan_network(subnet)
    resolve_hostnames(known_devices)
    display_devices(known_devices)

    try:
        while True:
            current_devices = scan_network(subnet)
            resolve_hostnames(current_devices)

            new_macs = current_devices.keys() - known_devices.keys()
            for mac in new_macs:
                print_device_event("joined", mac, current_devices[mac])

            left_macs = known_devices.keys() - current_devices.keys()
            for mac in left_macs:
                print_device_event("left", mac, known_devices[mac])

            known_devices = current_devices
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped.")

if __name__ == "__main__":
    subnet = "192.168.1.0/24"  # Set to your local subnet
    monitor_network(subnet, interval=10)
