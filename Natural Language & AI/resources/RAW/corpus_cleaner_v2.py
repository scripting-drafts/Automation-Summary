# from transformers import PegasusForConditionalGeneration, PegasusTokenizer
# import torch
from pszemraj_summarizer import generate_summarizer, summarize


file = open('corpus.txt', 'r')
persona = []
persona_sum = []

summarizer = generate_summarizer()

for line in file:
    if len(line) >= 80:
        line = summarize(summarizer, line)
        # line = ''.join(line)
    persona_sum.append(line)

for line in persona_sum:
    if type(line) == dict:
        persona_sum.append(line['summary_text'])
    else:
        persona_sum.append(line)

print(persona_sum)
persona_sum = ''.join([''.join(x) for x in persona_sum if type(x) == list])
print(persona_sum)

w = open('corpus_sum.txt', 'a')

w.write(persona_sum)
w.close()

