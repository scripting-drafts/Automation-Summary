
from transformers import AutoModelForQuestionAnswering, AutoTokenizer, pipeline, PretrainedConfig

model_name = "deepset/xlm-roberta-large-squad2"

# a) Get predictions
nlp = pipeline('question-answering', model=model_name, tokenizer=model_name)


# b) Load model & tokenizer
model = AutoModelForQuestionAnswering.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)

def model_func(prompt):
    '''
    # Function of a bert-large-cased-whole-word-masking-finetuned-squad model.
    '''
    
    QA_input = {
    'question': prompt,
    'context': 'Chemical and electrical synapses are the two major communication systems that permit cell-to-cell communication within the nervous system. Although most studies are focused on chemical synapses (glutamate, γ-aminobutyric acid, and other neurotransmitters), clearly both types of synapses interact and cooperate to allow the coordination of several cell functions within the nervous system. The pineal gland has limited independent axonal innervation and not every cell has access to nerve terminals. Thus, additional communication systems, such as gap junctions, have been postulated to coordinate metabolism and signaling. Using acutely isolated glands and dissociated cells, we found that gap junctions spread glycogenolytic signals from cells containing adrenoreceptors to the entire gland lacking these receptors. Our data using glycogen and lactate quantification, electrical stimulation, and high-performance liquid chromatography with electrochemical detection, demonstrate that gap junctional communication between cells of the rat pineal gland allows cell-to-cell propagation of norepinephrine-induced signal that promotes glycogenolysis throughout the entire gland. Thus, the interplay of both synapses is essential for coordinating glycogen metabolism and lactate production in the pineal gland.'
        }
        
    res = nlp(QA_input)
    return res
    
    

while True:
    try:
        prompt = input("[Gerard]: \n")
        print(f"[Frosty]: \n \n {model_func(prompt)}")
    except KeyboardInterrupt:
        break
