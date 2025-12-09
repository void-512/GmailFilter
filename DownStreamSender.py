import random
import string
import requests
from datetime import datetime, timezone

def send_payload(subject, sender, text, html, timestamp):
    dt = datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc)
    iso_date = dt.isoformat().replace("+00:00", "Z")

    code = ''.join(random.choices(string.ascii_uppercase, k=6))
    
    formatted_subject = f"<<{sender}>>||{code}|| {subject}"
    
    payload = [
        {
            "email": {
                "html": html,
                "text": text,
                "subject": formatted_subject,
                "date": iso_date
            }
        }
    ]
    
    url = "https://clients-shared-101.helixautomation.dev/webhook/garde-robe/process_email"
    response = requests.post(url, json=payload)

    return response.status_code, response.text
