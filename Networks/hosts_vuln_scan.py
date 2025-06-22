from subprocess import Popen

hosts = None, '--nmap hosts.xml'
hosts = hosts[0]
ips = open('./ips', mode='r').read()

def get_hosts():
    sources = Popen([f'nmap {ips} -sV -oX hosts.xml'], shell=True).communicate()

    return sources

_, search_result = Popen([f'searchsploit {get_hosts() if hosts == None else hosts} --json 2>&1 | tee result.json'], shell=True).communicate()
print(search_result)
