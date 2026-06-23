import urllib.request
import json
try:
    urllib.request.urlopen("http://localhost:8000/api/v1/notifications/")
except Exception as e:
    print(e)
