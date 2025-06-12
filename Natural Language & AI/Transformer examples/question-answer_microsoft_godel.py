from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from pegasus_summarizer import PegasusSummarizer
import torch

device = "cuda:0" if torch.cuda.is_available() else "cpu"
print(device)

tokenizer = AutoTokenizer.from_pretrained("microsoft/GODEL-v1_1-large-seq2seq")
model = AutoModelForSeq2SeqLM.from_pretrained("microsoft/GODEL-v1_1-large-seq2seq")
model.to(device)

ps = PegasusSummarizer()

file = open('knowledge.txt', 'a+', encoding='utf-8-sig')
knowledge = file.readlines()

def generate(instruction, knowledge, dialog):
    if knowledge != '':
        knowledge = '[KNOWLEDGE] ' + knowledge
    dialog = ' EOS '.join(dialog)
    query = f"{instruction} [CONTEXT] {dialog} {knowledge}"
    input_ids = tokenizer(f"{query}", return_tensors="pt").to(device)
    input_ids = input_ids.input_ids
    outputs = model.generate(input_ids, max_length=128, min_length=8, top_p=0.9, do_sample=True).to(device)
    output = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return output

def store_knowledge(user_input):
    knowledge.append(ps.summarize(user_input))    # TODO: ps.summarize(user_input)

def quit_godel():
    for line in knowledge:
        if line != '':
            file.write(line + '\n')
    file.close()
    torch.cuda.empty_cache()
    
instruction = f'Instruction: given a comment, you need to response empathically.'

while True:
    try:
        user_input = input("[Gerard]: ")
        store_knowledge(user_input)

        if len(user_input) > 0:
            response = generate(instruction, ''.join(knowledge), [user_input])
            print(f"{response}")
        else:
            print("Please enter a valid payload")

    except KeyboardInterrupt:
        quit_godel()
        break
    
