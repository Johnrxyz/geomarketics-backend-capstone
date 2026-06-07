import requests, json, base64, sys, os
import django
from pathlib import Path

# Setup minimal Django environment to get settings
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from django.conf import settings

api_key = getattr(settings, 'GEMINI_API_KEY', None)

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

payload = {
    "contents": [{
        "parts": [
            {"text": "Hello, how are you?"}
        ]
    }]
}
res = requests.post(url, json=payload)
print(res.status_code, res.text)
