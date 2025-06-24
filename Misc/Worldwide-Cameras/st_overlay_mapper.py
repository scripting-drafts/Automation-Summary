from PIL import Image
import folium
import os

lat = 0
lon = 0

img_name = 'Weather/msg_fes-h60b.tif'
# Blended SEVIRI / LEO MW precipitation and morphologic information - MSG - 0 degree 
# URL -> https://view.eumetsat.int/geoserver/ows?service=WMS&request=GetMap&version=1.3.0&layers=msg_fes:h60b&styles=&format=image/geotiff&crs=EPSG:4326&bbox=-77,-77,77,77&width=800&height=800
img = Image.open(img_name)
# img.show()
img = img.convert("RGBA")
datas = img.getdata()

newData = []
for item in datas:
    if item[0] == 255 and item[1] == 255 and item[2] == 255:
        newData.append((255, 255, 255, 0))
    else:
        newData.append(item)

img.putdata(newData)
transparent_image = img_name.replace('.tif', '_with_alpha.png')
# img.show()
img.save(f'{transparent_image}', "PNG")

im = os.path.abspath(transparent_image)

m = folium.Map(
    location=[lat, lon],
    zoom_start=3,
    # max_bounds=True,
    crs='EPSG4326'
)

# folium.raster_layers.ImageOverlay(
#     image=im,
#     bounds=[[-60, -80.], [60., 50.]],    #[lat, lon],   [[-70, -90.], [70., 70.]]
#     weight=4,
#     opacity=1.,
# ).add_to(m)

m.save('Samples/Weather.html')
m.show_in_browser()
