
import threading
import time
from internal_arp_monitor_core import monitor_internal_network

def start_internal_monitor():
    print("[*] Starting internal ARP-based device monitor...")
    thread = threading.Thread(target=monitor_internal_network, daemon=True)
    thread.start()
    while thread.is_alive():
        time.sleep(1)
