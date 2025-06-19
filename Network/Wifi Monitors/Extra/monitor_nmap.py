import subprocess
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
import csv
import concurrent.futures

init(autoreset=True)

CSV_LOG = "wifi_log.csv"
DASHBOARD_CSV = "device_dashboard.csv"
mon_interval = 2  # seconds between scans


total_uptime = defaultdict(timedelta)   # ip -> total time joined
online_since = {}                       # ip -> datetime
hostname_cache = {}
mac_by_ip = {}
vendor_by_mac = {}


# Known MAC vendors (example subset)
mac_vendors = {
    "00:1A:2B": "Cisco",
    "F4:5C:89": "Apple",
    "3C:5A:B4": "Samsung",
    "00:1E:C2": "Dell",
    "00:0C:29": "VMware",
}


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


logger = setup_logger()


def parse_old_logs():
    joins = {}
    with open(CSV_LOG, newline='', encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=';')
        next(reader)
        for row in reader:
            if len(row) < 5:
                continue
            timestamp, event, ip, _, _ = row
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            if event == "JOIN":
                joins[ip] = dt
            elif event == "LEAVE" and ip in joins:
                duration = dt - joins.pop(ip)
                total_uptime[ip] += duration
    for ip, dt in joins.items():
        total_uptime[ip] += datetime.now() - dt
        online_since[ip] = dt


def log_event(event_type, ip, mac, hostname):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{timestamp};{event_type};{ip};{mac};{hostname}"

    with open(CSV_LOG, 'a+', encoding='utf-8') as f:
        f.write(log_line + '\n')

    color = Fore.GREEN if event_type == "JOIN" else Fore.RED
    label = "[+]" if event_type == "JOIN" else "[-]"
    status = Fore.CYAN + "JOIN" if event_type == "JOIN" else Fore.YELLOW + "LEAVE"
    print(f"{color}{label}{Style.RESET_ALL} {timestamp:<20} | {status:<6}{Style.RESET_ALL} | IP: {ip:<15} | MAC: {mac:<17} | Host: {hostname}")


def get_hostname(ip):
    if ip in hostname_cache:
        return hostname_cache[ip]
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except socket.herror:
        hostname = "Unknown"
    hostname_cache[ip] = hostname
    return hostname


def format_td(td):
    s = int(td.total_seconds())
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s"


def get_vendor(mac):
    prefix = mac.upper()[0:8].replace("-", ":")
    return mac_vendors.get(prefix[:8], "Unknown")


def scan_with_nmap(ip_range):
    try:
        result = subprocess.check_output([
            "nmap", "-sn", "-n", "--min-parallelism", "50", ip_range
        ], stderr=subprocess.DEVNULL).decode()

        hosts = []
        current_ip = None
        mac = None

        for line in result.split("\n"):
            if line.startswith("Nmap scan report for"):
                current_ip = line.split()[-1]
            elif "MAC Address" in line:
                mac = line.split()[2]
                hosts.append({"ip": current_ip, "mac": mac})
                current_ip, mac = None, None
        return hosts
    except Exception as e:
        print(f"Error running Nmap: {e}")
        return []


def export_dashboard():
    with open(DASHBOARD_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["IP", "MAC", "Hostname", "Vendor", "Uptime"])
        for ip in total_uptime:
            mac = mac_by_ip.get(ip, "N/A")
            hostname = hostname_cache.get(ip, "Unknown")
            vendor = vendor_by_mac.get(ip, "Unknown")
            uptime = format_td(total_uptime[ip])
            writer.writerow([ip, mac, hostname, vendor, uptime])


def monitor(ip_range):
    seen = set()
    active = set()
    known = set()

    def update_dashboard():
        while True:
            export_dashboard()
            time.sleep(60)

    threading.Thread(target=update_dashboard, daemon=True).start()

    while True:
        now = datetime.now()
        devices = scan_with_nmap(ip_range)
        current = set()

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(get_hostname, d['ip']): d for d in devices}
            for future in concurrent.futures.as_completed(futures):
                d = futures[future]
                ip = d['ip']
                mac = d['mac']
                hostname = future.result()
                vendor = get_vendor(mac)

                mac_by_ip[ip] = mac
                vendor_by_mac[ip] = vendor
                hostname_cache[ip] = hostname
                current.add(ip)
                known.add(ip)

                if ip not in active:
                    log_event("JOIN", ip, mac, hostname)
                    online_since[ip] = now

        for ip in list(active):
            if ip not in current:
                log_event("LEAVE", ip, mac_by_ip.get(ip, "N/A"), hostname_cache.get(ip, "Unknown"))
                if ip in online_since:
                    total_uptime[ip] += now - online_since.pop(ip)

        active.clear()
        active.update(current)
        time.sleep(mon_interval)


if __name__ == "__main__":
    subnet = "192.168.1.0/24"
    print(f"🚀 Monitoring {subnet} with Nmap...\n")
    parse_old_logs()
    monitor(subnet)