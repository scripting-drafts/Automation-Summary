from selenium import webdriver
import csv

file = open("./global_warming_links.txt", "r")
links = [x.replace('\n', '') for x in file]

driver = webdriver.Firefox()
driver.implicitly_wait(10)

# links = [links[0], links[1]]
datalist = []

for link in links:
    try:
        driver.get(link)
        table = {}
        table['date'] = driver.find_element_by_css_selector('#date_posted').text
        table['title'] = driver.find_element_by_css_selector('#headline').text
        table['summary'] = driver.find_element_by_css_selector('#abstract').text
        fragments = driver.find_elements_by_css_selector('#text > p')
        debris = driver.find_elements_by_css_selector('#text > p > strong')

        for x in debris:
            fragments.remove(x)
                
        table['text'] = '\n'.join([x.text for x in fragments])

        datalist.append(table)
    
    except Exception as e:
        print(link, e)
        pass


driver.quit()

keys = datalist[0].keys()

with open('./gb_corpus.csv', 'w', encoding='utf_8_sig', newline='') as f:
    dict_writer = csv.DictWriter(f, keys, dialect='excel', delimiter=';')
    dict_writer.writeheader()
    dict_writer.writerows(datalist)


