import base64
import requests
from bs4 import BeautifulSoup
from st_logger import Logger
import pandas as pd
import csv
from io import BytesIO
log = Logger().logging()

# Copy Image Data-Url
# data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAQAAAADCAQAAAAe/WZNAAAADklEQVR42mNkgAJGDAYAAFEABCaLYqoAAAAASUVORK5CYII=

<<<<<<< HEAD
df = pd.read_csv('coords_asia.csv', delimiter=';')
=======
region = 'Australia'

df = pd.read_csv(f'./Processing/Coords_{region}.csv', delimiter=';')
>>>>>>> 3804c98 (update and improvements preview)
datalist = []

def b64_encode(jpg_img):
     encoded = base64.b64encode(open(jpg_img, 'rb').read())

     return encoded

def write_to_csv(datalist):
    keys = datalist[0].keys()

<<<<<<< HEAD
    with open('./coords_asia_img.csv', 'w', encoding='utf_8_sig', newline='') as f:
=======
    with open(f'./Processing/Complete_{region}.csv', 'w', encoding='utf_8_sig', newline='') as f:
>>>>>>> 3804c98 (update and improvements preview)
        dict_writer = csv.DictWriter(f, keys, dialect='excel', delimiter=';')
        dict_writer.writeheader()
        dict_writer.writerows(datalist)

for row in range(0, len(df.index)):
    data = {}
    img = None
    try:
        url = df.loc[row, 'url']
        response = requests.get(url, allow_redirects=False)
        sc = response.status_code

        if sc == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for a_tag in soup.findAll('img'):
                unformatted_class = a_tag.attrs.get('class')
                classs = ''.join(unformatted_class) if type(unformatted_class) == list else unformatted_class

                if classs == 'image-preview-last-thumbnail':
                    style = a_tag.attrs.get('style')

                    if style.startswith('background-image: image-set(url('):
                        img = str(a_tag).split('background-image: image-set(url(')[1].split('.jpg')[0] + '.jpg'
                    
                    if style.startswith('background-image: url('):
                        img = str(a_tag).split('background-image: url(')[1].split('.jpg')[0] + '.jpg'

            if img is not None:
                log.debug(f'GOTTEN: {img}')
                response = requests.get(img.strip(r'\'').strip())
                img = BytesIO(response.content).read()
                encoded = base64.b64encode(img) # open('mypict.jpg', 'rb').read())
                log.debug(f'ENCODED: {encoded[:64]}')

                # DEBUG
                # im = base64.b64decode(encoded)
                # with open('filename.jpg', 'wb') as f:
                #     f.write(im)

                data['region'] = df.loc[row, 'region']
                data['country'] = df.loc[row, 'country']
                data['zone'] = df.loc[row, 'zone']
                data['lat'] = df.loc[row, 'lat']
                data['lon'] = df.loc[row, 'lon']
                data['url'] = df.loc[row, 'url']
                data['ref'] = df.loc[row, 'ref']
                data['img'] = encoded.decode('utf-8')

            elif img is None:
                data['region'] = df.loc[row, 'region']
                data['country'] = df.loc[row, 'country']
                data['zone'] = df.loc[row, 'zone']
                data['lat'] = df.loc[row, 'lat']
                data['lon'] = df.loc[row, 'lon']
                data['url'] = df.loc[row, 'url']
                data['ref'] = df.loc[row, 'ref']
                data['img'] = ''

            datalist.append(data)

        else:
            raise AssertionError('URL not found')
    
    except Exception:
        write_to_csv(datalist)

    finally:
        write_to_csv(datalist)