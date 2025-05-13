import os, re

for i in os.listdir('.'):
    if i.startswith('NA'):
        os.rename(i, re.sub(r'NA ', '', i))

    # os.rename(i, re.sub(r'\(\d{4}\)', '(2009) ({n})'.format(n=n), i))
