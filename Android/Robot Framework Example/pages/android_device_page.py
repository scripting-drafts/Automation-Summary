from Android_Ops import Android_Ops
from Client_Ops import Client_Ops

class AndroidDevicePage:
    """Page layer exposing Android operations as Robot Framework keywords."""

    def __init__(self):
        self.android_ops = Android_Ops()
        self.client_ops = Client_Ops()

    def list_devices(self):
        return sum(self.android_ops.list_devices(), [])

    def reboot_device(self, udid):
        self.android_ops.reboot(udid)

    def set_wifi(self, udid):
        self.android_ops.wifi_connectivity_status(udid)

    def set_default_network(self, udid):
        self.android_ops.default_connectivity_status(udid)

    def install_client(self, udid, apk_path):
        self.client_ops.install(udid, apk_path)

    def uninstall_client(self, udid):
        self.client_ops.uninstall(udid, self.client_ops.client_packageName)

    def send_sos(self, udid):
        self.client_ops.initiate_sos(udid)
