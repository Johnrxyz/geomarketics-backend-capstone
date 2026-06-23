import urllib.request
import urllib.error
import json

data = {
    "vendor": 1,
    "violation_type": "Test",
    "description": "Test",
    "severity": "low",
    "violation_date": "2026-06-23",
    "photo": "data:image/jpeg;base64,AAAA"
}
req = urllib.request.Request(
    'http://localhost:8000/api/violations/',
    data=json.dumps(data).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    response = urllib.request.urlopen(req)
    print("SUCCESS", response.status)
except urllib.error.HTTPError as e:
    print("HTTP Error", e.code)
    body = e.read().decode('utf-8')
    # Try to extract the Exception Location from the Django debug page
    import re
    match = re.search(r'Exception Type:.*?<th>Exception Value:</th>\s*<td><pre>(.*?)</pre></td>', body, re.DOTALL)
    if match:
        print("EXCEPTION:", match.group(1))
    else:
        # Just grab the title or h1
        h1 = re.search(r'<h1>(.*?)</h1>', body, re.DOTALL)
        if h1:
            print("TITLE:", h1.group(1).strip())
        else:
            print("Body preview:", body[:500])
