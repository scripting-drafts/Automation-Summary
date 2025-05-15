
from event_listener import on_press
from pynput import keyboard
from osc4py3.as_eventloop import *
import colorama
from a_logger import Logger

log = Logger().logging()
colorama.init()
GREEN = colorama.Fore.GREEN
GRAY = colorama.Fore.LIGHTBLACK_EX
RESET = colorama.Fore.RESET
RED = colorama.Fore.RED

listener = keyboard.Listener(on_press=on_press)
listener.start()

ip = "127.0.0.1"
port = 3721

osc_startup()
osc_udp_server(ip, port, "server")

def handlerfunction(s, x, y):
    log.debug('message received {} {} {}'.format(s,x,y))
    pass

while True:
    osc_method("/test/*", handlerfunction)
    osc_process()