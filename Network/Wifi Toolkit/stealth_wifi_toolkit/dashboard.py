
import os
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

def format_section(title):
    now = datetime.now().strftime("%H:%M:%S")
    return f"{Fore.CYAN}[ {title} - {now} ]{Style.RESET_ALL}\n" + "-" * 90 + "\n"

def print_internal_devices(devices):
    print(format_section("INTERNAL DEVICES"))
    print(f"{'IP':<16} {'MAC':<18} {'HOSTNAME':<25} {'OS':<20} {'UPTIME'}")
    print("-" * 90)
    for dev in devices:
        print(f"{dev['ip']:<16} {dev['mac']:<18} {dev['hostname']:<25} {dev['os']:<20} {dev['uptime']}")
    print()

def print_external_aps(aps):
    print(format_section("EXTERNAL APS"))
    print(f"{'SSID':<22} {'BSSID':<20} {'SIG':>5} {'CH':>3} {'#CL':>4} {'HS':>4}")
    print("-" * 70)
    for bssid, info in aps.items():
        ssid = info['ssid'][:22].ljust(22)
        signal = f"{info['sig']}".rjust(5)
        ch = str(info['ch']).rjust(3)
        num_clients = str(len(info['clients'])).rjust(4)
        hs_flag = Fore.GREEN + '[OK]' if info.get('handshake') else Fore.RED + '[--]'
        print(f"{ssid} {bssid:<20} {signal} {ch} {num_clients}  {hs_flag}")
        for mac in info['clients']:
            print(Fore.LIGHTBLACK_EX + f"    ↳ {mac}" + Style.RESET_ALL)
    print()

def unified_display(internal_data, external_data):
    os.system("cls" if os.name == "nt" else "clear")
    if internal_data:
        print_internal_devices(internal_data)
    if external_data:
        print_external_aps(external_data)
