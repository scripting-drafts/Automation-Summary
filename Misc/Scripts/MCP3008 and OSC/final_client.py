## Circuit: 3.3V - boton - (GPIO) - R(220 Ohm) - GND

#!/usr/bin/python3
from osc4py3.as_eventloop import *
from osc4py3 import oscbuildparse
from gpiozero import MCP3008
from gpiozero import Button
from event_listener import on_press
from pynput import keyboard
import time

listener = keyboard.Listener(on_press=on_press)
listener.start()

ip = "192.168.1.103"
port = 8000

pot1 = MCP3008(0)
pot2 = MCP3008(1)
master = MCP3008(2)
switch = MCP3008(3)  

b1 = Button(2)
b2 = Button(4)

osc_startup()
osc_udp_client(ip, port, "client")

pot1_val = pot1.value
pot1_old_val = pot1.value

strip_spectra_symbol = pot2.value
old_strip_value = pot2.value
touch = False
dif = 0
out = 0

master_val = master.value
master_old_val = master.value

while True:
    pot1_val = pot1.value
    strip_spectra_symbol = pot2.value
    master_val = master.value

    if strip_spectra_symbol < 0.01:
        touch = False

    if touch == True:
        dif = strip_spectra_symbol - old_strip_value
        out = out + dif

        if out > 1:
            out = 1
        
        if out < 0:
            out = 0

    if b1.is_pressed:
        address = '/test/4.1'
        s = 'on'
        msg = oscbuildparse.OSCMessage(address, ",s", [s])
        osc_send(msg, "client")
    
    elif b2.is_pressed:
        s = 'on'
        address = '/test/4.2'
        msg = oscbuildparse.OSCMessage(address, ",s", [s])
        osc_send(msg, "client")
    
    elif abs(pot1_val-pot1_old_val) > 0.01 and pot1_val>0.1:
        address = '/track/1/volume'
        s = str(pot1_val)
        msg = oscbuildparse.OSCMessage(address, ",s", [s])
        osc_send(msg, "client")

    elif abs(strip_spectra_symbol-old_strip_value) > 0.01 and strip_spectra_symbol > 0.1:
        if touch == True:
            address = '/test/5.2'
            s = list(str(out))
            msg = oscbuildparse.OSCMessage(address, ",s", s)
            osc_send(msg, "client")

        if strip_spectra_symbol > 0.01:
            touch = True

    elif abs(master_val-master_old_val) > 0.01:
        address = '/test/6.1'
        s = str(master_val)
        msg = oscbuildparse.OSCMessage(address, ",s", [s])
        osc_send(msg, "client")
        
    pot1_old_val = pot1_val
    old_strip_value = strip_spectra_symbol
    master_old_val = master_val
    time.sleep(0.01)

    osc_process()