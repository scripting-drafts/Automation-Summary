import pandas as pd
import csv
from  graphviz import Digraph as d
from sys import argv

file = argv[1]
df = pd.read_csv(file, delimiter='\t')
titles = list(dict.fromkeys(df.loc[:, 'title']))
dots = (title for title in titles)
parents_list = []

for title, dot in zip(titles, dots):
    sub = df.loc[df['title'] == title, 'sub'].iloc[0]
    dot = d(comment=str(sub), engine='circo')

    for row in range(df.loc[df['title'] == title].index[0], df.loc[df['title'] == title].index[-1]+1):
        if df.loc[row, 'parent_id'] == 'root':
            dot.node(str(df.loc[row,'id']), str(df.loc[row,'author']), shape='circle', fontname='helvetica')
            try:
                for children in df.loc[df['title'] == title, 'id']:
                    dot.edges(str(df.loc[row, 'id']) + children)
            except Exception as e:
                pass

        parent_pids_chunk_list = []
        parent_pids_list = []
        children = 0

        row_id = df.loc[row, 'id']
        row_pid = df.loc[row, 'parent_id']
        row_id_related = df['parent_id'].str.contains(row_id, case=True)
        row_pid_related = df['id'].str.contains(row_pid, case=True)
        c_ids = df.loc[row_id_related, 'id']
        p_id = df.loc[row_pid_related, 'id']
        p_pids = df.loc[row_pid_related, 'parent_id']

        for p_pid in p_pids:
            parent_pids_chunk_list.append(p_pid)
            p_pid_related = df['id'].str.contains(p_pid, case=True)
            p2_pids = df.loc[p_pid_related, 'parent_id']

            for p2_pid in p2_pids:
                if p2_pid:
                    parent_pids_chunk_list.append(p2_pid)
                    p2_pid_related = df['id'].str.contains(p2_pid, case=True)
                    p3_pids = df.loc[p_pid_related, 'parent_id']
                    for p3_pid in p3_pids:
                        if p3_pid:
                            parent_pids_chunk_list.append(p3_pid)

        for i in range(0, len(parent_pids_chunk_list), 1):
            parent_pids_list = parent_pids_chunk_list[i:i + 1]

        if 'root' in parent_pids_list:
            dot.node(str(df.loc[row,'id']), str(df.loc[row,'author']), shape='circle', fontname='helvetica')

        for c_id in c_ids:
            dot.edge(df.loc[row, 'id'], c_id, constraint = 'true')

    dot.render('test-output/' + str(sub) + '-' + str(title).replace('/', ' ') + '.gv', view=True)
