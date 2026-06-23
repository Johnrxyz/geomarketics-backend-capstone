import requests
from bs4 import BeautifulSoup

url = "https://calabarzon.da.gov.ph/da-calabarzon-bantay-presyo/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.content, 'html.parser')

print("--- DRIVE LINKS ---")
for a in soup.find_all('a'):
    href = a.get('href')
    if href and 'drive.google.com/file/d/' in href:
        print(f"TEXT: {a.text.strip()} | URL: {href}")
        break
