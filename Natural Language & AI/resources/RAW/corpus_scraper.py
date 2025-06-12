from datetime import datetime
import os
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.keys import Keys
from subprocess import PIPE, Popen, call
from time import time, sleep
import secrets
import string
import shutil


# def fetch_url(url):
#     from subprocess import call, Popen, PIPE
#     try:
#         p = Popen(['curl', url ,'--silent'], stdout=PIPE)
#         a=[]
#         for line in p.stdout:
#             a.append(line)
#         p.wait()
#         print (a[0])
#     except:
#         print ("error")
#     finally:
#         print ("fetched in %ss" % ((time.time() - start)))

# current_path = os.getcwd() + '\\'
# profile_name = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
# profile_dir = "profile_dir_" + profile_name
# current_profile_dir = current_path + profile_dir
# print(current_profile_dir)
# call("firefox -CreateProfile \"" + profile_name + ' ' + current_profile_dir + "\"")



options = Options()
# options.add_argument('--headless')
options.set_preference('dom.webnotifications.enabled', False)
options.set_preference('dom.push.enabled', False)
options.set_preference('dom.webdriver.enabled', False)
options.set_preference('useAutomationExtension', False)
options.set_preference('privacy.trackingprotection.enabled', True)
profile_path = 'C:\\Users\\creat\\AppData\\Roaming\\Mozilla\\Firefox\\Profiles\\e76nnqhd.iouiewquro.bot'

date = datetime.now()

start = time()

driver = webdriver.Firefox(firefox_profile=profile_path, options=options)
driver.implicitly_wait(10)
driver.get("https://www.biography.com/actor/leonardo-dicaprio")

paragraphs = []
SCROLL_PAUSE_TIME = 1

# Get scroll height


try:
    sleep(1)
    driver.switch_to.frame(driver.find_element_by_css_selector("#sp_message_iframe_342240"))
    driver.find_element_by_css_selector('.settings-button').click()

    sleep(3)
    # driver.switch_to.frame(driver.find_element_by_id('sp_message_iframe_335237'))
    for _ in range(5):
        try:
            overlay = driver.find_element_by_css_selector('.message')
            buttons = driver.find_elements_by_css_selector('button') # .sp_choice_type_SAVE_AND_EXIT
            if 'Save' in buttons[3].text:
                buttons[3].click()
            sleep(1)
        except Exception:
            break

    driver.switch_to.default_content()
    # page = driver.find_element_by_css_selector('#main-content')
    # page.sendKeys(Keys.PAGE_DOWN)

    sleep(2)
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        # Scroll down to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Wait to load page
        sleep(SCROLL_PAUSE_TIME)

        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    
    for x in range(100):
        try:
            paragraph = driver.find_elements_by_css_selector('p:nth-child({})'.format(str(x)))
            paragraphs.extend(paragraph)
            
        except Exception:
            break

    paragraphs = paragraphs[:paragraphs.index("We strive for accuracy and fairness. If you see something that doesn't look right, contact us!")]
    clean_paragraphs = [x for x in paragraphs if x not in clean_paragraphs]


except Exception as e:
    print(e)

for x in paragraphs:
    print(x)


driver.quit()


# try:
#     driver.get("about:profiles")
#     profiles = driver.find_elements_by_css_selector("#profiles > div")
#     for profile in profiles:
#         if profile_name in profile.text:
#             profile.find_element_by_css_selector("button:nth-child(4)").click()
#             sleep(5)
#             #profiles > div:nth-child(4) > button:nth-child(4)
#             # webdriver.ActionChains(driver).send_keys(Keys.TAB).perform()
#             webdriver.ActionChains(driver).send_keys(Keys.ENTER).perform()
#             sleep(1)
#         else:
#             print("Couldn't remove the profile from about:profiles")

# title = driver.find_element_by_css_selector()

# for request in driver.requests:
#     if request.response and ".m3u8" in request.url:
#         call("ffmpeg -protocol_whitelist file,http,https,tcp,tls,crypto -i", request.url, "-c copy ", title)
#         print(
#             "REQ:", request.url, "\n",
#             "STAT:", request.response.status_code, "\n",
#             "CT:", request.response.headers['content-type'], "\n"
#         )
# except KeyboardInterrupt:
#     driver.quit()

# call("firefox -ProfileManager")

# shutil.rmtree(profile_path)
