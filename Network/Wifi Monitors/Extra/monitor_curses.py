# Enhanced Network Monitor with Curses UI, Nmap Scanning, CSV Export, Graphs & History

import curses
import threading
import subprocess
import socket
import scapy.all as scapy
import time
import csv
import os
from datetime import datetime, timedelta
from collections import defaultdict
import matplotlib.pyplot as plt
import queue

# Globals for uptime tracking
total_uptime = defaultdict(timedelta)
online_since = {}
hostname_cache = {}
mac_by_ip = {}
detailed_history = defaultdict(list)  # per-device event history

# Shared device data
devices = []
devices_lock = threading.Lock()
nmap_output = []
nmap_lock = threading.Lock()
discreet_scan_enabled = True
deep_scan_enabled = False
individual_deep_scan_requested = threading.Event()
deep_scan_queue = queue.Queue()
subnet = "192.168.1.1/24"
CSV_LOG = "wifi_log.csv"
EXPORT_FILE = "export_uptime.csv"

# Ensure CSV log exists
def setup_logger():
    if not os.path.exists(CSV_LOG):
        with open(CSV_LOG, "w", encoding="utf-8") as f:
            f.write("timestamp;event;ip;mac;hostname\n")

def log_event(event_type, ip, mac, hostname):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp};{event_type};{ip};{mac};{hostname}"
    with open(CSV_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    detailed_history[ip].append((event_type, timestamp))

# Load previous uptime from CSV
def parse_old_logs():
    joins = {}
    if not os.path.exists(CSV_LOG): return
    with open(CSV_LOG, newline='', encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=';')
        next(reader)
        for row in reader:
            if len(row) != 5: continue
            timestamp, event, ip, mac, hostname = row
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            detailed_history[ip].append((event, timestamp))
            if event == "JOIN":
                joins[ip] = dt
            elif event == "LEAVE" and ip in joins:
                total_uptime[ip] += dt - joins.pop(ip)
    for ip, dt in joins.items():
        total_uptime[ip] += datetime.now() - dt
        online_since[ip] = dt

def scan_network(ip_range):
    global devices
    while True:
        arp = scapy.ARP(pdst=ip_range)
        ether = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = ether / arp
        answered = scapy.srp(packet, timeout=1, verbose=False)[0]
        found = [{"ip": rcv.psrc, "mac": rcv.hwsrc} for _, rcv in answered]
        with devices_lock:
            devices = found
        time.sleep(5)

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

def run_nmap_discreet(ip_range):
    global nmap_output
    while True:
        if discreet_scan_enabled:
            try:
                result = subprocess.run(["nmap", "-sn", "-n", ip_range], capture_output=True, text=True, timeout=60)
                lines = ["-- Discreet Nmap Scan --"] + result.stdout.splitlines()
            except Exception as e:
                lines = [f"Discreet scan error: {e}"]
            with nmap_lock:
                nmap_output = lines
        time.sleep(60)

def run_nmap_deep_individual():
    global nmap_output
    while True:
        individual_deep_scan_requested.wait()
        try:
            ip = deep_scan_queue.get()
            result = subprocess.run(["nmap", "-A", "-T4", ip], capture_output=True, text=True, timeout=120)
            lines = [f"-- Deep Nmap Scan for {ip} --"] + result.stdout.splitlines()
        except Exception as e:
            lines = [f"Deep scan error: {e}"]
        with nmap_lock:
            nmap_output = lines
        individual_deep_scan_requested.clear()

def update_uptime(current_ips):
    now = datetime.now()
    for ip in set(total_uptime.keys()).union(online_since.keys()):
        if ip in current_ips:
            if ip not in online_since:
                online_since[ip] = now
        else:
            if ip in online_since:
                total_uptime[ip] += now - online_since.pop(ip)

def draw_dashboard(win):
    win.erase()
    height, width = win.getmaxyx()
    now = datetime.now()
    win.addstr(1, 2, f"[ DASHBOARD ] Device Uptime Summary ({now.strftime('%H:%M:%S')})")

    uptime_snapshot = {}
    with devices_lock:
        current_ips = [d["ip"] for d in devices]
    for ip in set(total_uptime.keys()).union(online_since.keys()):
        base = total_uptime[ip]
        if ip in online_since:
            base += now - online_since[ip]
        uptime_snapshot[ip] = base

    sorted_uptime = sorted(uptime_snapshot.items(), key=lambda x: x[1], reverse=True)
    half = len(sorted_uptime) // 2 or 1
    most = sorted_uptime[:half]
    least = sorted_uptime[half:]

    def draw_section(title, items, row):
        win.addstr(row, 2, f"[{title}]")
        row += 1
        win.addstr(row, 2, f"{'IP':<16} {'MAC':<18} {'Hostname':<20} {'Uptime':>10}")
        row += 1
        for ip, td in items:
            mac = mac_by_ip.get(ip, "N/A")
            hostname = hostname_cache.get(ip, "Unknown")
            uptime = format_td(td)
            win.addstr(row, 2, f"{ip:<16} {mac:<18} {hostname:<20} {uptime:>10}")
            row += 1
        return row

    r = draw_section("MOST ACTIVE DEVICES", most, 3)
    draw_section("LEAST ACTIVE DEVICES", least, r + 2)

    win.box()
    win.refresh()

def draw_nmap_output(win):
    win.erase()
    height, width = win.getmaxyx()
    win.addstr(1, 2, "[ NMAP OUTPUT ]")
    with nmap_lock:
        lines = nmap_output.copy()
    for i, line in enumerate(lines[:height - 3]):
        win.addstr(i + 2, 2, line[:width - 4])
    win.box()
    win.refresh()

def export_csv():
    with open(EXPORT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["IP", "MAC", "Hostname", "Total Uptime"])
        for ip in total_uptime:
            mac = mac_by_ip.get(ip, "N/A")
            hostname = hostname_cache.get(ip, "Unknown")
            uptime = format_td(total_uptime[ip])
            writer.writerow([ip, mac, hostname, uptime])

def draw_graph(ip):
    events = detailed_history[ip]
    if not events:
        print(f"No history for {ip}")
        return

    times = []
    states = []
    for evt, ts in events:
        times.append(datetime.strptime(ts, "%Y-%m-%d %H:%M:%S"))
        states.append(1 if evt == "JOIN" else 0)

    plt.figure(figsize=(10, 2))
    plt.step(times, states, where='post')
    plt.title(f"Uptime Graph for {ip}")
    plt.xlabel("Time")
    plt.ylabel("Online (1) / Offline (0)")
    plt.tight_layout()
    plt.savefig(f"uptime_{ip.replace('.', '_')}.png")
    plt.close()

def prompt_ip(stdscr, prompt_str="Enter IP for deep scan: "):
    curses.echo()
    stdscr.addstr(curses.LINES - 1, 0, prompt_str)
    stdscr.clrtoeol()
    ip = stdscr.getstr(curses.LINES - 1, len(prompt_str), 30).decode("utf-8").strip()
    curses.noecho()
    return ip

def monitor(stdscr):
    global discreet_scan_enabled, deep_scan_enabled
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(200)
    height, width = stdscr.getmaxyx()
    lw = width // 2
    rw = width - lw - 1
    left = curses.newwin(height - 2, lw, 0, 0)
    right = curses.newwin(height - 2, rw, 0, lw + 1)
    stdscr.vline(0, lw, curses.ACS_VLINE, height - 2)

    threading.Thread(target=scan_network, args=(subnet,), daemon=True).start()
    threading.Thread(target=run_nmap_discreet, args=(subnet,), daemon=True).start()
    threading.Thread(target=run_nmap_deep_individual, daemon=True).start()

    while True:
        with devices_lock:
            current = [d["ip"] for d in devices]
        for d in devices:
            mac_by_ip[d["ip"]] = d["mac"]
            get_hostname(d["ip"])
        update_uptime(current)

        draw_dashboard(left)
        draw_nmap_output(right)
        stdscr.addstr(height - 1, 2,
            "[d]eep toggle | [s]tealth toggle | [i]deep IP | [e]xport | [g]raph | [q]uit")
        stdscr.clrtoeol()
        stdscr.refresh()

        try:
            c = stdscr.getch()
            if c == ord('q'): break
            elif c == ord('d'): deep_scan_enabled = not deep_scan_enabled
            elif c == ord('s'): discreet_scan_enabled = not discreet_scan_enabled
            elif c == ord('i'):
                ip = prompt_ip(stdscr)
                if ip:
                    deep_scan_queue.put(ip)
                    individual_deep_scan_requested.set()
            elif c == ord('e'):
                export_csv()
            elif c == ord('g'):
                ip = prompt_ip(stdscr, "IP to graph: ")
                if ip: draw_graph(ip)
        except: pass
        time.sleep(0.2)

if __name__ == "__main__":
    setup_logger()
    parse_old_logs()
    curses.wrapper(monitor)
