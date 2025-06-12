from concurrent.futures import ThreadPoolExecutor
import os
import platform
from subprocess import Popen, call

platform_name = platform.system()
root_path = os.path.abspath('.')
print(root_path)

repositories = ['https://github.com/CompVis/stable-diffusion.git',
                'https://github.com/CompVis/taming-transformers.git',
                'https://github.com/crowsonkb/k-diffusion.git',
                'https://github.com/sczhou/CodeFormer.git',
                'https://github.com/salesforce/BLIP.git']

scripts = ['https://gist.github.com/camenduru/9ec5f8141db9902e375967e93250860f/raw/d0bcf01786f20107c329c03f8968584ee67be12a/run_n_times.py']

extensions = ['https://github.com/yfszzx/stable-diffusion-webui-images-browser',
            'https://github.com/deforum-art/deforum-for-automatic1111-webui']


models = ['https://huggingface.co/nitrosocke/Arcane-Diffusion/resolve/main/arcane-diffusion-v3.ckpt',
         'https://huggingface.co/DGSpitzer/Cyberpunk-Anime-Diffusion/resolve/main/Cyberpunk-Anime-Diffusion.ckpt',
         'https://huggingface.co/prompthero/midjourney-v4-diffusion/resolve/main/mdjrny-v4.ckpt',
         'https://huggingface.co/nitrosocke/mo-di-diffusion/resolve/main/moDi-v1-pruned.ckpt',
         'https://huggingface.co/Fictiverse/Stable_Diffusion_PaperCut_Model/resolve/main/PaperCut_v1.ckpt',
         'https://huggingface.co/lilpotat/sa/resolve/main/samdoesarts_style.ckpt',
         'https://huggingface.co/hakurei/waifu-diffusion-v1-3/resolve/main/wd-v1-3-float32.ckpt',
         'https://huggingface.co/CompVis/stable-diffusion-v-1-4-original/resolve/main/sd-v1-4.ckpt',
         'https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.ckpt',
         'https://huggingface.co/runwayml/stable-diffusion-inpainting/resolve/main/sd-v1-5-inpainting.ckpt',
         'https://huggingface.co/Linaqruf/anything-v3.0/resolve/main/Anything-V3.0-pruned.ckpt',
         'https://huggingface.co/Linaqruf/anything-v3.0/resolve/main/Anything-V3.0.vae.pt',
         'https://huggingface.co/stabilityai/stable-diffusion-2/resolve/main/768-v-ema.ckpt',
         'https://raw.githubusercontent.com/Stability-AI/stablediffusion/main/configs/stable-diffusion/v2-inference-v.yaml',
         'https://huggingface.co/stabilityai/stable-diffusion-2-1/resolve/main/v2-1_768-ema-pruned.ckpt',
         'https://raw.githubusercontent.com/Stability-AI/stablediffusion/main/configs/stable-diffusion/v2-inference-v.yaml'
         ]

model_download_program = 'wget.exe -q' if platform_name.find('windows') != -1 else 'wget -q'
model_download_arg = '-O'

extensions_download_program = 'git clone'
extensions_download_arg = ''

sep = '\\\\' if platform_name.find('windows') != -1 else '/'
pids = []

# Repositories names and path
repositories_names = [x.split('/')[-1].replace('.git', '') for x in repositories]
repositories_paths = [f'{root_path}{sep}stable-diffusion-webui{sep}repositories{sep}{repo_name}' for repo_name in repositories_names]

# Scripts names and paths
if isinstance(scripts[1:], list):
    scripts_names = [x.split('/')[-1] for x in scripts]
else:
    scripts_names = [scripts[0].split('/')[-1]]

scripts_paths = [f'{root_path}{sep}stable-diffusion-webui{sep}scripts{sep}{script_name}' for script_name in scripts_names]

# Extensions names and paths
extensions_names = [x.split('/')[-1] for x in extensions]
extensions_paths = [f'{root_path}{sep}stable-diffusion-webui{sep}extensions{sep}{extension_name}' for extension_name in extensions_names]

# Models names and paths
model_names = [x.split('/')[-1] for x in models]
models_paths = [f'{root_path}{sep}stable-diffusion-webui{sep}models{sep}Stable-diffusion{sep}{model_name}' for model_name in model_names]

### DEBUGGING PURPOSES
# def debug(item):
#     print(item)

# with ThreadPoolExecutor(max_workers=3) as executor:
#     for path in zip(scripts_names, scripts_paths):
#         executor.submit(debug, path)

#     for path in extensions_paths:
#         executor.submit(debug, path)

#     for path in models_paths:
#         executor.submit(debug, path)

def runner(program, arg, url, filename):
    run = Popen(f'{program} {url} {arg} {filename}', shell=True)
    pids.append(run.pid)
    run.communicate()

def kill_process(pid):
    call(f'taskkill /PID {pid} /F', shell=True)

with ThreadPoolExecutor(max_workers=3) as executor:
    for url, path in zip(repositories_names, repositories_paths):
        executor.submit(runner, extensions_download_program, extensions_download_arg, url, path)

    for url, path in zip(scripts, scripts_paths):
        executor.submit(runner, model_download_program, model_download_arg, url, path)

    for url, path in zip(extensions, extensions_paths):
        executor.submit(runner, extensions_download_program, extensions_download_arg, url, path)

    for url, path in zip(models, models_paths):
        executor.submit(runner, model_download_program, model_download_arg, url, path)

# for pid in pids:
#     kill_process(pid)