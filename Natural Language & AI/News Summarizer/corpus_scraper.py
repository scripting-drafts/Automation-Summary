from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from tqdm import tqdm
import csv

file = open("./global_warming_links.txt", "r")
links = [x.replace('\n', '') for x in file]

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

driver = webdriver.Firefox(options=options)
driver.implicitly_wait(10)

datalist = []
first_time = True

for link in tqdm(links):
    try:
        driver.get(link)
        if first_time == True:
            accept_btn = driver.find_element(By.CSS_SELECTOR, '.ePGZca')
            accept_btn.click()
            first_time = False

        table = {}
        table['date'] = driver.find_element(By.CSS_SELECTOR, '#date_posted').text
        table['headline'] = driver.find_element(By.CSS_SELECTOR, '#headline').text
        table['abstract'] = driver.find_element(By.CSS_SELECTOR, '#abstract').text
        fragments = driver.find_elements(By.CSS_SELECTOR, '#text > p')
        debris = driver.find_elements(By.CSS_SELECTOR, '#text > p > strong')
        insertions = driver.find_elements(By.CSS_SELECTOR, '#insertion_middle')
        
        chunks = [x.text for x in fragments if x not in debris and x not in insertions]
        chunks = ''.join(chunks)
   
        table['text'] = chunks

        datalist.append(table)
    
    except Exception as e:
        print(link, e)

driver.quit()

keys = datalist[0].keys()

with open('./global_warming_corpus.csv', 'w', encoding='utf_8_sig', newline='') as f:
    dict_writer = csv.DictWriter(f, keys, dialect='excel', delimiter='\t')
    dict_writer.writeheader()
    dict_writer.writerows(datalist)


