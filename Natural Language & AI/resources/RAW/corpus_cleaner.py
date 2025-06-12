from transformers import PegasusForConditionalGeneration, PegasusTokenizer
import torch

file = open('corpus.txt', 'r')
persona = []

for line in file:
    persona.append(line)

persona_sum = []
model_name = 'google/pegasus-xsum'
torch_device = 'cuda' if torch.cuda.is_available() else 'cpu'
tokenizer = PegasusTokenizer.from_pretrained(model_name)
model = PegasusForConditionalGeneration.from_pretrained(model_name).to(torch_device)

def xsum(text):
    inputs = tokenizer.batch_encode_plus(["summarize: " + text], return_tensors="pt", padding='max_length', truncation=True)
    outputs = model.generate(inputs['input_ids'], num_beams=12, max_length=40, early_stopping=True)
    decoded_output = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=False) for g in outputs][0]

    return decoded_output

print(persona)

for text in persona:
    if len(text) >= 80:
        if len(text.split('. ')) >= 3:
            chunks = text.split('. ')
            paragraph_percentage_selector = int(len(chunks) / 0.33)
    
            for _ in range(paragraph_percentage_selector):
                chunk = max(chunks)
                decoded_output = xsum(chunk)
                chunks[chunks.index(chunk)] = decoded_output

            shortened = '. '.join([x for x in chunks])
            persona_sum.append(shortened)
    else:
        persona_sum.append(text)

persona_sum = '\n'.join([x for x in persona_sum])
w = open('corpus_sum.txt', 'a')
w.write(persona_sum)
w.close()

print(persona_sum)
