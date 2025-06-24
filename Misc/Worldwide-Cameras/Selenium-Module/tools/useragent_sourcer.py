# Originally developed @ https://github.com/scripting-drafts/User-Agent-Scraper/
from os import path, remove
from time import sleep
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
import mod_initializer as gui_enhancements

gui_enhancements.run_useragent()
input_file = '../resources/useragents.txt'
userAgents = open(input_file, 'w')

path_firefox_binary = Service(path.abspath('../tools/geckodriver.exe'))
# path_geckodriver_log = Service(path.devnull)

options = Options()
# options.add_argument('--headless')
options.set_preference('dom.webnotifications.enabled', False)
options.set_preference('dom.push.enabled', False)
options.set_preference('dom.webdriver.enabled', False)
options.set_preference('useAutomationExtension', False)
options.set_preference('privacy.trackingprotection.enabled', True)

options.set_preference('browser.cache.disk.enable', False)
options.set_preference('browser.cache.memory.enable', False)
options.set_preference('browser.cache.offline.enable', False)
options.set_preference('network.http.use-cache', False)

profile_path = open('../resources/profile_path', 'r').read()

driver = webdriver.Firefox(service=path_firefox_binary, options=options)
                           # service_log_path=path_geckodriver_log)

driver.implicitly_wait(10)
driver.get("https://explore.whatismybrowser.com/useragents/explore/")
sleep(10)

try:
    # IFRAME Consent dialog
    driver.find_element(By.CSS_SELECTOR, '.fc-cta-consent > p:nth-child(2)').click()
    
except Exception:
    pass

driver.find_element(By.LINK_TEXT, 'Phone').click()
sleep(10)
phones = driver.find_elements(By.CLASS_NAME, 'useragent')
for phone in phones:
    userAgents.write(phone.text + '\n')
driver.back()
driver.find_element(By.LINK_TEXT, 'Computer').click()
sleep(10)
computers = driver.find_elements(By.CLASS_NAME, 'useragent')
for computer in computers:
    userAgents.write(computer.text + '\n')
driver.back()
driver.find_element(By.LINK_TEXT, 'Tablet').click()
sleep(10)
tablets = driver.find_elements(By.CLASS_NAME, 'useragent')
for tablet in tablets:
    userAgents.write(tablet.text + '\n')
driver.back()
driver.find_element(By.LINK_TEXT, 'Android').click()
sleep(10)
androids = driver.find_elements(By.CLASS_NAME, 'useragent')
for android in androids:
    userAgents.write(android.text + '\n')
driver.back()
driver.find_element(By.LINK_TEXT, 'iOS').click()
sleep(10)
iOSes = driver.find_elements(By.CLASS_NAME, 'useragent')
for iOS in iOSes:
    userAgents.write(iOS.text + '\n')
driver.back()
driver.find_element(By.LINK_TEXT, 'Windows').click()
sleep(10)
windows = driver.find_elements(By.CLASS_NAME, 'useragent')
for window in windows:
    userAgents.write(window.text + '\n')

driver.quit()

remove('geckodriver.log')