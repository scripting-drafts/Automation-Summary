from osc4py3.as_eventloop import *
from osc4py3 import oscmethod as osm
from event_listener import on_press
from pynput import keyboard
from a_logger import Logger
import colorama

log = Logger().logging()
colorama.init()
GREEN = colorama.Fore.GREEN
GRAY = colorama.Fore.LIGHTBLACK_EX
RESET = colorama.Fore.RESET
RED = colorama.Fore.RED

ip = "127.0.0.1"
port = 3721

listener = keyboard.Listener(on_press=on_press)
listener.start()

def handlerfunction(s, x, y):
    log.debug('message received {}{}{}'.format(s,x,y))
    pass

# Start the system.
osc_startup()

osc_udp_server(ip, port, "server")

osc_method("/test/*", handlerfunction)

while True:
    osc_method("/test/*", handlerfunction)
    osc_process()