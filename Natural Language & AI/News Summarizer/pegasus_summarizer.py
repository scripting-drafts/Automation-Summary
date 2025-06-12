from transformers import PegasusForConditionalGeneration, PegasusTokenizer
from transformers import pipeline
import pandas as pd
import torch

df = pd.read_csv('./gb_corpus.csv', delimiter=';')
print(df)
text = df.loc[3, 'text']

model_name = 'google/pegasus-xsum'
torch_device = 'cuda' if torch.cuda.is_available() else 'cpu'

tokenizer = PegasusTokenizer.from_pretrained(model_name)
model = PegasusForConditionalGeneration.from_pretrained(model_name, pad_token_id=tokenizer.eos_token_id).to(torch_device)

inputs = tokenizer.batch_encode_plus(["summarize: " + text], return_tensors="pt", padding='max_length', truncation=True)
outputs = model.generate(inputs['input_ids'], num_beams=8, temperature=0.7, top_k=20, no_repeat_ngram_size=2, max_length=40, early_stopping=True) # num_return_sequences=5, do_sample=True, 

print([tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in outputs][0])

# for i, output in enumerate(outputs):
#     decoded = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in output][0]
#     print(f"{i}: {decoded}\n")