import sys
from subprocess import Popen

def pkill(proc):
        platform = sys.platform

        match platform:
            case "linux":
                terminate_cmd = 'kill -9'
            case 'win32':
                terminate_cmd = 'taskkill /F /PID'
            case 'cygwin':
                terminate_cmd = 'taskkill /F /PID'
            case 'darwin':
                terminate_cmd = 'kill -9'

        Popen(f'{terminate_cmd} {proc}', shell=True).communicate()

        # return terminate_cmd
