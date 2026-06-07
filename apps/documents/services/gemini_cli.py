import sys
import json
import base64
import os
import django
from pathlib import Path
import requests

# Setup minimal Django environment to get settings
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Missing arguments"}))
        sys.exit(1)

    file_path = sys.argv[1]
    doc_type = sys.argv[2]

    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        print(json.dumps({"error": "Missing GEMINI_API_KEY"}))
        sys.exit(1)

    if doc_type == "business_permit":
        prompt = """
        Extract the following details from this Philippine Business Permit. 
        Return the result strictly as a JSON object with these keys:
        - permit_number
        - business_name
        - registered_owner
        - business_address
        - expiration_date
        - line_of_business

        If a field is not found or unreadable, leave it as an empty string.
        Ensure dates are in YYYY-MM-DD format if possible.
        """
    else:
        prompt = """
        Extract the following details from this market vendor contract document. 
        Return the result strictly as a JSON object with these keys:
        - vendor_name (the person leasing the stall)
        - business_name (if mentioned)
        - stall_number (the stall or booth being leased)
        - lease_start_date
        - lease_end_date
        - monthly_rental_fee

        If a field is not found or unreadable, leave it as an empty string.
        Ensure dates are in YYYY-MM-DD format if possible.
        """

    try:
        with open(file_path, "rb") as f:
            image_bytes = f.read()
    except Exception as e:
        print(json.dumps({"error": f"File read error: {e}"}))
        sys.exit(1)

    b64_image = base64.b64encode(image_bytes).decode('utf-8')
    mime_type = "image/jpeg"
    if file_path.lower().endswith(".png"):
        mime_type = "image/png"

    # Try models in order. 429 = quota exceeded (skip model). 503 = overloaded (retry).
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.0-flash-lite",
        "gemini-flash-latest",
    ]
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": b64_image
                        }
                    },
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    import time

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        print(f"[Gemini] Trying model: {model_name}", file=sys.stderr)
        for attempt in range(3):
            try:
                res = requests.post(url, json=payload, timeout=60)

                if res.status_code == 429:
                    # Quota exceeded for this model — skip immediately
                    print(f"[Gemini] {model_name} quota exceeded, trying next model.", file=sys.stderr)
                    break

                if res.status_code == 503:
                    # Temporarily overloaded — wait and retry same model
                    if attempt < 2:
                        wait = 2 ** attempt
                        print(f"[Gemini] {model_name} overloaded (503), retrying in {wait}s...", file=sys.stderr)
                        time.sleep(wait)
                        continue
                    else:
                        print(f"[Gemini] {model_name} still overloaded, trying next model.", file=sys.stderr)
                        break

                if res.status_code != 200:
                    print(json.dumps({"error": f"Gemini API HTTP Error {res.status_code}: {res.text}"}))
                    sys.exit(1)

                data = res.json()
                try:
                    content_text = data['candidates'][0]['content']['parts'][0]['text']
                    print(content_text)
                    sys.exit(0)
                except (KeyError, IndexError):
                    print(json.dumps({"error": f"Unexpected API response format: {data}"}))
                    sys.exit(1)

            except requests.exceptions.RequestException as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                print(f"[Gemini] {model_name} network error: {e}", file=sys.stderr)
                break

    print(json.dumps({"error": "All Gemini models unavailable. Please try again in a moment."}))
    sys.exit(1)

if __name__ == "__main__":
    main()
