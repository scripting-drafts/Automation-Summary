import yt_dlp

URLS = [
        '',
        
      ]
        
opts = {'format': 'm4a/bestaudio/best',
        # ℹ️ See help(yt_dlp.postprocessor) for a list of available Postprocessors and their arguments
        # 'outtmpl': r'%(playlist_index)s %(title)s.%(ext)s',   # Number playlists songs i.e. https://www.youtube.com/watch?v=n2rVnRwW0h8&list=PL65E33789AA7052BC
        'postprocessors': [{  # Extract audio using ffmpeg
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'm4a',
            }]
        }

with yt_dlp.YoutubeDL(opts) as ydl:
    ydl.download(URLS)
