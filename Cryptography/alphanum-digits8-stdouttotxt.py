import string
import random
from time import sleep
from datetime import datetime
import sys

num = list(string.digits)
# get_seed, get_length
dt = str(datetime.today().strftime("%d-%m-%Y   %H_%M_%S"))
sys.stdout = open(f'nums_{dt}.txt', "w")

while True:
    try:
        if bool(random.getrandbits(1)):
            nums = '  '.join(random.SystemRandom().choice(num) for _ in range(8))
            time = str(datetime.today().strftime("%d-%m-%Y   [%H:%M:%S.%f]"))
            print(time, nums)

        sleep(random.gammavariate(0.1, 10))

    except KeyboardInterrupt:
        sys.stdout.close()