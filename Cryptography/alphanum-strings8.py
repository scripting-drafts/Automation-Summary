import random
import string
from time import sleep
from datetime import datetime

lets = string.ascii_letters
digs = string.digits

while True:
    if bool(random.getrandbits(1)):
        output_string = '  '.join(random.SystemRandom().choice(lets + digs) for _ in range(8))
        time = str(datetime.today().strftime("%d-%m-%Y   [%H:%M:%S.%f]"))
        print(time, output_string)

    sleep(random.gammavariate(0.1, 10))
