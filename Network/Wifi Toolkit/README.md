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