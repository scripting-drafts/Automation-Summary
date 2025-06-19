import curses
import threading
import subprocess
import socket
import scapy.all as scapy
import time
from datetime import datetime, timedelta
from collections import defaultdict, deque
import queue
import os
import csv
import matplotlib.pyplot as plt
import io
import base64
from flask import Flask, send_file, make_response, jsonify
import smtplib
from email.message import EmailMessage
import ssl
import signal
import shutil

# --- CONFIG ---
CSV_LOG = "wifi_log.csv"
BACKUP_DIR = "backups"
MON_INTERVAL = 0.5
SUBNET = "192.168.1.1/24"
EMAIL_TARGET = "creative.gsp@gmail.com"
EMAIL_SENDER = "your-email@example.com"      # TODO: change this to your sending email
EMAIL_PASSWORD = "your-email-password"       # TODO: change this to your email password or app password
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
REPORT_INTERVAL_SECONDS = 24 * 3600  # Daily report

# --- GLOBALS ---
total_uptime = defaultdict(timedelta)
online_since = {}
hostname_cache = {}
mac_by_ip = {}

devices = []
devices_lock = threading.Lock()

nmap_output = []
nmap_lock = threading.Lock()

discreet_scan_enabled = True
deep_scan_enabled = False
individual_deep_scan_ip = None
individual_deep_scan_requested = threading.Event()
deep_scan_queue = queue.Queue()

selected_ip = None  # For per-device deep scan navigation

# For uptime history, per device, max 2016 entries (~1 week of 5-minute intervals)
uptime_history = defaultdict(lambda: deque(maxlen=2016))

# For graceful exit
exit_event = threading.Event()

# ------------------ LOGGING & PERSISTENCE ------------------

def setup_log():
    if not os.path.exists(CSV_LOG):
        with open(CSV_LOG, "w", encoding="utf-8") as f:
            f.write("timestamp;event;ip;mac;hostname\n")

def log_event(event_type, ip, mac, hostname):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{timestamp};{event_type};{ip};{mac};{hostname}"
    with open(CSV_LOG, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")

def parse_old_logs():
    joins = {}
    if not os.path.isfile(CSV_LOG):
        return
    with open(CSV_LOG, newline='', encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=';')
        next(reader, None)
        for row in reader:
            if len(row) != 5:
                continue
            timestamp, event, ip, mac, hostname = row
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            if event == "JOIN":
                joins[ip] = dt
            elif event == "LEAVE" and ip in joins:
                total_uptime[ip] += dt - joins.pop(ip)
    # Remaining online devices
    for ip, dt in joins.items():
        total_uptime[ip] += datetime.now() - dt
        online_since[ip] = dt

def save_uptime_history():
    # Save per-device uptime history to CSV in backups folder
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    fname = os.path.join(BACKUP_DIR, f"uptime_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    with open(fname, "w", encoding="utf-8") as f:
        f.write("timestamp;ip;status\n")
        for ip, history in uptime_history.items():
            for ts, status in history:
                f.write(f"{ts.isoformat()};{ip};{status}\n")

def save_all_histories():
    # Save total uptime and history to backups folder
    backup_csv = os.path.join(BACKUP_DIR, f"wifi_log_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    shutil.copy2(CSV_LOG, backup_csv)
    save_uptime_history()

# ------------------ NETWORK SCANNING ------------------

def scan_network(ip_range):
    while not exit_event.is_set():
        try:
            arp = scapy.ARP(pdst=ip_range)
            ether = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
            packet = ether / arp
            answered = scapy.srp(packet, timeout=1, verbose=False)[0]
            found_devices = [{"ip": rcv.psrc, "mac": rcv.hwsrc} for _, rcv in answered]
            with devices_lock:
                global devices
                devices = found_devices
            time.sleep(5)
        except Exception:
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
    while not exit_event.is_set():
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
        else:
            time.sleep(1)

def run_nmap_deep_all(ip_range):
    global nmap_output
    while not exit_event.is_set():
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
            time.sleep(300)
        else:
            time.sleep(1)

def run_nmap_deep_individual():
    global nmap_output
    while not exit_event.is_set():
        individual_deep_scan_requested.wait()
        try:
            ip = deep_scan_queue.get(timeout=10)
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

# ------------------ UPTIME TRACKING ------------------

def update_uptime(active_ips):
    now = datetime.now()
    # Update total uptime for devices that left & online_since for those online
    for ip in list(total_uptime.keys()) + list(online_since.keys()):
        if ip in active_ips:
            if ip not in online_since:
                online_since[ip] = now
        else:
            if ip in online_since:
                total_uptime[ip] += now - online_since.pop(ip)

def record_uptime_history(active_ips):
    now = datetime.now()
    for ip in set(list(total_uptime.keys()) + list(online_since.keys())):
        status = "online" if ip in active_ips else "offline"
        uptime_history[ip].append((now, status))

# ------------------ CURSES UI ------------------

def draw_dashboard(win):
    win.erase()
    height, width = win.getmaxyx()
    now = datetime.now()
    win.addstr(1, 2, f"[ DASHBOARD ] Device Uptime Summary ({now.strftime('%H:%M:%S')})")

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

    # Sort descending uptime
    sorted_uptime = sorted(uptime_snapshot.items(), key=lambda x: x[1], reverse=True)
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
        status = "ONLINE" if ip in current_ips else "OFFLINE"
        return hostname, mac, uptime, status

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

def plot_uptime_graph(ip, hours=24):
    # Plot uptime graph for the selected IP (last 'hours')
    if ip not in uptime_history or len(uptime_history[ip]) == 0:
        return None
    now = datetime.now()
    cutoff = now - timedelta(hours=hours)

    times = []
    statuses = []
    for ts, status in uptime_history[ip]:
        if ts >= cutoff:
            times.append(ts)
            statuses.append(1 if status == "online" else 0)

    if len(times) < 2:
        return None

    plt.figure(figsize=(6, 2))
    plt.step(times, statuses, where='post')
    plt.ylim(-0.1, 1.1)
    plt.yticks([0, 1], ['Offline', 'Online'])
    plt.title(f"Uptime for {ip} last {hours} hours")
    plt.xlabel("Time")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    return buf

def save_plot_png(buf, fname):
    with open(fname, "wb") as f:
        f.write(buf.read())
    buf.seek(0)

def prompt_ip(stdscr, prompt_str="Enter IP for deep scan: "):
    curses.echo()
    stdscr.addstr(curses.LINES - 1, 0, prompt_str)
    stdscr.clrtoeol()
    ip = stdscr.getstr(curses.LINES - 1, len(prompt_str), 30).decode("utf-8").strip()
    curses.noecho()
    return ip

# ------------------ CSV EXPORT ------------------

def export_csv():
    # Write full device uptime info to CSV
    fname = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(fname, "w", encoding="utf-8") as f:
        f.write("ip,mac,hostname,total_uptime_seconds\n")
        with devices_lock:
            ips = set(mac_by_ip.keys())
        for ip in ips:
            hostname = hostname_cache.get(ip, "Unknown")
            mac = mac_by_ip.get(ip, "N/A")
            uptime_sec = int(total_uptime[ip].total_seconds())
            f.write(f"{ip},{mac},{hostname},{uptime_sec}\n")
    return fname

# ------------------ EMAIL REPORT ------------------

def send_email_report():
    try:
        # Compose email with CSV export attached
        fname = export_csv()

        msg = EmailMessage()
        msg['Subject'] = 'Daily Network Uptime Report'
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_TARGET
        msg.set_content(f"Attached is the daily uptime report.\n\nGenerated on {datetime.now().isoformat()}")

        with open(fname, 'rb') as f:
            file_data = f.read()
            file_name = os.path.basename(fname)
        msg.add_attachment(file_data, maintype='text', subtype='csv', filename=file_name)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"[Email] Report sent successfully to {EMAIL_TARGET}")
    except Exception as e:
        print(f"[Email] Failed to send report: {e}")

def periodic_report_worker():
    while not exit_event.is_set():
        send_email_report()
        # Save backups
        save_all_histories()
        # Sleep until next report
        for _ in range(REPORT_INTERVAL_SECONDS):
            if exit_event.is_set():
                break
            time.sleep(1)

# ------------------ HTTP SERVER ------------------

app = Flask(__name__)

@app.route('/export.csv')
def serve_csv():
    if not os.path.exists(CSV_LOG):
        return "No CSV log available.", 404
    return send_file(CSV_LOG, mimetype='text/csv', download_name='wifi_log.csv')

@app.route('/uptime_graph/<ip>')
def serve_graph(ip):
    buf = plot_uptime_graph(ip, hours=24)
    if buf is None:
        return jsonify({"error": "Not enough data for graph"}), 404
    response = make_response(buf.getvalue())
    response.headers.set('Content-Type', 'image/png')
    return response

def run_http_server():
    app.run(port=5000, debug=False, use_reloader=False)

# ------------------ MAIN MONITORING LOOP ------------------

def monitor(stdscr):
    global discreet_scan_enabled, deep_scan_enabled, individual_deep_scan_ip, selected_ip

    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(200)

    height, width = stdscr.getmaxyx()

    left_width = width // 2
    right_width = width - left_width - 1

    left_win = curses.newwin(height - 2, left_width, 0, 0)
    right_win = curses.newwin(height - 2, right_width, 0, left_width + 1)

    stdscr.vline(0, left_width, curses.ACS_VLINE, height - 2)

    # Start background threads
    threading.Thread(target=scan_network, args=(SUBNET,), daemon=True).start()
    threading.Thread(target=run_nmap_discreet, args=(SUBNET,), daemon=True).start()
    threading.Thread(target=run_nmap_deep_all, args=(SUBNET,), daemon=True).start()
    threading.Thread(target=run_nmap_deep_individual, daemon=True).start()

    active_ips = set()
    known_ips = set()

    last_history_record = datetime.now()

    while True:
        with devices_lock:
            current_devices = devices.copy()

        now = datetime.now()
        current_ips = set(d["ip"] for d in current_devices)

        # Update MAC and hostname cache
        for d in current_devices:
            mac_by_ip[d["ip"]] = d["mac"]
            get_hostname(d["ip"])

        # Update uptime tracking
        update_uptime(current_ips)
        record_uptime_history(current_ips)

        active_ips = current_ips
        known_ips.update(current_ips)

        draw_dashboard(left_win)
        draw_nmap_output(right_win)

        # Show selected IP uptime
