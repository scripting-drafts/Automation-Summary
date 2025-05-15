from pynput import keyboard
from osc4py3.as_eventloop import *
import os

stop_key_options = {
    'esc': keyboard.Key.esc,
    'ctrl+c': chr(ord("C")-64)
}
stop_key = stop_key_options['ctrl+c']

def on_press(key):
    '''Stops if stop_key is pressed'''
    if key == stop_key:
        print('{0} pressed'.format(key))

    try:
        if key.char == stop_key:
            osc_terminate()
            os._exit(1)
    except AttributeError:
        if key == stop_key:
            osc_terminate()
            os._exit(1) 

listener = keyboard.Listener(on_press=on_press)
listener.start()