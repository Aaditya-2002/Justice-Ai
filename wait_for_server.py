import urllib.request
import urllib.error
import time
n = 0
while n < 10:
    try:
        response = urllib.request.urlopen('http://localhost:8000/health/live')
        print('Live:', response.read().decode())
        break
    except urllib.error.URLError:
        print('Waiting...')
        time.sleep(1)
        n += 1
