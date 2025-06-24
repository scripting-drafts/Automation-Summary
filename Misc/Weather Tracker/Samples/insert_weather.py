import streamlit as st

# Read your HTML map
with open("Europe_maptest.html", "r") as f:
    html = f.read()

# Inject the weather tile (OpenWeatherMap example)
weather_js = """
<script>
setTimeout(function() {
    var weatherLayer = L.tileLayer(
      'https://tile.openweathermap.org/map/precipitation_new/{z}/{x}/{y}.png?appid=API',
      {attribution: 'Weather data © OpenWeatherMap', opacity: 1.0}
    );
    weatherLayer.addTo(mapname);
}, 500);
</script>
"""

patched_html = html.replace("</body>", weather_js + "</body>")

# Show in Streamlit app
st.components.v1.html(patched_html)
