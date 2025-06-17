from datetime import datetime
import subprocess
import scapy.all as scapy
import socket
import threading
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from colorama import Fore, Style, init
import os
import csv
from datetime import datetime, timedelta
from collections import defaultdict
import shutil

uptime_tracker = defaultdict(timedelta)  # {ip: total_time_online}
online_since = {}  # {ip: datetime}

init(autoreset=True)
CSV_LOG = "wifi_log.csv"

if not os.path.exists(CSV_LOG):
    with open(CSV_LOG, "w", encoding="utf-8") as f:
        f.write("timestamp;event;ip;hostname\n")

logger = logging.getLogger("NetworkMonitor")
logger.setLevel(logging.INFO)

log_handler = TimedRotatingFileHandler(
    CSV_LOG, when="W0", interval=1, backupCount=4, encoding="utf-8"
)
log_formatter = logging.Formatter(
    '%(asctime)s;%(message)s'
)

log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)
mon_interval = .5

def log_event(event_type, ip, hostname):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    csv_message = f'{event_type};{ip};{hostname}'
    logger.info(csv_message)

    # Format the console message
    if event_type == "JOIN":
        print(
            f"{Fore.GREEN}[+]{Style.RESET_ALL} {timestamp:<20} | "
            f"{Fore.CYAN}JOIN{Style.RESET_ALL:<6} | IP: {ip:<15} | Host: {hostname}"
        )
    elif event_type == "LEAVE":
        print(
            f"{Fore.RED}[-]{Style.RESET_ALL} {timestamp:<20} | "
            f"{Fore.YELLOW}LEAVE{Style.RESET_ALL:<6} | IP: {ip:<15} | Host: {hostname}"
        )

def scan_network(ip_range):
    arp_request = scapy.ARP(pdst=ip_range)
    broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
    arp_request_broadcast = broadcast / arp_request
    answered_list = scapy.srp(arp_request_broadcast, timeout=1, verbose=False)[0]

    clients = []
    for element in answered_list:
        client_dict = {"ip": element[1].psrc, "mac": element[1].hwsrc}
        clients.append(client_dict)
    return clients
    

def get_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except socket.herror:
        return "Unknown"

def ping_devices_loop(get_ips_fn, interval=3):
    """Continuously pings all known devices every few seconds and shows dynamic status."""
    while True:
        ips = get_ips_fn()
        if not ips:
            print("\n📶 Ping Status: ⚪ No devices to ping.")
            time.sleep(interval)
            continue

        print("\n🔁 Pinging known devices:")
        alive_count = 0
        for ip in sorted(ips):
            try:
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", ip],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                is_alive = result.returncode == 0
                status = f"{Fore.GREEN}ALIVE{Style.RESET_ALL}" if is_alive else f"{Fore.RED}NO RESPONSE{Style.RESET_ALL}"
                if is_alive:
                    alive_count += 1
                print(f"  {ip:<15} -> {status}")
            except Exception as e:
                print(f"  {ip:<15} -> ERROR: {e}")

        total = len(ips)
        if alive_count == total:
            sign = f"{Fore.GREEN}✅ Good{Style.RESET_ALL}"
        elif alive_count == 0:
            sign = f"{Fore.RED}❌ Offline{Style.RESET_ALL}"
        else:
            sign = f"{Fore.YELLOW}⚠️  Partial{Style.RESET_ALL}"

        print(f"\n📶 Ping Status: {sign} ({alive_count}/{total} alive)")
        time.sleep(interval)


def monitor_network(ip_range, mon_interval=10):
    '''Start ping thread
        Start uptime summary display'''
    old_devices = set()
    # 
    def get_current_ips():
        return current_devices.copy()
    threading.Thread(target=ping_devices_loop, args=(get_current_ips,), daemon=True).start()
    # 
    threading.Thread(target=display_uptime_loop, daemon=True).start()
    while True:
        devices = scan_network(ip_range)
        current_devices = set()

        for device in devices:
            ip = device["ip"]
            hostname = get_hostname(ip)
            current_devices.add(ip)

            if ip not in old_devices:
                log_event("JOIN", ip, hostname)

        now = datetime.now()
        for ip in current_devices:
            if ip not in online_since:
                online_since[ip] = now  # new JOIN
        for ip in list(online_since):
            if ip not in current_devices:
                # device left — finalize uptime
                joined_at = online_since.pop(ip)
                uptime_tracker[ip] += now - joined_at

        # Detect devices that left
        for ip in old_devices:
            if ip not in current_devices:
                hostname = "Unknown"
                log_event("LEAVE", ip, hostname)

        old_devices = current_devices
        time.sleep(mon_interval)


def display_uptime_loop(interval=5):
    """Displays most and least active devices every N seconds."""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Fore.BLUE}📊 Device Uptime Summary (Updated Every {interval}s){Style.RESET_ALL}")
        print("=" * shutil.get_terminal_size().columns)

        # Merge current session uptime
        now = datetime.now()
        combined_uptime = uptime_tracker.copy()
        for ip, since in online_since.items():
            combined_uptime[ip] += now - since

        if not combined_uptime:
            print("No devices tracked yet.")
        else:
            sorted_ips = sorted(combined_uptime.items(), key=lambda x: x[1], reverse=True)
            most_active = sorted_ips[:3]
            least_active = sorted_ips[-3:]

            def format_entry(ip, uptime):
                hrs, rem = divmod(int(uptime.total_seconds()), 3600)
                mins, secs = divmod(rem, 60)
                return f"{ip:<16} {str(uptime).split('.')[0]:>12} ({hrs}h{mins:02d}m{secs:02d}s)"

            print(f"\n{Fore.GREEN}🟢 Most Active Devices:{Style.RESET_ALL}")
            for ip, ut in most_active:
                print("  " + format_entry(ip, ut))

            print(f"\n{Fore.RED}🔴 Least Active Devices:{Style.RESET_ALL}")
            for ip, ut in least_active:
                print("  " + format_entry(ip, ut))

        time.sleep(interval)


if __name__ == "__main__":
    subnet = "192.168.1.1/24"  # Change this to your subnet
    print(f"Starting network monitor on subnet {subnet} | Rate {mon_interval}s")
    monitor_network(subnet)
