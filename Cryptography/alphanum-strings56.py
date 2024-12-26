import random
import string

lets = string.ascii_letters
digs = string.digits
 
output_string = ''.join(random.SystemRandom().choice(lets + digs) for _ in range(56))
 
print(output_string)
