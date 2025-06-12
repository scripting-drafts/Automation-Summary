from transformers import PegasusForConditionalGeneration, PegasusTokenizer
from transformers import pipeline
from selenium import webdriver
from time import sleep
import datetime
import random
import torch

while True:
    profile = webdriver.FirefoxProfile()
    profile.set_preference('dom.webnotifications.enabled', False)
    profile.set_preference('dom.push.enabled', False)
    profile.set_preference('dom.webdriver.enabled', False)
    profile.set_preference('useAutomationExtension', False)
    profile.set_preference('privacy.trackingprotection.enabled', True)
    profile.update_preferences()

    date = datetime.datetime.now()
    
    driver = webdriver.Firefox(profile)
    driver.implicitly_wait(10)
    driver_On = True

    # Get today's news links
    driver.get('https://www.theguardian.com/environment/climate-change/' + date.strftime('%Y') + '/' + date.strftime('%b') + '/' + date.strftime('%d') + '/all/')
    raw_links = driver.find_element_by_css_selector('.fc-container__inner > a')
    links = [x.get_attribute('href') for x in raw_links]

    # Scrap text for each link
    news_list = []

    for link in links:
        driver.get(link)
        fragments = driver.find_elements_by_css_selector('.article-body-commercial-selector.css-79elbk.article-body-viewer-selector > p')
        news_list.append(['\n'.join([x.text.replace('[', '(').replace(']', ')') for x in fragments])])

    # Feed it to the model
    summaries = []

    model_name = 'google/pegasus-xsum'
    torch_device = 'cuda' if torch.cuda.is_available() else 'cpu'
    tokenizer = PegasusTokenizer.from_pretrained(model_name)
    model = PegasusForConditionalGeneration.from_pretrained(model_name).to(torch_device)

    for text in news_list:
        inputs = tokenizer.batch_encode_plus(['summarize: ' + text[0]], return_tensors='pt', padding='max_length', truncation=True)
        outputs = model.generate(inputs['input_ids'], num_beams=8, max_length=40, early_stopping=True)
        summaries.append([tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in outputs])

    # Post to Twitter every random time
    while date.strftime('%d') == datetime.datetime.now().strftime('%d'):
        while summaries:
            summmary = random.choice(summaries)
            summaries.remove(summary)
            # TODO post to twitter && post with summary[0]
            sleep(random.uniform(30*60, 120*60)) # To Rethink
        if driver_On:
            driver.quit()
            driver_On = False
        sleep(180*60)
