from transformers import GPT2Tokenizer, GPT2LMHeadModel
import torch

class leonardo:
    def __init__(self):
        self.tokenizer = GPT2Tokenizer.from_pretrained("af1tang/personaGPT")
        self.model = GPT2LMHeadModel.from_pretrained("af1tang/personaGPT")

        if torch.cuda.is_available():
            self.model = self.model.cuda()
            
        self.flatten = lambda l: [item for sublist in l for item in sublist]

        file = open('corpus_repl_xs.txt', 'r')
        self.personas = []

        for line in file:
            self.personas.append(line)

        # print(self.personas)

        # self.personas = ["I'm Leonardo Da Vinci",
        #                  "I had three children with my beloved wife Katja",
        #                  "I sometimes enjoy playing chess",
        #                  "My idol is Michael Jackson"]

        self.personas = self.personas[:4]
        
        self.personas = self.tokenizer.encode(''.join(['<|p2|>'] + self.personas + ['<|sep|>'] + ['<|start|>']))

        self.dialog_hx = []

    def leonardo_rx(self, input):
        user_inp = self.tokenizer.encode(input + self.tokenizer.eos_token)
        # append to the chat history
        self.dialog_hx.append(user_inp)
            
        # generated a response while limiting the total chat history to 1000 tokens, 
        bot_input_ids = self.to_var([self.personas + self.flatten(self.dialog_hx)]).long()
        msg = self.generate_next(bot_input_ids)
        self.dialog_hx.append(msg)
        reply = "{}".format(self.tokenizer.decode(msg, skip_special_tokens=True))

        return reply

    def to_data(self, x):
        if torch.cuda.is_available():
            x = x.cpu()
        return x.data.numpy()

    def to_var(self, x):
        if not torch.is_tensor(x):
            x = torch.Tensor(x)
        if torch.cuda.is_available():
            x = x.cuda()
        return x

    def display_dialog_history(self, dialog_hx):
        for j, line in enumerate(dialog_hx):
            msg = self.tokenizer.decode(line)
            if j %2 == 0:
                print(">> User: "+ msg)
            else:
                print("Bot: "+msg)
                print()

    def generate_next(self, bot_input_ids, do_sample=True, top_k=11, top_p=.97, # defaults 10, .92 || 10/11, .96 good # 11, .97 experimental
                    max_length=1000):
        full_msg = self.model.generate(bot_input_ids, do_sample=do_sample,
                                                top_k=top_k, top_p=top_p,
                                                temperature=.70,  # 70 good
                                                # num_beams=16, # early_stopping=True,
                                                max_length=max_length, pad_token_id=self.tokenizer.eos_token_id)
        msg = self.to_data(full_msg.detach()[0])[bot_input_ids.shape[-1]:]
        return msg

    def cleanup(self):
        del self.tokenizer
        del self.model
        torch.cuda.empty_cache()
    