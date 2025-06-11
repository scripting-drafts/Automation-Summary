from sys import exit
from pynput import keyboard
from pynput.keyboard import Controller, Key
from threading import Thread
import time
import mouse


# Configuration
times_to_repeat = 1
stop_key = chr(ord("C") - 64)      # CTRL+C

# Define the cheat codes
cheat_map = {
    '1': "cheese steak jimmy's",   # Food
    '2': "lumberjack",             # Wood
    '3': "robin hood",             # Gold
    '4': "rock on",                # Stone
    '5': "how do you turn this on",  # Cobra car
    '6': "aegis"                   # Instant build
}

# Track modifier state
modifiers = {
    'alt': False
}

# Create a keyboard controller
kb = Controller()

def type_cheat(cheat: str):
    # Release Alt to avoid Alt+Enter fullscreen bug
    kb.release(Key.alt_l)
    kb.release(Key.alt_r)
    for _ in range(times_to_repeat):
        kb.press(Key.enter)
        kb.release(Key.enter)

        time.sleep(2)
        mouse.move(623, 400)
        mouse.click()
        
        kb.type(cheat)
        
        kb.press(Key.enter)
        time.sleep(2)
        kb.release(Key.enter)

        time.sleep(.1)
        print(f"AOE Cheat {cheat}")

def on_press(key):
    if key in [Key.alt_l, Key.alt_r]:
        modifiers['alt'] = True

def on_release(key):
    if key in [Key.alt_l, Key.alt_r]:
        modifiers['alt'] = False
    elif isinstance(key, keyboard.KeyCode):
        if modifiers['alt'] and key.char in cheat_map:
            cheat = cheat_map[key.char]
            Thread(target=type_cheat, args=(cheat,), daemon=True).start()
    try:
        if key.char == stop_key:
        # Optional: allow exiting with ESC
            print("Exiting...")
            return False
        
    except AttributeError:
        if key == stop_key:
            exit(1) 

# Start the global keyboard listener
listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

print("AOE Cheat Hotkeys enabled.")
print("Use Alt+1 to Alt+6 to type cheats. Press ESC to quit.")

while True:
    time.sleep(.1)

    






