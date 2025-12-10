import random
import string
import requests
from datetime import datetime, timezone

def send_payload(subject, sender, current_user, html, timestamp):
    CODE_LENGTH = 6
    dt = datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc)
    iso_date = dt.isoformat().replace("+00:00", "Z")

    code = ''.join(random.choice(string.ascii_uppercase) for _ in range(CODE_LENGTH))
    
    formatted_subject = f"<<{current_user}>>||{code}|| {subject}"
    
    payload = {
        "subject": formatted_subject,
        "date": iso_date,
        "textAsHTML": html,
    }

    print(payload)

    url = "https://clients-shared-101.helixautomation.dev/webhook/garde-robe/process_email"
    response = requests.post(url, json=payload)

    return response.status_code, response.text
