# External Monitor  
  
Key Features:  
Auto-detect or manually select wireless interface

Monitor mode enabled automatically

AP + Client dashboard (using colored ASCII symbols ⚪ replaced)

Saved logs in wifi_ap.log

Filters by SSID or client MAC (via CLI args)

Hotkeys:

    h → deauth + parallel handshake capture for selected clients

    H → deauth + parallel handshake capture for all APs with ≥ 40% signal

Auto channel detection, handshake capture, live verification, and UI flag [OK] if handshake found

Vendor lookup for client MACs via mac_vendors.py

# Clean Monitor

Live EAPOL detection, no aircrack-ng delay

Auto-delete .cap on failure + backoff for repeated fails

Handshake .cap file paths logged to handshake_report.csv

UI shows [✔] if handshake found

Skips APs with known handshakes to save time

Multi-round deauth, marked targets, and deep scan hotkeys

----------------------------------

More rounds + faster sleep → faster, better deauth floods

Reduced REFRESH → faster UI updates, showing more APs “in time”

Skip APs marked in SKIP_APS during all deauths

-----------------------------------