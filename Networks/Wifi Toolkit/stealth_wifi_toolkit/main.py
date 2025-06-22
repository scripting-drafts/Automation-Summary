
#!/usr/bin/env python3
import argparse
import threading
import time
from shared_state import SharedState
from dashboard_loop import start_dashboard_loop
from hotkeys import hotkey_listener
from internal_monitor import start_internal_monitor
from external_monitor import start_external_monitor

shared = SharedState()

def main():
    parser = argparse.ArgumentParser(description="Stealth WiFi Toolkit")
    parser.add_argument("--mode", choices=["internal", "external", "both"], default="both",
                        help="Select scan mode: internal (ARP), external (monitor mode), or both")
    args = parser.parse_args()

    # Start dashboard and hotkey threads
    threading.Thread(target=start_dashboard_loop, args=(shared,), daemon=True).start()
    threading.Thread(target=hotkey_listener, args=(shared,), daemon=True).start()

    # Start selected monitor threads
    if args.mode in ("internal", "both"):
        threading.Thread(target=start_internal_monitor, args=(shared,), daemon=True).start()
    if args.mode in ("external", "both"):
        threading.Thread(target=start_external_monitor, args=(shared,), daemon=True).start()

    try:
        while shared.running:
            time.sleep(1)
    except KeyboardInterrupt:
        shared.running = False

if __name__ == "__main__":
    main()
