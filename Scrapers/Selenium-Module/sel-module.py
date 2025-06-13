from os import path
from seleniumwire import webdriver
from selenium.webdriver.firefox.options import Options
import tools.turquoise_logger as turquoise_logger
import tools.mod_initializer as gui_enhancements

class SeleniumWireModule:
    def __init__(self):
        gui_enhancements.run_sel()
        logg = turquoise_logger.Logger()
        path_firefox_binary = 'tools/geckodriver.exe'
        path_geckodriver_log = path.abspath('resources/geckodriver.log')
        log = logg.logging()
        localhost = '127.0.0.1'
        initial_url = 'https://www.google.com'

        options = Options()
        options.add_argument('--headless')
        options.set_preference('dom.webnotifications.enabled', False)
        options.set_preference('dom.push.enabled', False)
        options.set_preference('dom.webdriver.enabled', False)
        options.set_preference('useAutomationExtension', False)
        options.set_preference('privacy.trackingprotection.enabled', True)

        options.set_preference('browser.cache.disk.enable', False)
        options.set_preference('browser.cache.memory.enable', False)
        options.set_preference('browser.cache.offline.enable', False)
        options.set_preference('network.http.use-cache', False)

        # USER AGENT OPT
        # options.set_preference('intl.accept_languages', random.choice(localesList).lower())
        # options.set_preference('general.useragent.override', random.choice(userAgentList))

        profile_path = open('resources/profile_path', 'r').read()

        driver = webdriver.Firefox(firefox_profile=profile_path,
                                   options=options, executable_path=path_firefox_binary,
                                   service_log_path=path_geckodriver_log)
        driver.implicitly_wait(10)
        log.debug('Webdriver is UP')

        self.log = log
        self.localhost = localhost
        self.initial_url = initial_url
        self.driver = driver

    def healthcheck(self):
        '''1 Returns an int if dead and None if alive  
        2 Throws a WebDriverException if dead'''
        self.log.debug('Webdriver healthcheck going on')
        try:
            assert(self.driver.service.process.poll() == None)
            self.driver.service.assert_process_still_running()
            self.log.debug('The driver appears to be OK')
            status = True
        except Exception as e:
            self.log.debug(f'The driver appears to be NOK - {e}')
            status = False
        
        return status

    def connection_attempt(self, max_attempts_count=2):
        '''Commits attempts_count connection attempts to the given initial_url'''
        attempts_count = 1
        initial_url=self.initial_url

        while attempts_count < max_attempts_count:
            self.log.debug(f'{self.localhost} <-> {initial_url}')
            self.driver.get(initial_url)

            if len(self.driver.requests) > 0:
                if self.driver.requests[0].response.status_code == 200:
                    self.log.debug(f'Connection reached | Attempts: {attempts_count}')
                    attempts_count = max_attempts_count
                    is_connected = True
            
            else:
                self.log.debug(f'Failed to connect | Attempts: {attempts_count}')
                is_connected = False

            attempts_count += 1
            
        self.is_connected = is_connected

    def requests_vars_get(self):
        '''Outputs REQ (Request URL), STAT (Status Code) and CT (Content Type) within responses in requests'''
        print('\n' + 'Responses summary')
        if self.is_connected:
            for request in self.driver.requests:
                if request.response:
                    self.log.debug(f'REQ: {request.url}')
                    self.log.debug(f'STAT: {request.response.status_code}')
                    self.log.debug('CT:' +  request.response.headers['content-type'] + '\n')
        if not self.is_connected:
            self.log.debug('The driver is not available')

    def teardown(self):
        '''Graceful shutdown and status verification'''
        self.driver.quit()
        self.log.debug('Verifying webdriver shutdown')
        status = self.healthcheck()

        if status == False:
            self.log.debug('Successful driver termination')
        else:
            self.log.error('Unsuccessful driver termination')

# TEST
wm = SeleniumWireModule()
wm_is_up = wm.healthcheck()

if wm_is_up:
    is_connected = wm.connection_attempt()
    wm.requests_vars_get()

wm.teardown()
