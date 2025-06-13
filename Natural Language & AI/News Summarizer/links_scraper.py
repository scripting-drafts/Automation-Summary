from selenium import webdriver

driver = webdriver.Firefox()
driver.implicitly_wait(10)
driver.get('https://www.sciencedaily.com/news/earth_climate/global_warming/')
driver.find_element_by_link_text('Headlines').click()

last_height = driver.execute_script('return document.body.scrollHeight')
popup = True

while True:
    try:
        load_btn = driver.find_element_by_css_selector('.btn.btn-custom > span')
        if 'Loading' in load_btn.text:
            pass

        elif 'Load more stories' in load_btn.text:
            load_btn.click()
            load_btn = driver.find_element_by_css_selector('.btn.btn-custom > span')
            if 'Loading' in load_btn.text:
                pass

            else:
                new_height = driver.execute_script('return document.body.scrollHeight')
                if new_height == last_height:
                    break
                
                last_height = new_height
    except Exception:
        if popup:
            try:
                driver.find_element_by_css_selector('button.hIGsQq:nth-child(1)').click()
                driver.find_element_by_css_selector('button.hIGsQq:nth-child(1)').click()
                popup = False
            except Exception:
                pass       

headlines = driver.find_elements_by_css_selector('.fa-ul.list-padded > li > a')
links = [x.get_attribute('href') for x in headlines]

file = open("./gb_links.txt", "+w")
for link in links:
    file.write(link + '\n')

print(len(links))
driver.quit()
