import subprocess
import csv
import time
from datetime import datetime
import os

ACTIVE_DEVICES_FILE = "active_devices.txt"
LOG_FILE = "wifi_log.csv"
SCAN_LOG_FILE = "deep_scan_results.txt"

def load_current_devices():
    if not os.path.exists(ACTIVE_DEVICES_FILE):
        return []

    with open(ACTIVE_DEVICES_FILE, "r") as f:
        return [line.strip().split(",")[0] for line in f if line.strip()]

def load_left_devices():
    left_ips = set()
    if not os.path.exists(LOG_FILE):
        return left_ips

    with open(LOG_FILE, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if len(row) < 4:
                continue
            timestamp_str, event_type, ip, hostname = row
            if event_type == "LEAVE":
                left_ips.add(ip)
    return left_ips

def deep_scan(ip):
    try:
        print(f"[SCAN] Deep scanning {ip} ...")
        result = subprocess.check_output(
            ["nmap", "-T4", "-A", "-p-", ip], stderr=subprocess.STDOUT
        ).decode()
        return result
    except subprocess.CalledProcessError as e:
        return f"Error scanning {ip}: {e.output.decode()}"

def log_scan_result(ip, scan_result):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(SCAN_LOG_FILE, "a") as f:
        f.write(f"\n\n--- {timestamp} - {ip} ---\n")
        f.write(scan_result)
        f.write("\n")

def main():
    active_ips = load_current_devices()
    left_ips = load_left_devices()

    devices_to_scan = [ip for ip in active_ips if ip not in left_ips]

    print(f"Found {len(devices_to_scan)} active device(s) to scan.")

    for ip in devices_to_scan:
        result = deep_scan(ip)
        log_scan_result(ip, result)

    print("Deep scan complete. Results saved in deep_scan_results.txt")

if __name__ == "__main__":
    main()
