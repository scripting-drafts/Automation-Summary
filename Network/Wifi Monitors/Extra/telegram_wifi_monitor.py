import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
import random
from functools import wraps
import csv
from datetime import datetime
from threading import Lock

def get_week_str():
    now = datetime.now()
    week_str = now.strftime("%Y-W%U")
    return week_str

def get_current_log_filename():
      # ISO Week
    week_str = get_week_str()
    filename = f"device_log_{week_str}.csv"
    full_path = os.path.join(os.getcwd(), filename)

    # If file doesn't exist, create and add header
    if not os.path.exists(full_path):
        with open(full_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["timestamp", "event", "ip", "mac", "hostname"])

    return full_path

# Ensure CSV header exists
week_str = get_week_str()
with open(f"device_log_{week_str}.csv", mode='a', newline='') as file:
    writer = csv.writer(file)
    if file.tell() == 0:
        writer.writerow(["timestamp", "event", "ip", "mac", "hostname"])

def log_device_event(event_type, info, mac):
    log_file = get_current_log_filename()
    with open(log_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.now().isoformat(timespec='seconds'),
            event_type.upper(),
            info['ip'],
            mac,
            info['hostname']
        ])

shared_devices = {}
device_events = []
device_lock = Lock()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

LIST_OF_ADMINS = [19419361]
TOKEN = '449394451:AAF70wCzhZer4EfSzvMyLXTs5yL1WsH8O1M'

import time
import socket
import threading
import sys
from scapy.all import ARP, Ether, srp
from colorama import Fore, Style, init

init(autoreset=True)

LOG_FILE = "telegram_wifi_log.txt"

# ------------------------
# Logging Setup
# ------------------------

class Logger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

# Replace stdout with logger
sys.stdout = Logger(LOG_FILE)

# ------------------------
# Network Scanning Functions
# ------------------------

def scan_network(subnet):
    """Fast ARP scan for active devices on the network."""
    arp = ARP(pdst=subnet)
    ether = Ether(dst="ff:ff:ff:ff:ff:ff")
    packet = ether / arp
    result = srp(packet, timeout=2, verbose=False)[0]

    devices = {}
    for _, received in result:
        ip = received.psrc
        mac = received.hwsrc
        devices[mac] = {"ip": ip, "hostname": "Resolving..."}
    return devices

def resolve_hostnames(devices):
    """Try to resolve hostnames in the background."""
    def resolver(mac, ip):
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except Exception:
            hostname = "Unknown"
        devices[mac]["hostname"] = hostname

    for mac, info in devices.items():
        if info["hostname"] == "Resolving...":
            thread = threading.Thread(target=resolver, args=(mac, info["ip"]))
            thread.daemon = True
            thread.start()

def display_devices(devices):
    print("\n📡 Current Devices on Network:")
    print("-" * 60)
    print(f"{'IP Address':<16} {'MAC Address':<18} {'Hostname'}")
    print("-" * 60)
    for mac, info in devices.items():
        print(f"{info['ip']:<16} {mac:<18} {info['hostname']}")
    print("-" * 60)

def print_device_event(event_type, mac, info):
    symbol = "+" if event_type == "joined" else "-"
    color = Fore.GREEN if event_type == "joined" else Fore.RED
    print(color + f"[{symbol}] {event_type.upper():7} | {info['ip']} ({mac}) - {info['hostname']}")

def monitor_network(subnet, interval=10):
    global shared_devices, device_events

    print(f"🌐 Background monitoring started on {subnet} every {interval}s")

    known_devices = scan_network(subnet)
    resolve_hostnames(known_devices)

    with device_lock:
        shared_devices = known_devices.copy()

    while True:
        time.sleep(interval)
        current_devices = scan_network(subnet)
        resolve_hostnames(current_devices)

        new_macs = current_devices.keys() - known_devices.keys()
        left_macs = known_devices.keys() - current_devices.keys()

        with device_lock:
            shared_devices = current_devices.copy()
            for mac in new_macs:
                msg = f"[+] JOINED: {current_devices[mac]['ip']} - {mac} ({current_devices[mac]['hostname']})"
                device_events.append(msg)
                log_device_event("joined", current_devices[mac], mac)

            for mac in left_macs:
                msg = f"[-] LEFT:   {known_devices[mac]['ip']} - {mac} ({known_devices[mac]['hostname']})"
                device_events.append(msg)
                log_device_event("left", known_devices[mac], mac)
            if len(device_events) > 50:
                device_events = device_events[-50:]

        known_devices = current_devices

subnet = "192.168.1.0/24"  # Set to your local subnet
if __name__ == '__main__':
    threading.Thread(target=monitor_network, args=(subnet,), daemon=True).start()


def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in LIST_OF_ADMINS:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(update, context, *args, **kwargs)
    return wrapped

@restricted
def start(update, context):
    keyboard = [
        [
            InlineKeyboardButton("Show Devices", callback_data='show_devices'),
            InlineKeyboardButton("Recent Events", callback_data='show_events'),
        ],
        [InlineKeyboardButton("Flip coin", callback_data=random.choice(['heads', 'tails']))],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Choose an option:', reply_markup=reply_markup)


def button(update, context):
    query = update.callback_query
    query.answer()

    with device_lock:
        if query.data == "show_devices":
            text = "📡 Current Devices:\n"
            for mac, info in shared_devices.items():
                text += f"- {info['ip']} ({mac}) - {info['hostname']}\n"
            query.edit_message_text(text=text or "No devices found.")

        elif query.data == "show_events":
            text = "📜 Recent Events:\n" + "\n".join(device_events[-10:])
            query.edit_message_text(text=text or "No events recorded.")

        elif query.data in ['heads', 'tails']:
            query.edit_message_text(text=f"You flipped: {query.data}")



def main():
    updater = Updater(TOKEN, use_context=True)

    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))
    
    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
