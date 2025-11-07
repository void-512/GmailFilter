import base64
from config import KEYWORD_FILE, NUM_MESSAGES
from getMailList import get_gmail_service, list_messages, get_message
from concurrent.futures import ThreadPoolExecutor, as_completed

def load_keywords(file_path=KEYWORD_FILE):
    """Load keywords from a text file (one per line)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            keywords = [line.strip().lower() for line in f if line.strip()]
        return keywords
    except Exception as e:
        print(f"Error in load_keywords: {e}")
        return []

def extract_text_from_payload(payload):
    """Recursively extract all text/plain parts as a single string."""
    text = ""
    if 'parts' in payload:
        for part in payload['parts']:
            mime = part.get('mimeType', '')
            if mime == 'text/plain':
                data = part['body'].get('data')
                if data:
                    text += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore') + "\n"
            elif mime.startswith('multipart/'):
                text += extract_text_from_payload(part)
    else:
        data = payload['body'].get('data')
        if data:
            text += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    return text.strip()

def filter_helper(msg_id, pattern, matching_msg_id):
    try:
        service = get_gmail_service()
        full_msg = get_message(service, msg_id)
        payload = full_msg.get('payload', {})
        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
        snippet = full_msg.get('snippet', '')
        body = extract_text_from_payload(payload)

        combined_text = f"{subject}\n{snippet}\n{body}"

        if pattern.search(combined_text):
            matching_msg_id.append(msg_id)
    except Exception as e:
        print(f"⚠️ Error in filter_helper with msg_id {msg_id}: {e}")



def filter_messages_by_keywords(service, pattern, max_total=NUM_MESSAGES, max_threads=8):
    """
    Multi-threaded Gmail keyword filter using ThreadPoolExecutor.
    Fetches all messages via pagination (list_messages) and scans them in parallel.
    """

    try:
        # Get all message IDs via pagination
        messages = list_messages(service, max_total=max_total)
        print(f"📬 Fetched {len(messages)} messages from Gmail.")

        matching_msg_id = []

        # Use ThreadPoolExecutor to parallelize
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = [executor.submit(filter_helper, msg['id'], pattern, matching_msg_id) for msg in messages]

        return matching_msg_id

    except Exception as e:
        print(f"⚠️ Error in filter_messages_by_keywords: {e}")
        return []