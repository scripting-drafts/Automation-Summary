import os
import re
import subprocess
import time
from datetime import datetime
from colorama import Fore, Back, Style, init

init(autoreset=True)

REFRESH_SECONDS = 6

def scan_wifi_networks():
    try:
        result = subprocess.check_output(['nmcli', '-f', 'SSID,BSSID,CHAN,RATE,SIGNAL,SECURITY', 'device', 'wifi', 'list'], encoding='utf-8')
        return result
    except Exception as e:
        return str(e)

def parse_nmcli_output(raw):
    lines = raw.strip().split('\n')
    if len(lines) < 2:
        return []

    headers = [h.strip().lower() for h in lines[0].split()]
    entries = []

    for line in lines[1:]:
        if not line.strip():
            continue
        try:
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) >= 5:
                entry = {
                    'ssid': parts[0],
                    'bssid': parts[1],
                    'channel': parts[2],
                    'rate': parts[3],
                    'signal': int(parts[4]),
                    'security': parts[5] if len(parts) > 5 else "Unknown"
                }
                entries.append(entry)
        except Exception:
            continue
    return entries

def display_dashboard(networks):
    os.system('cls' if os.name == 'nt' else 'clear')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{Fore.CYAN}{'='*100}")
    print(f"{Fore.CYAN}[ WIFI AP MONITOR ] {now} — Showing Nearby Access Points")
    print(f"{'='*100}{Style.RESET_ALL}\n")

    if not networks:
        print(f"{Fore.RED}No networks found. Check your adapter or run as sudo.")
        return

    print(f"{'SSID':<28} {'BSSID':<20} {'Channel':<7} {'Signal':<8} {'Speed':<10} {'Security'}")
    print("-" * 100)

    for net in networks:
        ssid = net['ssid'] or "<Hidden>"
        bssid = net['bssid']
        channel = net['channel']
        signal = f"{net['signal']}%"
        signal_color = Fore.GREEN if net['signal'] > 70 else (Fore.YELLOW if net['signal'] > 40 else Fore.RED)
        speed = net['rate']
        sec = net['security']

        print(f"{Fore.WHITE}{ssid:<28} {bssid:<20} {channel:<7} {signal_color}{signal:<8} {Fore.MAGENTA}{speed:<10} {Fore.CYAN}{sec}")
    print()

def main():
    while True:
        raw = scan_wifi_networks()
        networks = parse_nmcli_output(raw)
        display_dashboard(networks)
        time.sleep(REFRESH_SECONDS)

if __name__ == "__main__":
    main()
