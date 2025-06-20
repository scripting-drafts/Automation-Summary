
import scapy.all as scapy
import socket
import time
from datetime import datetime, timedelta
from collections import defaultdict
from resources.mac_vendors import MAC_VENDOR_PREFIXES

total_uptime = defaultdict(timedelta)
online_since = {}
hostname_cache = {}
mac_by_ip = {}

def guess_os_from_mac(mac):
    if not mac or len(mac) < 8:
        return "Unknown"
    normalized = mac.lower().replace('-', ':')
    parts = normalized.split(':')
    if len(parts) < 3:
        return "Unknown"
    prefix = ':'.join(parts[:3])
    return MAC_VENDOR_PREFIXES.get(prefix, "Unknown")

def get_hostname(ip):
    if ip in hostname_cache:
        return hostname_cache[ip]
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except socket.herror:
        hostname = "Unresolved"
    hostname_cache[ip] = hostname
    return hostname

def format_td(td):
    s = int(td.total_seconds())
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s"

def scan_network(ip_range="192.168.1.1/24"):
    arp = scapy.ARP(pdst=ip_range)
    ether = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
    packet = ether / arp
    answered = scapy.srp(packet, timeout=1, verbose=False)[0]
    return [{"ip": rcv.psrc, "mac": rcv.hwsrc} for _, rcv in answered]

def monitor_internal_network(shared_state):
    while shared_state.running:
        now = datetime.now()
        devices = scan_network()
        seen_ips = set()
        result = []

        for d in devices:
            ip = d["ip"]
            mac = d["mac"]
            seen_ips.add(ip)
            mac_by_ip[ip] = mac
            hostname = get_hostname(ip)
            os_info = guess_os_from_mac(mac)

            if ip not in online_since:
                online_since[ip] = now

            uptime = total_uptime[ip]
            if ip in online_since:
                uptime += now - online_since[ip]

            result.append({
                "ip": ip,
                "mac": mac,
                "hostname": hostname,
                "os": os_info,
                "uptime": format_td(uptime)
            })

        for ip in list(online_since.keys()):
            if ip not in seen_ips:
                duration = now - online_since.pop(ip)
                total_uptime[ip] += duration

        shared_state.update_internal(result)
        time.sleep(5)
