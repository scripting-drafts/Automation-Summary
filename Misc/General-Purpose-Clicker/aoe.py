import mouse
import time
import random
import numpy as np
from bool_converter import strtobool
from sys import exit
from threading import Thread
from pynput import keyboard
from pynput.keyboard import Controller, Key
import os

times_to_repeat = 3
stop_key = chr(ord("C") - 64)

str_food = "cheese steak jimmy's"
str_wood = "lumberjack"
str_gold = "robin hood"
str_stone = "rock on"
str_car = "how do you turn this on"
str_instant_build = "aegis"

# Keyboard controller to type the cheats
kb_controller = Controller()

# Mapping hotkeys to cheat strings
cheat_map = {
    (Key.alt_l, '1'): str_food,
    (Key.alt_l, '2'): str_wood,
    (Key.alt_l, '3'): str_gold,
    (Key.alt_l, '4'): str_stone,
    (Key.alt_l, '5'): str_car,
    (Key.alt_l, '6'): str_instant_build
}

pressed_keys = set()

def type_cheat(cheat):
    for _ in range(times_to_repeat):
        kb_controller.press(Key.enter)
        kb_controller.release(Key.enter)
        kb_controller.type(cheat)
        kb_controller.press(Key.enter)
        kb_controller.release(Key.enter)
        time.sleep(0.1)

def on_press(key):
    '''Handle key press for hotkeys and stop key.'''
    pressed_keys.add(key)

    # Check for stop key
    try:
        if key.char == stop_key:
            os._exit(1)
    except AttributeError:
        if key == stop_key:
            os._exit(1)

    # Check if Alt+<number> was pressed
    for (mod, num), cheat in cheat_map.items():
        if mod in pressed_keys and hasattr(key, 'char') and key.char == num:
            Thread(target=type_cheat, args=(cheat,), daemon=True).start()

def on_release(key):
    '''Clear key from pressed set on release.'''
    if key in pressed_keys:
        pressed_keys.remove(key)

listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

# Keep the program running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass