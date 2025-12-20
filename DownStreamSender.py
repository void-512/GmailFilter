import json
import time
import random
import string
import requests
from datetime import datetime, timezone

with open("config.json", "r") as f:
    config = json.load(f)
url = config["downstreamEndpoint"]

def send_payload(subject, sender, current_user, html, text, timestamp):
    CODE_LENGTH = 6
    dt = datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc)
    iso_date = dt.isoformat().replace("+00:00", "Z")

    code = ''.join(random.choice(string.ascii_uppercase) for _ in range(CODE_LENGTH))
    
    formatted_subject = f"<<{current_user}>>||{code}|| {subject}"
    
    payload = [
        {
            "email": {
                "html": html,
                "text": text,
                "textAsHtml": html,
                "subject": formatted_subject,
                "date": iso_date,
            }
        }
    ]
    
    response = requests.post(url, json=payload)

    '''
    with open(f"payload{timestamp}-{int(time.time())}.json", "w") as f:
        json.dump(payload, f, indent=4)
    with open(f"payload{timestamp}-{int(time.time())}.html", "w") as f:
        f.write(html)
    '''

    return response.status_code, response.text
