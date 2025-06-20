
import threading

class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.internal_devices = []
        self.external_aps = {}
        self.show_internal = True
        self.show_external = True
        self.running = True

    def update_internal(self, devices):
        with self.lock:
            self.internal_devices = devices

    def update_external(self, aps):
        with self.lock:
            self.external_aps = aps

    def get_state(self):
        with self.lock:
            return {
                'internal': self.internal_devices if self.show_internal else [],
                'external': self.external_aps if self.show_external else {}
            }

    def toggle_internal(self):
        with self.lock:
            self.show_internal = not self.show_internal

    def toggle_external(self):
        with self.lock:
            self.show_external = not self.show_external
