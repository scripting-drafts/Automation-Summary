# Import needed modules from osc4py3
from osc4py3.as_eventloop import *
from osc4py3 import oscbuildparse
from event_listener import on_press
from pynput import keyboard

ip = "127.0.0.1"
port = 3721

listener = keyboard.Listener(on_press=on_press)
listener.start()
osc_startup()

osc_udp_client(ip, port, "client")

msg = oscbuildparse.OSCMessage("/test/me", ",sif", ["text", 672, 8.871])
osc_send(msg, "aclientname")

osc_send(msg, "aclientname")


while True:
    osc_send(msg, "aclientname")
    osc_process()
