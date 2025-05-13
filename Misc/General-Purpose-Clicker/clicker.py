import mouse
import time
import random
import numpy as np
from bool_converter import strtobool
from sys import exit
from threading import Thread
from pynput import keyboard
import os

times_to_repeat = 999
stop_key = chr(ord("C")-64)

def on_press(key):
    '''Stops if stop_key is pressed'''
    if key != keyboard.Key.ctrl_l:
        print('{0} pressed'.format(key))

    try:
        if key.char == stop_key:
            os._exit(1)
    except AttributeError:
        if key == stop_key:
            os._exit(1) 

listener = keyboard.Listener(on_press=on_press)
listener.start()

for t in range(times_to_repeat):
    is_repeat = np.random.choice(a=[True, False], size=(1,), p=[0.1, 0.9])
    is_repeat = strtobool(''.join([str(x) for x in is_repeat]))

    if is_repeat == False or t == 0:
        x, y = 870, 630
        x, y = random.uniform(x - 10, x + 10), random.uniform(y - 20, y + 20)
        
    t += 1
    z = random.uniform(0.4, 0.6)

    mouse.move(x, y)
    mouse.click()
    
    if t % 2 == 0 and t % 10 != 0:
        alt_z = random.uniform(0.7, 1)
        choice = random.choice([z, alt_z])
        time.sleep(choice)

    elif t % 3 == 0:
        alt_z = random.uniform(1, 3)
        choice = random.choice([z, alt_z])
        time.sleep(choice)

    elif t % 5 == 0:
        alt_z = random.uniform(3, 5)
        choice = random.choice([z, alt_z])
        time.sleep(choice)

    elif t % 7 == 0:
        alt_z = random.uniform(5, 7)
        choice = random.choice([z, alt_z])
        time.sleep(choice)

    elif t % 10 == 0:
        alt_z = random.uniform(0.4, 23)
        choice = random.choice([z, alt_z])
        time.sleep(choice)

    else:
        choice = z
        time.sleep(choice)

    print(f'Click {str(t)} | Slept {str(choice)}')
    t -= 1

