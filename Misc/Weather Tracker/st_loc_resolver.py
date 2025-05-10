from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By

from st_logger import Logger
import csv
import re
from selenium import webdriver
from os import path
from tqdm import tqdm

log = Logger().logging()
datalist = []
geolocation_pattern = re.compile('(-?\d+\.\d+?),(-?\d+\.\d+)')
df = open('worldcam_aa.csv', newline='')
csv_datareader = csv.reader(df, delimiter=';')
headers = next(csv_datareader, None)

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

profile_path = open('Selenium-Module/resources/profile_path', 'r').read()
path_firefox_binary = Service(path.abspath('Selenium-Module/tools/geckodriver.exe'))

driver = webdriver.Firefox(service=path_firefox_binary, options=options)
                           # service_log_path=path_geckodriver_log)

driver.implicitly_wait(10)

def coords(zone='knokke heist beach', country=None, maps_url = 'https://www.google.com/maps/search/', first_run = True):
    zone_transform = zone.replace(' ', '+') + ',+' + country.replace(' ', '+')
    url = f'{maps_url}{zone_transform}'
    driver.get(f'{url}')

    if first_run:
        driver.find_element(By.CSS_SELECTOR, '.VtwTSb > form:nth-child(1) > div:nth-child(1) > div:nth-child(1) > button:nth-child(1) > span:nth-child(4)').click()  # css -> .VtwTSb > form:nth-child(1) > div:nth-child(1) > div:nth-child(1) > button:nth-child(1) > span:nth-child(4)
        first_run = False

    redirect = driver.current_url
    
    while redirect == url:
        redirect = driver.current_url

    geoCode = re.findall(geolocation_pattern, redirect)
    lat, lon = geoCode[0][0], geoCode[0][1]

    return lat, lon

def process_datalist(data=csv_datareader):
    first_run = True
    csv_data = list(csv_datareader)

    for row in csv_data:    # Match[1589:] [1957:]
        lat, lon = coords(zone=row[2], country=row[1], first_run=True) if first_run else coords(zone=row[2], country=row[1], first_run=False)
        data = {}

        data['region'] = row[0]
        data['country'] = row[1]
        data['zone'] = row[2]
        data['lat'] = lat
        data['lon'] = lon
        data['url'] = row[4]
        data['ref'] = row[3]

        datalist.append(data)
        log.debug('DONE {} of {}: {}'.format(csv_data.index(row), len(csv_data), data['url']))
        first_run = False

def write_to_csv(datalist):
    keys = datalist[0].keys()

    with open('./coords_asia.csv', 'w', encoding='utf_8_sig', newline='') as f:
        dict_writer = csv.DictWriter(f, keys, dialect='excel', delimiter=';')
        dict_writer.writeheader()
        dict_writer.writerows(datalist)

try:
    process_datalist()
    write_to_csv(datalist)
except Exception as e:
    log.warning(f'Stopped: {e}')
    driver.quit()
    write_to_csv(datalist)

finally:
    driver.quit()
    write_to_csv(datalist)