import curses
import threading
import subprocess
import socket
import scapy.all as scapy
import time
from datetime import datetime, timedelta
from collections import defaultdict
import queue

# Globals for uptime tracking
total_uptime = defaultdict(timedelta)  # ip -> total time online
online_since = {}                      # ip -> datetime when came online
hostname_cache = {}
mac_by_ip = {}

# Shared device data updated by scans
devices = []
devices_lock = threading.Lock()

# Nmap scan outputs
nmap_output = []
nmap_lock = threading.Lock()

# Scan control flags
discreet_scan_enabled = True
deep_scan_enabled = False
individual_deep_scan_ip = None
individual_deep_scan_requested = threading.Event()

# Queue for deep scan requests (for thread-safe input)
deep_scan_queue = queue.Queue()

# Monitoring subnet (change as needed)
subnet = "192.168.1.1/24"

def scan_network(ip_range):
    """ARP scan via scapy - runs in background thread"""
    global devices
    while True:
        arp = scapy.ARP(pdst=ip_range)
        ether = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = ether / arp
        answered = scapy.srp(packet, timeout=1, verbose=False)[0]
        found_devices = [{"ip": rcv.psrc, "mac": rcv.hwsrc} for _, rcv in answered]
        with devices_lock:
            devices = found_devices
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
    """Background thread for running discreet Nmap scans"""
    global nmap_output
    while True:
        if discreet_scan_enabled:
            try:
                result = subprocess.run(
                    ["nmap", "-sn", "-n", ip_range],
                    capture_output=True, text=True, timeout=60
                )
                lines = ["-- Discreet Nmap Scan --"] + result.stdout.splitlines()
            except Exception as e:
                lines = [f"Discreet scan error: {e}"]
            with nmap_lock:
                nmap_output = lines
        time.sleep(60)

def run_nmap_deep_all(ip_range):
    """Background thread for running deep Nmap scan on whole subnet"""
    global nmap_output
    while True:
        if deep_scan_enabled:
            try:
                result = subprocess.run(
                    ["nmap", "-A", "-T4", ip_range],
                    capture_output=True, text=True, timeout=180
                )
                lines = ["-- Deep Nmap Scan (All Devices) --"] + result.stdout.splitlines()
            except Exception as e:
                lines = [f"Deep scan error: {e}"]
            with nmap_lock:
                nmap_output = lines
            # Sleep long after scan to avoid overload
            time.sleep(300)
        else:
            time.sleep(1)

def run_nmap_deep_individual():
    """Background thread to handle individual deep scan requests"""
    global nmap_output
    while True:
        individual_deep_scan_requested.wait()
        try:
            ip = deep_scan_queue.get()
            result = subprocess.run(
                ["nmap", "-A", "-T4", ip],
                capture_output=True, text=True, timeout=120
            )
            lines = [f"-- Deep Nmap Scan for {ip} --"] + result.stdout.splitlines()
        except Exception as e:
            lines = [f"Deep individual scan error: {e}"]
        with nmap_lock:
            nmap_output = lines
        individual_deep_scan_requested.clear()

def update_uptime(active_ips):
    now = datetime.now()
    # Update total uptime for devices that left
    for ip in list(total_uptime.keys()) + list(online_since.keys()):
        if ip in active_ips:
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

    # Snapshot uptime (total + current session)
    uptime_snapshot = {}
    with devices_lock:
        current_ips = [d["ip"] for d in devices]
    for ip in set(list(total_uptime.keys()) + list(online_since.keys())):
        base = total_uptime[ip]
        if ip in online_since:
            base += now - online_since[ip]
        uptime_snapshot[ip] = base

    if not uptime_snapshot:
        win.addstr(3, 2, "No devices tracked yet.")
        win.box()
        win.refresh()
        return

    # Sort by uptime descending
    sorted_uptime = sorted(uptime_snapshot.items(), key=lambda x: x[1], reverse=True)

    # Split into two lists - most active and least active (balanced)
    mid = len(sorted_uptime) // 2 or 1
    most_active = sorted_uptime[:mid]
    least_active = sorted_uptime[mid:]

    col_ip = 16
    col_mac = 20
    col_host = 28
    col_uptime = 12
    col_status = 10

    def get_info(ip):
        hostname = hostname_cache.get(ip, "Unknown")
        mac = mac_by_ip.get(ip, "N/A")
        uptime = format_td(uptime_snapshot[ip])
        if ip in current_ips:
            status = "ONLINE"
        else:
            status = "OFFLINE"
        return hostname, mac, uptime, status

    # Print Most Active devices
    row = 3
    win.addstr(row, 2, "[ MOST ACTIVE DEVICES ]")
    row += 1
    header = f"{'IP':<{col_ip}} {'MAC':<{col_mac}} {'Hostname':<{col_host}} {'Uptime':>{col_uptime}} {'Status':>{col_status}}"
    win.addstr(row, 2, header)
    row += 1
    win.hline(row, 2, curses.ACS_HLINE, len(header))
    row += 1
    for ip, _ in most_active:
        if row >= height - 3:
            break
        hostname, mac, uptime, status = get_info(ip)
        line = f"{ip:<{col_ip}} {mac:<{col_mac}} {hostname:<{col_host}} {uptime:>{col_uptime}} {status:>{col_status}}"
        win.addstr(row, 2, line)
        row += 1

    row += 1
    if row < height - 3:
        # Print Least Active devices
        win.addstr(row, 2, "[ LEAST ACTIVE DEVICES ]")
        row += 1
        win.addstr(row, 2, header)
        row += 1
        win.hline(row, 2, curses.ACS_HLINE, len(header))
        row += 1
        for ip, _ in least_active:
            if row >= height - 3:
                break
            hostname, mac, uptime, status = get_info(ip)
            line = f"{ip:<{col_ip}} {mac:<{col_mac}} {hostname:<{col_host}} {uptime:>{col_uptime}} {status:>{col_status}}"
            win.addstr(row, 2, line)
            row += 1

    win.box()
    win.refresh()

def draw_nmap_output(win):
    win.erase()
    height, width = win.getmaxyx()

    win.addstr(1, 2, "[ NMAP SCAN OUTPUT ]")

    with nmap_lock:
        lines = nmap_output.copy()

    max_lines = height - 3
    for i, line in enumerate(lines[:max_lines]):
        try:
            win.addstr(i + 2, 2, line[:width - 4])
        except curses.error:
            pass

    win.box()
    win.refresh()

def prompt_ip(stdscr, prompt_str="Enter IP for deep scan: "):
    curses.echo()
    stdscr.addstr(curses.LINES - 1, 0, prompt_str)
    stdscr.clrtoeol()
    ip = stdscr.getstr(curses.LINES - 1, len(prompt_str), 30).decode("utf-8").strip()
    curses.noecho()
    return ip

def monitor(stdscr):
    global discreet_scan_enabled, deep_scan_enabled, individual_deep_scan_ip

    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(200)  # 200 ms input wait

    height, width = stdscr.getmaxyx()

    left_width = width // 2
    right_width = width - left_width - 1

    left_win = curses.newwin(height - 2, left_width, 0, 0)
    right_win = curses.newwin(height - 2, right_width, 0, left_width + 1)

    stdscr.vline(0, left_width, curses.ACS_VLINE, height - 2)

    # Start scanning threads
    threading.Thread(target=scan_network, args=(subnet,), daemon=True).start()
    threading.Thread(target=run_nmap_discreet, args=(subnet,), daemon=True).start()
    threading.Thread(target=run_nmap_deep_all, args=(subnet,), daemon=True).start()
    threading.Thread(target=run_nmap_deep_individual, daemon=True).start()

    active_ips = set()
    known_ips = set()

    while True:
        with devices_lock:
            current_devices = devices.copy()
        
        now = datetime.now()
        new_ips = set(d["ip"] for d in current_devices)

        # Register MACs
        for d in current_devices:
            mac_by_ip[d["ip"]] = d["mac"]
            get_hostname(d["ip"])  # Pre-cache hostname

        # JOIN detection
        for ip in new_ips:
            if ip not in online_since:
                online_since[ip] = now

        # LEAVE detection
        for ip in list(online_since.keys()):
            if ip not in new_ips:
                total_uptime[ip] += now - online_since.pop(ip)


        active_ips = current_ips
        known_ips.update(current_ips)

        draw_dashboard(left_win)
        draw_nmap_output(right_win)

        stdscr.addstr(height - 1, 2,
            "Toggle Deep Scan [d] | Individual Deep Scan [i] | Toggle Discreet Scan [s] | Quit [q]")
        stdscr.clrtoeol()
        stdscr.refresh()

        try:
            c = stdscr.getch()
            if c == ord('q'):
                break
            elif c == ord('d'):
                deep_scan_enabled = not deep_scan_enabled
            elif c == ord('s'):
                global discreet_scan_enabled
                discreet_scan_enabled = not discreet_scan_enabled
            elif c == ord('i'):
                ip = prompt_ip(stdscr)
                if ip:
                    deep_scan_queue.put(ip)
                    individual_deep_scan_requested.set()
        except Exception:
            pass

        time.sleep(0.1)

if __name__ == "__main__":
    curses.wrapper(monitor)
