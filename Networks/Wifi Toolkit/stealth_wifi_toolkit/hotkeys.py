
import sys, tty, termios, select

def getch(timeout=0.1):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        rlist, _, _ = select.select([fd], [], [], timeout)
        if rlist:
            return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return None

def hotkey_listener(shared_state):
    while shared_state.running:
        key = getch()
        if not key:
            continue
        key = key.lower()
        if key == 'q':
            shared_state.running = False
        elif key == 'i':
            shared_state.toggle_internal()
        elif key == 'e':
            shared_state.toggle_external()
