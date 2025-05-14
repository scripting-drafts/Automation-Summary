import folium
import branca
import warnings
import pandas as pd
import numpy as np
import seaborn as sns
import tensorflow as tf
from tensorflow.keras.layers import *
import logging
warnings.simplefilter(action='ignore', category=FutureWarning)
print('x' in np.arange(5))
tf.get_logger().setLevel(logging.ERROR)

df = pd.read_csv('/home/gerard/2020-11-15_00:55:38_barcelona-supermercado.csv', delimiter=';')
df = df.drop('address', axis=1).drop('errors', axis=1)

keywords = ['Supermercado', 'Tienda de alim', 'ultramarinos', 'delicatessen', 'Fruter', 'congelados', 'Mercado']

df_filter = df.type.isin(keywords)
df = df[df_filter]

df = df[df.comments < 500]

df.fillna(value=0, inplace=True)

X_train = df[['rate', 'comments']].values
y_train = df[['lat', 'lon']].values

def train_input_fn():
    X_train_dic = {}
    X_train_dic['rate'] = []
    X_train_dic['comments'] = []
    count = 0

    for test in np.nditer(X_train):
        if count % 2 == 0:
            X_train_dic['rate'].append(float(test))
        else:
            X_train_dic['comments'].append(float(test))
        count += 1

    return X_train_dic, y_train


def pred_input_fn():
    X_test_dic = {}
    X_test_dic['rate'] = [5.]
    X_test_dic['comments'] = [499.]

    return X_test_dic


rate = tf.feature_column.numeric_column("rate",shape=[1])
comments = tf.feature_column.numeric_column("comments",shape=[1])

model = tf.estimator.DNNRegressor(
  hidden_units    = [1024, 512, 256, 128],
  feature_columns = [rate, comments],
  label_dimension = y_train.shape[1],
  activation_fn   = 'relu',
  dropout         = 0.2,
  optimizer       = 'Adam',
  model_dir       = './Google-Places-DNNRegressor'
  )

mode = int(input('''
Choose one:
1. Training
2. Predicting
'''))


if mode == 1:
    print('Training...')
    for _ in range(1000):
      r = model.evaluate(train_input_fn,steps=1);
      print('Loss:',r['loss'])
      model.train(train_input_fn,steps=1000)

elif mode == 2:
    predictions = model.predict(pred_input_fn)
    print(next(predictions)['predictions'][:])

    map_q = input('Do you want a map of the result? y/n \n')

    if map_q == 'y':
        pred_output = {'latitude': next(predictions)['predictions'][0],
                    'longitude': next(predictions)['predictions'][1]}
        m = folium.Map(location=[41.4, 2.17], zoom_start=13)

        for row in df.index:
            lat, lon, comments = df.loc[row, 'lat'], df.loc[row, 'lon'], df.loc[row, 'comments']

            radius = int(df.loc[row, 'rate'])*int(df.loc[row, 'rate'])/2+3

            tooltip = (df.loc[row, 'name']) + ' | ' + str(df.loc[row, 'rate']) + ' Stars | ' + str(int(df.loc[row, 'comments'])) + ' Comments'

            if comments < 10:
                color = '#{:02x}{:02x}{:02x}'.format(255, 215, 0)
            elif comments >= 10 and comments <= 50:
                color = '#{:02x}{:02x}{:02x}'.format(249, 56, 34)
            elif comments > 50 and comments <= 200:
                color = '#{:02x}{:02x}{:02x}'.format(214, 37, 152)
            elif comments > 200 and comments <= 500:
                color = '#{:02x}{:02x}{:02x}'.format(78, 0, 142)
            elif comments > 500:
                color = '#{:02x}{:02x}{:02x}'.format(0, 36, 156)

            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                tooltip=tooltip,
                fill=True,
                fill_color=color,
                stroke = False,
                fill_opacity=.5
                ).add_to(m)

        colormap = branca.colormap.LinearColormap(colors=[
            (255, 215, 0, 255),
            (249, 56, 34, 255),
            (214, 37, 152, 255),
            (78, 0, 142, 255),
            (0, 36, 156, 255)
        ]).scale(0, 600)
        colormap.caption = 'Color per Comments, Radius per Stars Rate'
        colormap.add_to(m)

        folium.CircleMarker(
            location=[pred_output['latitude'], pred_output['longitude']],
            radius=10,
            tooltip='Best Spot',
            fill=True,
            fill_color='#{:02x}{:02x}{:02x}'.format(0, 255, 100),
            stroke = False,
            fill_opacity=1.
            ).add_to(m)

        m.save('map.html')


    scatter_q = input('Do you want a scatterplot of the result? y/n \n')

    if scatter_q == 'y':
        pred_output = {'latitude': [next(predictions)['predictions'][0]],
                    'longitude': [next(predictions)['predictions'][1]]}
        test_predictions = pd.DataFrame.from_dict(pred_output)
        test_predictions['type'] = 'model_prediction'
        y_test_df = pd.DataFrame(y_train, columns=['latitude', 'longitude'])
        y_test_df['type'] = 'y_test_true'
        frames = [y_test_df, test_predictions]
        pred_df = pd.concat(frames)

        pred_plot = sns.scatterplot(x='latitude', y='longitude', hue='type', data=pred_df, alpha=0.6, linewidth=0, palette='viridis')
        pred_plot.invert_yaxis()
        pred_plot.invert_xaxis()
        fig = pred_plot.get_figure()
        fig.savefig('prediction_scatterplot.png', dpi = 600)
    else:
        exit()

else:
    exit()
