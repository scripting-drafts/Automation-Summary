import os
import secrets
import string
from subprocess import call

current_path = os.getcwd() + '\\'
profile_name = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
profile_dir = "profile_dir_" + profile_name
current_profile_dir = current_path + profile_dir
print(current_profile_dir)
call("firefox -CreateProfile \"" + profile_name + ' ' + current_profile_dir + "\"")