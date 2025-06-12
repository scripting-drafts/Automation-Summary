import pandas as pd
import csv
from sys import argv
import codecs
import os

file = argv[1]
df = pd.read_csv(file, delimiter='\t')

def printLines(file, n=10):
    with open(file, 'rb') as datafile:
        lines = datafile.readlines()
    for line in lines[:n]:
        print(line)

data_path = os.path.join("data")
datafile = os.path.join(data_path, "pairs.txt")
delimiter = '\t'
delimiter = str(codecs.decode(delimiter, "unicode_escape"))
qa_pairs = []

for row in df.index:
    row_id = df.loc[row, 'id']
    row_id_related = df['parent_id'].str.contains(row_id, case=True)
    c_ids = df.loc[row_id_related, 'body']
    for c_id in c_ids:
        qa_pairs.append([df.loc[row, 'body'], c_id])


print("\nWriting newly formatted file...")
with open(datafile, 'w', encoding='utf_8_sig') as outputfile:
    writer = csv.writer(outputfile, delimiter=delimiter, lineterminator='\n')
    for pair in qa_pairs:
        writer.writerow(pair)

print("\nSample lines from file:")
printLines(datafile)
