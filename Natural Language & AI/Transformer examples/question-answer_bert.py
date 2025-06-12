
import torch
from transformers import AutoTokenizer, AutoModelForQuestionAnswering


# Model Repository on huggingface.co
tokenizer = AutoTokenizer.from_pretrained("bert-large-uncased-whole-word-masking-finetuned-squad")
model = AutoModelForQuestionAnswering.from_pretrained('bert-large-uncased-whole-word-masking-finetuned-squad', return_dict=True)

context = "A human and a robot are casually talking about the weather."

def model_func(prompt):
    '''
    # Function of a bert-large-cased-whole-word-masking-finetuned-squad model.
    '''
    
    # input_ids = tokenizer(prompt, return_tensors="pt")

    inputs = tokenizer(prompt, context, add_special_tokens=True, return_tensors="pt")
    input_ids = inputs["input_ids"].tolist()[0] # the list of all indices of words in question + context

    answer_start_scores, answer_end_scores = model(**inputs, return_dict=False)

    answer_start = torch.argmax(answer_start_scores)  # Get the most likely beginning of answer with the argmax of the score
    answer_end = torch.argmax(answer_end_scores) + 1  # Get the most likely end of answer with the argmax of the score

    answer = tokenizer.convert_tokens_to_string(tokenizer.convert_ids_to_tokens(input_ids[answer_start:answer_end]))

    return answer
    
    

while True:
    try:
        prompt = input("[Gerard]: \r")
        # print(f"input payload: \n \n{prompt}")
        print(f"[Frosty]: \n \n {model_func(prompt)}")
    except KeyboardInterrupt:
        break
