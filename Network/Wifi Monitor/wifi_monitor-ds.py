import subprocess
import scapy.all as scapy
import socket
import threading
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from colorama import Fore, Style, init
from datetime import datetime, timedelta
from collections import defaultdict
import os
import shutil

init(autoreset=True)

CSV_LOG = "wifi_log.csv"
mon_interval = 0.5  # seconds between scans
ping_interval = 20   # seconds between ping rounds

total_uptime = defaultdict(timedelta)   # ip -> total time joined
online_since = {}                       # ip -> datetime

def setup_logger():
    if not os.path.exists(CSV_LOG):
        with open(CSV_LOG, "w", encoding="utf-8") as f:
            f.write("timestamp;event;ip;hostname\n")

    logger = logging.getLogger("NetworkMonitor")
    logger.setLevel(logging.INFO)
    handler = TimedRotatingFileHandler(CSV_LOG, when="W0", interval=1, backupCount=4, encoding="utf-8")
    formatter = logging.Formatter('%(asctime)s;%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

logger = setup_logger()

def log_event(event_type, ip, hostname):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{timestamp};{event_type};{ip};{hostname}"
    logger.info(log_line)

    color = Fore.GREEN if event_type == "JOIN" else Fore.RED
    label = "[+]" if event_type == "JOIN" else "[-]"
    status = Fore.CYAN + "JOIN" if event_type == "JOIN" else Fore.YELLOW + "LEAVE"
    print(f"{color}{label}{Style.RESET_ALL} {timestamp:<20} | {status:<6}{Style.RESET_ALL} | IP: {ip:<15} | Host: {hostname}")

def scan_network(ip_range):
    arp = scapy.ARP(pdst=ip_range)
    ether = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
    packet = ether / arp
    answered = scapy.srp(packet, timeout=1, verbose=False)[0]
    return [{"ip": rcv.psrc, "mac": rcv.hwsrc} for _, rcv in answered]

def get_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except socket.herror:
        return "Unknown"

def format_td(td):
    s = int(td.total_seconds())
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s"

def show_uptime_status(interval=5):
    while True:
        time.sleep(interval)
        os.system("cls" if os.name == "nt" else "clear")
        print(f"{Fore.BLUE}📊 Real-Time Device Uptime Summary{Style.RESET_ALL}\n")

        now = datetime.now()
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
        least_active = sorted_uptime[-half:]

        print(f"{Fore.GREEN}🟢 Most Active Devices:{Style.RESET_ALL}")
        for ip, ut in most_active:
            print(f"  {ip:<15} {format_td(ut):>12}")

        print(f"\n{Fore.RED}🔴 Least Active Devices:{Style.RESET_ALL}")
        for ip, ut in least_active:
            print(f"  {ip:<15} {format_td(ut):>12}")


def ping_loop(get_ips, interval=3):
    while True:
        print("\n🔁 Pinging known devices:")
        alive = 0
        for ip in get_ips():
            res = subprocess.run(["ping", "-c", "1", "-W", "1", ip], stdout=subprocess.DEVNULL)
            if res.returncode == 0:
                alive += 1
                print(f"  {ip:<15} -> {Fore.GREEN}ALIVE{Style.RESET_ALL}")
            else:
                print(f"  {ip:<15} -> {Fore.RED}NO RESPONSE{Style.RESET_ALL}")
        print(f"\n📶 Ping Status: {alive}/{len(get_ips())} responsive\n")
        time.sleep(interval)

def monitor(ip_range):
    seen = set()
    active = set()

    def get_ips():
        return list(active)

    threading.Thread(target=ping_loop, args=(get_ips,), daemon=True).start()
    threading.Thread(target=show_uptime_status, daemon=True).start()

    while True:
        devices = scan_network(ip_range)
        current = set()
        now = datetime.now()

        for d in devices:
            ip = d["ip"]
            hostname = get_hostname(ip)
            current.add(ip)
            if ip not in active:
                log_event("JOIN", ip, hostname)
                online_since[ip] = now
        
        for ip in list(active):
            if ip not in current:
                log_event("LEAVE", ip, "Unknown")
                if ip in online_since:
                    total_uptime[ip] += now - online_since.pop(ip)

        active.clear()
        active.update(current)
        time.sleep(mon_interval)

if __name__ == "__main__":
    subnet = "192.168.1.1/24"
    print(f"🚀 Monitoring {subnet}...")
    monitor(subnet)
