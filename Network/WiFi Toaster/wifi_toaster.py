import pywifi
import pywifi.const as const
import time
import keyring
import time
import creds
import subprocess
import random
import threading
from logger import Logger
import queue as queue
from pythonping import ping
import re
from sys import exit as sexit

class Geored_Wifi_Server:
    def __init__(self):
        self.wifi = pywifi.PyWiFi()
        self.logging = Logger().logging()

        self.threads_list = []
        self.urls = '8.8.8.8', '192.168.1.1', 'google.com'
        self.ping_results = []
        self.get_network_interfaces()

        self.initialize_network_status_vars()

        self.ap_disconnected_status = 'disconnected', 'disconnecting'
        self.ap_processing_status = 'discovering', 'associating'

    def initialize_network_status_vars(self):
        self.ap_a_current_name = None
        self.ap_a_current_status = None
        self.hardware_a_radio = None
        self.software_a_radio = None

        self.ap_b_current_name = None
        self.ap_b_current_status = None
        self.hardware_b_radio = None
        self.software_b_radio = None

        self.set_network_status_vars()

    def set_network_status_vars(self):
        self.current_ap_names = [self.ap_a_current_name, self.ap_b_current_name]
        self.aps_current_status = [self.ap_a_current_status, self.ap_b_current_status]
        
        self.hardware_radios = [self.hardware_a_radio, self.hardware_b_radio]
        self.software_radios = [self.software_a_radio, self.software_b_radio]

    def get_network_status(self):
        '''
        TODO: Improve Regex syntax and avoid iterating over status_lists
        
        Classify which network interface drivers are disabled (flagged with 'Hosted network status  : Not available')
        '''
        
        def parse_status_list():
            network_status = subprocess.check_output(r'netsh WLAN show interfaces', encoding='utf-8')

            if 'There is no wireless interface on the system' in network_status:
                '''Rare case exception
                
                TODO: Enable Network Interface from Device Manager'''
                self.logging.critical('Enable Network Interface from Device Manager')
                sexit()

            network_status_list = network_status.split('Name                   :')
            return network_status, network_status_list

        network_status, network_status_list = parse_status_list()
        ifaces_amount = len(network_status_list) - 1
        network_a_status_list = network_status_list[1].split('\n')

        if ifaces_amount == 2:
            network_b_status_list = network_status_list[2].split('\n')

        def get_hardware_radio(status_list):
            pattern = re.compile(r'Radio status           : Hardware')

            for line in status_list:
                if 'Hardware' in line:
                    return re.sub(pattern, '', line).strip()

        def get_software_radio(status_list):
            pattern = re.compile(r'Software')

            for line in status_list:
                if 'Software' in line:
                    return re.sub(pattern, '', line).strip()

        def get_network_name(status_list):
            # pattern = re.compile(r'SSID                  :')
            for line in status_list:
                if 'SSID' in line:
                    # DOES NOT WORK
                    # return re.sub(pattern, '', line).strip()
                    return line.split('SSID')[1].split(':')[1].split('\n')[0].strip()

        def get_status(status_list):
            pattern = re.compile(r'State                  :')

            for line in status_list:
                if 'State' in line:
                    return re.sub(pattern, '', line).strip()

        def process_connected_status(self, ap = 'a'):
            ap = 0 if ap == 'a' else 1
            self.hardware_radios[ap] = 'On'
            self.software_radios[ap] = 'On'
            return self.current_ap_names[ap], self.hardware_radios[ap], self.software_radios[ap]

        def process_disconnected_status(self, ap = 'a'):
            ap = 0 if ap == 'a' else 1
            private_network_list = network_a_status_list if ap == 0 else network_b_status_list
            self.hardware_radios[ap] = get_hardware_radio(private_network_list)
            self.software_radios[ap] = get_software_radio(private_network_list)
            return self.hardware_radios[ap], self.software_radios[ap]

        if network_status:
            self.ap_a_current_status = get_status(network_a_status_list)

            if self.ap_a_current_status == 'connected':
                self.ap_a_current_name = get_network_name(network_a_status_list)
                _, self.hardware_a_radio, self.software_a_radio = process_connected_status(self)
                

            elif self.ap_a_current_status == 'disconnected':
                self.hardware_a_radio, self.software_a_radio = process_disconnected_status(self)

            else:
                wait_timer_processing = 2
                waited_processing = 0

                while self.ap_a_current_status in self.ap_processing_status:
                    self.logging.info(f'PROCESSING_AP_STATUS: {self.ap_a_current_status}')
                    time.sleep(wait_timer_processing)
                    _, network_status_list = parse_status_list()
                    network_a_status_list = network_status_list[1].split('\n')
                    self.ap_a_current_status = get_status(network_a_status_list)

                    if waited_processing > 30:
                        self.logging.critical(f'AP_STATUS: {self.ap_a_current_status}')
                        break

                wait_timer_disconnecting = 5
                waited_disconnecting = 0

                while self.ap_a_current_status == 'disconnecting':
                    time.sleep(wait_timer_disconnecting)
                    _, network_status_list = parse_status_list()
                    network_a_status_list = network_status_list[1].split('\n')
                    self.ap_a_current_status = get_status(network_a_status_list)

                    if waited_disconnecting > 15:
                        '''[REMINDER] TODO: Adjust time.sleep if error pops up '''
                        self.logging.error('AP Disconnecting status after disconnecting')

                if self.ap_a_current_status == 'disconnected':
                    self.hardware_b_radio, self.software_b_radio = process_disconnected_status(self, 'b')

            self.logging.info(f'{self.ifaces[0].name()}')

            self.logging.info(f'[iface 0] HW_Radio: {self.hardware_a_radio}')
            self.logging.info(f'[iface 0] SW_Radio: {self.software_a_radio}')
            self.logging.info(f'[iface 0] AP_NAME: {self.ap_a_current_name}')
            self.logging.info(f'[iface 0] AP_STATUS: {self.ap_a_current_status}')

            if ifaces_amount > 1:
                self.ap_b_current_status = get_status(network_b_status_list)

                if self.ap_b_current_status == 'connected':
                    self.ap_b_current_name = get_network_name(network_b_status_list)
                    _, self.hardware_b_radio, self.software_b_radio = process_connected_status(self, 'b')

                elif self.ap_b_current_status == 'disconnected':
                    self.hardware_b_radio, self.software_b_radio = process_disconnected_status(self, 'b')

                else:
                    wait_timer_processing = 2
                    waited_processing = 0

                    while self.ap_b_current_status in self.ap_processing_status:
                        self.logging.info(f'PROCESSING_AP_STATUS: {self.ap_b_current_status}')
                        time.sleep(wait_timer_processing)
                        _, network_status_list = parse_status_list()
                        network_b_status_list = network_status_list[2].split('\n')
                        self.ap_b_current_status = get_status(network_b_status_list)

                        if waited_processing > 30:
                            self.logging.critical(f'AP_STATUS: {self.ap_b_current_status}')
                            break

                    wait_timer_disconnecting = 5
                    waited_disconnecting = 0

                    while self.ap_b_current_status == 'disconnecting':
                        time.sleep(wait_timer_disconnecting)
                        _, network_status_list = parse_status_list()
                        network_b_status_list = network_status_list[2].split('\n')
                        self.ap_b_current_status = get_status(network_b_status_list)

                        if waited_disconnecting > 15:
                            '''[REMINDER] TODO: Adjust time.sleep if error pops up '''
                            self.logging.error('AP Disconnecting status after disconnecting')

                    if self.ap_b_current_status == 'disconnected':
                        self.hardware_b_radio, self.software_b_radio = process_disconnected_status(self, 'b')

                self.logging.info(f'{self.ifaces[1].name()}')

                self.logging.info(f'[iface 1] HW_Radio: {self.hardware_b_radio}')
                self.logging.info(f'[iface 1] SW_Radio: {self.software_b_radio}')
                self.logging.info(f'[iface 1] AP_NAME: {self.ap_b_current_name}')
                self.logging.info(f'[iface 1] AP_STATUS: {self.ap_b_current_status}')

            self.set_network_status_vars()

        else:
            self.initialize_network_status_vars()

    def disable_software_radio(self, iface):
        iface.disconnect()
        time.sleep(.7)
        assert iface.status() in\
            [const.IFACE_DISCONNECTED, const.IFACE_INACTIVE]
        
    def enable_hardware_radio(self):
        '''Enables hardware WiFi radio
        
        The requested operation requires elevation (Run as administrator)'''
        subprocess.Popen('netsh interface set interface "WiFi" enable', shell=True).communicate()

    def disable_hardware_radio(self):
        '''Disables hardware WiFi radio

        TODO: The requested operation requires elevation (Run as administrator)'''
        sh = subprocess.Popen('powershell.exe -noprofile "Start-Process -Verb RunAs -Wait powershell.exe -Args -noprofile; netsh interface set interface WiFi disable"',
                         shell=True, stdin=subprocess.PIPE).communicate()
        sh.stdin.write('netsh interface set interface')
        # subprocess.Popen('netsh interface set interface "WiFi" disable', shell=True, stdin=subprocess.PIPE).communicate()

    def list_ap_attrs(self):
        '''List all bss attributes'''
        '''TODO:
        Retrieve handshake algorithm name'''

        for i in list(self.aps):
            bssid = i.bssid
            ssid  = i.ssid
            signal = i.signal
            freq = i.freq
            auth = i.auth
            akm = i.akm
            # alg = i.alg
            cipher = i.cipher
            profile_attrs = bssid, ssid, signal, freq, auth, akm, cipher
            self.logging.info(profile_attrs)

    def connect_ap(self, iface, ap):
        '''
        Connects to desired AP

        Disconnects from current AP first (In case there isn't traffic) <-> Relies on current_ap_name

        Use saved AP in \ProgramData\Microsoft\Wlansvc\Profiles\Interfaces\{GUID} if available'''
        profiles = iface.network_profiles()
        profile_names = [profile.ssid for profile in profiles]
        self.logging.debug(f'Profiles Available: {profile_names}')

        # '''WORKAROUND'''
        # if self.current_ap_name is not None:
        #     current_profile = [profile for profile in profiles if profile.ssid == self.current_ap_name][0]

        #     if iface.status() == const.IFACE_CONNECTED:
        #         self.logging.info(f'Disconnecting from {current_profile.ssid}')
        #         iface.disconnect()
        # ##################

        if ap in profile_names:
            profile = [profile for profile in profiles if profile.ssid == ap][0]
        else:
            # self.logging.info(f'Removing profile {profile}')
            # iface.remove_network_profile(profile)

            profile = pywifi.Profile()

            i = [i for i in list(self.aps) if i.ssid == ap]
            i = i[0]

            profile.bssid = i.bssid[:-1]
            profile.ssid  = i.ssid
            profile.signal = i.signal
            profile.freq = i.freq
            profile.auth = i.auth[0] if len(i.auth) > 0 else 0
            profile.akm = i.akm[0]
            profile.cipher = i.cipher

            # profile.ssid = ap
            # profile.auth = const.AUTH_ALG_OPEN
            # profile.akm.append(const.AKM_TYPE_WPA2PSK)
            # profile.cipher = const.CIPHER_TYPE_CCMP
            pwd = keyring.get_password('system', ap)
            profile.key = pwd

            profile_attrs = profile.bssid, profile.ssid, profile.signal, profile.freq, profile.auth, profile.akm, profile.cipher
            self.logging.debug(profile_attrs)
            
        self.logging.info(f'Connecting to {profile.ssid}')
        iface.connect(profile)
        time.sleep(5)
        
        if iface.status() == const.IFACE_CONNECTED:
            result = True
        else:
            result = False
                
        self.logging.info(f'Connection established' if result == True else f'Connection did not succeed')

        return result

    def get_network_interfaces(self):
        '''
        ifaces is a list of objects with the attribute ifaces.name

        We assume ifaces will never be empty
        '''
        self.ifaces = self.wifi.interfaces()
        self.iface_0 = self.ifaces[0]
        
        if len(self.ifaces) > 1:
            self.iface_1 = self.ifaces[1]

        # for u, w in enumerate(self.ifaces):
        #     self.logging.info(f'iface {u}: {w.name()}' )

    def get_networks_list(self, iface):
        '''Fetch Available APs list

        Service Set (bss) attributes are bssid, ssid, freq, auth, akm, signal

        TODO: Check if it gets connected automatically to each AP '''
        iface.scan()
        time.sleep(0.7)
        aps = iface.scan_results()
        self.aps = aps

    def keepalived(self):
        for url in self.urls:
            t = threading.Thread(target=self.keepalive_service, daemon=True, args=(url,))
            self.threads_list.append(t)
            t.start()

        for t in self.threads_list:
            t.join()
            self.ping_results = []

    def keepalive_service(self, url):
        '''Remove try except'''
        try:
            response = ping(url, verbose=False, timeout=1, size=1, count=1, interval=.8)
            response_str = str(response).split('\n')[0].strip()
            self.logging.info(response_str)

            self.ping_results.append(response.success())

        except Exception:
            self.logging.error(f'KeepAlive.d: NO_RESOLUTION for {url}')
            self.ping_results.append(False)

    def georedundancy(self):
        while True:
            self.keepalived()
            self.healthcheck()
            
    def healthcheck(self, iface = 0):
        if not any(self.ping_results):
            self.geored_failover(iface)

        self.get_network_status()

        if self.software_radios[iface] == 'On':
            if self.aps_current_status[iface] == 'connected':
                pass

            elif self.aps_current_status[iface] is None:
                '''Rare case exception
                
                TODO: Enable Network Interface from Device Manager'''
                pass
        
            elif self.aps_current_status[iface] in self.ap_disconnected_status:
                # self.get_network_interfaces()
                # if len(self.iface_a.name()) == 0:
                #     raise AssertionError('No network interfaces available')
                self.logging.info('No interfaces available')
                
                self.geored_failover(iface)

            else:
                self.logging.error('Unknown AP or Interface error occurred')

        elif self.software_radios[iface] == 'Off':
            '''TODO: Turn ON network interface'''
            pass

    def geored_failover(self, iface = 0):
        if self.current_ap_names[iface] is not None:

            if self.current_ap_names[iface] == creds.ap_b:
                target_ap = creds.ap_a
            elif self.current_ap_names[iface] == creds.ap_a:
                target_ap = creds.ap_b

        elif self.current_ap_names[iface] is None:
            target_ap = random.choice([creds.ap_a, creds.ap_b])

        self.logging.info(f'Failover attempt {self.current_ap_names[iface]} -> {target_ap}')
        resolution = self.connect_ap(self.ifaces[iface], target_ap)
        self.logging.info(f'Failover OK - {self.current_ap_names[iface]} -> {target_ap}' if resolution \
                          else f'Did not failover {self.current_ap_names[iface]} -> {target_ap}')
        
        # if resolution == False:
        #     '''ha_failover'''
        #     return

    def ha_failover(self):
        '''
        Put iface 0 down
        Put iface 1 up
        Run healthcheck'''

    def test(self):
        # self.get_network_status()
        # self.get_networks_list(self.iface_a)
        # self.healthcheck()
        # self.list_ap_attrs()
        # self.connect_ap(self.iface_a, creds.ap_b)
        # self.logging.info(f'Failover {self.current_ap_name} -> {target_ap}')

        self.disable_hardware_radio()
        pass

wg = Geored_Wifi_Server()
# wg.georedundancy()
wg.test()
