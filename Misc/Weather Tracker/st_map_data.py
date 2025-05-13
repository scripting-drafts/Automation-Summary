# from sys import argv
from io import BytesIO
from PIL import Image
import folium
import pandas as pd
import base64
from st_bookmarks import favourites

region = 'Australia'
mode = ''

<<<<<<< HEAD
df = pd.read_csv('coords_asia_img.csv', delimiter=';')  # 'Samples/bulkall.csv'
=======
central_point = {
    'Asia': [44., 135.],
    'Australia': [10., 135.],
    'Europe': [46, 9],
    'Polska': [54, 18.17],
    'Europe with Polska': [46, 9],
}

latitude, longitude = central_point[region]

if region != 'Europe with Polska':
    favourites = favourites[region]

elif region == 'Europe with Polska':
    region = region.replace(' ', '_')
    favourites = favourites['Europe'] + favourites['Polska']
    
else:
    print('Introduce valid region')

df = pd.read_csv(f'./Processing/Complete_{region}.csv', delimiter=';')  # 'Samples/bulkall.csv'
>>>>>>> 3804c98 (update and improvements preview)

m = folium.Map(
    location=[latitude, longitude], # list(t.transform(latitude, longitude))
    zoom_start=5,
    attr="<a href=https://github.com/scripting-drafts/>scripting-drafts</a>"
)

def get_frame(url,url_frontend,img_url,width,height):
    html = """ 
            <!doctype html>
        <html>
        <iframe id="myIFrame" width="{}" height="{}" src={}""".format(width,height,img_url) + """ frameborder="0"></iframe>
        <script type="text/javascript">
        var resizeIFrame = function(event) {
            var loc = document.location;
            if (event.origin != loc.protocol + '//' + loc.host) return;

            var myIFrame = document.getElementById('myIFrame');
            if (myIFrame) {
                myIFrame.style.height = event.data.h + "px";
                myIFrame.style.width  = event.data.w + "px";
            }
        };
        if (window.addEventListener) {
            window.addEventListener("message", resizeIFrame, false);
        } else if (window.attachEvent) {
            window.attachEvent("onmessage", resizeIFrame);
        }
        </script>""" + """
        <a href="{}" target="_blank" >{}</a>""".format(url,url_frontend) + """
        </html>"""
    
    return html

for row in range(0, len(df.index)):
    lat, lon = df.loc[row, 'lat'], df.loc[row, 'lon']

    tooltip = str(df.loc[row, 'zone'])
    url = str(df.loc[row, 'url'])
    url_frontend = ' '.join([x.capitalize() for x in tooltip.split(' ')] if tooltip[1:] else tooltip.capitalize())

    img_url = df.loc[row, 'img']

    im = base64.b64decode(img_url.encode('utf_8_sig'))
    img = Image.open(BytesIO(im))
    buffer = img.resize((210,118))   # 210,118 - 158,89
    
    buffered = BytesIO()
    buffer.save(buffered, format="JPEG")
    img_url = base64.b64encode(buffered.getvalue()).decode('utf_8_sig')

<<<<<<< HEAD
=======
    except Exception:
        '''I break "no image" links for convenience'''
        print(url)
        img_url = ''
    
>>>>>>> 3804c98 (update and improvements preview)
    html = '<img src="data:image/png;base64,{}"><p></p><a href="{}" target="_blank" >{}</a>'.format
    iframe = folium.IFrame(html(img_url,url,url_frontend), width=245, height=180)
    popup = folium.Popup(iframe, max_width=270)

    if url_frontend not in favourites:
        blue = '#{:02x}{:02x}{:02x}'.format(214, 37, 152) if mode == 'pink' else '#{:02x}{:02x}{:02x}'.format(31, 61, 159)
        radius = 4
        fill_color = blue
        fill_opacity = .5

    elif url_frontend in favourites:
        dark_blue = '#{:02x}{:02x}{:02x}'.format(31, 61, 159) if mode == 'pink' else '#{:02x}{:02x}{:02x}'.format(129, 159, 255)
        radius = 5
        fill_color = dark_blue
        fill_opacity = .7

    folium.CircleMarker(
        location=[lat, lon],
        radius= radius,
        tooltip=url_frontend,
        fill=True,
        fill_color=fill_color,  # color pink 214, 37, 152, purple 129, 159, 255, blue 31, 61, 159
        stroke = False,
        fill_opacity=fill_opacity,
        popup=popup
        ).add_to(m)        

<<<<<<< HEAD
m.save('Samples/maptest.html')
=======
mode = '_pink' if mode == 'pink' else ''
m.save(f'Samples/Map_{region}{mode}.html')
>>>>>>> 3804c98 (update and improvements preview)
m.show_in_browser()