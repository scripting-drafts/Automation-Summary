
import time
from dashboard import unified_display

def start_dashboard_loop(shared_state, interval=5):
    while shared_state.running:
        state = shared_state.get_state()
        unified_display(state['internal'], state['external'])
        time.sleep(interval)
