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

init(autoreset=True)

CSV_LOG = "wifi_log.csv"
UPTIME_FILE = "uptime_data.csv"
mon_interval = 2  # seconds between scans

# State
total_uptime = defaultdict(timedelta)   # ip -> total time joined
online_since = {}                       # ip -> datetime
hostname_cache = {}                     # ip -> hostname
mac_by_ip = {}                          # ip -> mac


def setup_logger():
    if not os.path.exists(CSV_LOG):
        with open(CSV_LOG, "w", encoding="utf-8") as f:
            f.write("timestamp;event;ip;mac;hostname\n")

    logger = logging.getLogger("NetworkMonitor")
    logger.setLevel(logging.INFO)

    file_handler = TimedRotatingFileHandler(CSV_LOG, when="W0", interval=1, backupCount=4, encoding="utf-8")
    file_formatter = logging.Formatter('%(asctime)s;%(message)s', datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(file_formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(file_formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    return logger


def log_event(event_type, ip, mac, hostname):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{timestamp};{event_type};{ip};{mac};{hostname}"
    with open(CSV_LOG, 'a+', encoding='utf-8') as f:
        f.write(log_line + '\n')

    if event_type == "JOIN":
        color = Fore.LIGHTGREEN_EX + Back.BLACK
        label = "[ + ]"
        status = Fore.CYAN + "JOIN"
    else:
        color = Fore.LIGHTRED_EX + Back.BLACK
        label = "[ - ]"
        status = Fore.YELLOW + "LEAVE"

    print(f"{color}{label}{Style.RESET_ALL}  {timestamp:<20}  |  {status:<6}{Style.RESET_ALL}  |  IP: {ip:<15}  |  MAC: {mac:<17}  |  Host: {hostname}")


def scan_network(ip_range):
    arp = scapy.ARP(pdst=ip_range)
    ether = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
    packet = ether / arp
    answered = scapy.srp(packet, timeout=1, verbose=False)[0]
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


def save_uptime():
    with open(UPTIME_FILE, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        for ip, td in total_uptime.items():
            writer.writerow([ip, int(td.total_seconds())])


def load_uptime():
    if not os.path.isfile(UPTIME_FILE):
        return
    with open(UPTIME_FILE, newline='', encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=';')
        for row in reader:
            if len(row) != 2:
                continue
            ip, seconds = row
            total_uptime[ip] = timedelta(seconds=int(seconds))


def uptime_autosave():
    while True:
        save_uptime()
        time.sleep(30)


def display_status():
    while True:
        time.sleep(5)
        os.system("cls" if os.name == "nt" else "clear")
        now = datetime.now()

        print(f"\n{Fore.BLUE}{'=' * 80}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{Back.BLACK}[ DASHBOARD ] Device Uptime Summary ({now.strftime('%H:%M:%S')}){Style.RESET_ALL}\n")

        uptime_snapshot = {}
        for ip in set(list(total_uptime.keys()) + list(online_since.keys())):
            base = total_uptime[ip]
            if ip in online_since:
                base += now - online_since[ip]
            uptime_snapshot[ip] = base

        if not uptime_snapshot:
            print("No devices tracked yet.\n")
            continue

        sorted_uptime = sorted(uptime_snapshot.items(), key=lambda x: x[1], reverse=True)
        half = len(sorted_uptime) // 2 or 1
        most_active = sorted_uptime[:half]
        least_active = sorted_uptime[half:]

        def get_info(ip):
            hostname = hostname_cache.get(ip, "Unresolved")
            mac = mac_by_ip.get(ip, "N/A")
            uptime = format_td(uptime_snapshot[ip])
            if ip in online_since:
                status = Fore.LIGHTGREEN_EX + Back.BLACK + " ONLINE  "
            else:
                status = Fore.LIGHTRED_EX + Back.BLACK + " OFFLINE "
            return hostname, mac, uptime, status

        print(f"{Fore.LIGHTGREEN_EX}{Back.BLACK}[ MOST ACTIVE DEVICES ]{Style.RESET_ALL}\n")
        print(f"{'IP':<18} {'MAC':<20} {'Hostname':<28} {'Uptime':>12} {'Status':>10}")
        print("-" * 90)
        for ip, _ in most_active:
            hostname, mac, uptime, status = get_info(ip)
            print(f"{ip:<18} {mac:<20} {hostname:<28} {uptime:>12} {status:>10}")

        print(f"\n{Fore.LIGHTRED_EX}{Back.BLACK}[ LEAST ACTIVE DEVICES ]{Style.RESET_ALL}\n")
        print(f"{'IP':<18} {'MAC':<20} {'Hostname':<28} {'Uptime':>12} {'Status':>10}")
        print("-" * 90)
        for ip, _ in least_active:
            hostname, mac, uptime, status = get_info(ip)
            print(f"{ip:<18} {mac:<20} {hostname:<28} {uptime:>12} {status:>10}")

        print('\n')


def monitor(ip_range):
    threading.Thread(target=uptime_autosave, daemon=True).start()
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
            get_hostname(ip)

            if ip not in online_since:
                online_since[ip] = now
                log_event("JOIN", ip, mac, hostname_cache[ip])

        # Detect LEAVES
        for ip in list(online_since.keys()):
            if ip not in seen_ips:
                total_uptime[ip] += now - online_since.pop(ip)
                log_event("LEAVE", ip, mac_by_ip.get(ip, "N/A"), hostname_cache.get(ip, "Unresolved"))

        time.sleep(mon_interval)


if __name__ == "__main__":
    subnet = "192.168.1.1/24"
    print(f"{Fore.BLUE}{Back.BLACK}[ * ]{Style.RESET_ALL} Monitoring {subnet}...\n")
    load_uptime()
    monitor(subnet)
