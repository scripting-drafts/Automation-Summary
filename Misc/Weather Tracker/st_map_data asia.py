from io import BytesIO
from PIL import Image
import folium
import pandas as pd
import base64
from threading import Thread

favourites = ['Matsumoto Kappa Bridge', 'Sendai Airport',
              'Kushiro Harbour', 'Cherry Blossoms Railway Station',
              'Tokyo Hachioji Takao Station',
              'Tottori Sand Dunes', 'Tottori Sea Of Japan',
              'Tokyo Sky Tree Panoramic View', 'Tokyo Chidorigafuchi Park Sakura',
              'Luobei County Dulu River Nature Reserve',
              'Nagasaki Harbour']

central_point = {
    'Asia': [44., 135.],
    'Europe': [45.4, 10.17]
}

latitude, longitude = central_point['Asia']

df = pd.read_csv('eu_complete.csv', delimiter=';')

m = folium.Map(
    location=[latitude, longitude], # list(t.transform(latitude, longitude))
    zoom_start=5,
    attr="<a href=https://github.com/scripting-drafts/>scripting-drafts</a>"
)

def split_odd_list(a, n):
    '''Split list'''
    k, m = divmod(len(a), n)
    return (a[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(n))

def toast_map(row):
    lat, lon = df.loc[row, 'lat'], df.loc[row, 'lon']
    zone = df.loc[row, 'zone']

    img_url = df.loc[row, 'img']
    url = str(df.loc[row, 'url'])

    url_frontend = ' '.join([x.capitalize() for x in zone.split(' ')] if zone[1:] else zone.capitalize())
    im = base64.b64decode(img_url.encode('utf_8_sig'))
    img = Image.open(BytesIO(im))
    buffer = img.resize((210,118))
    
    buffered = BytesIO()
    buffer.save(buffered, format="JPEG")
    img_url = base64.b64encode(buffered.getvalue()).decode('utf_8_sig')

    html = '<img src="data:image/png;base64,{}"><p></p><a href="{}" target="_blank" >{}</a>'.format
    iframe = folium.IFrame(html(img_url,url,url_frontend), width=245, height=195)
    popup = folium.Popup(iframe, max_width=245)

    if url_frontend not in favourites:
        bourdeaux = '#{:02x}{:02x}{:02x}'.format(255,20,147)
        radius = 4
        fill_color = bourdeaux
        fill_opacity = .5

    elif url_frontend in favourites:
        blue = '#{:02x}{:02x}{:02x}'.format(25,25,112)
        radius = 5
        fill_color = blue
        fill_opacity = .7

    folium.CircleMarker(
        location=[lat, lon],
        radius=radius,
        tooltip=url_frontend,
        fill=True,
        fill_color=fill_color,
        stroke = False,
        fill_opacity=fill_opacity,
        popup=popup
        ).add_to(m)        

ts = []
chunks = split_odd_list(range(0, len(df.index)), 5)

for chunk in chunks:
    for row in chunk:
        t = Thread(target=toast_map, args=(row,))
        ts.append(t)
        t.start()

    for t in ts:
        t.join()

m.save('Samples/maptest.html')
m.show_in_browser()