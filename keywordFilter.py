import re
import json
import base64
from config import KEYWORD_FILE, NUM_MESSAGES
from concurrent.futures import ThreadPoolExecutor, as_completed
from getMailList import get_gmail_service, list_messages, get_message

def load_from_json(path=KEYWORD_FILE):
    """
    Load keywords from JSON and compile regex lists for each block.
    Returns: blocks_compiled: dict[name -> list of compiled patterns], exclude_any (compiled or None)
    """
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    include_all_list = cfg.get("include_all", {})
    include_all_compiled = {}
    for name, keywords in include_all_list.items():
        # compile each keyword as a regex; you can add r"\b...\b" for whole-word matching
        include_all_compiled[name] = [re.compile(re.escape(k), re.IGNORECASE) for k in keywords]

    exclude_any_list = cfg.get("exclude_any", [])
    exclude_any_compiled = re.compile("|".join(re.escape(k) for k in exclude_any_list), re.IGNORECASE) if exclude_any_list else None

    return include_all_compiled, exclude_any_compiled

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

def is_match(text, include_all_compiled, exclude_any_compiled=None):
    """
    Returns True iff:
      - text does NOT match any exclude_any pattern (if provided), AND
      - for every block in include_all_compiled, at least one pattern in that block matches text.
    """
    if exclude_any_compiled and exclude_any_compiled.search(text):
        return False

    # For each block: require at least one match
    for include_filter, patterns in include_all_compiled.items():
        if not any(p.search(text) for p in patterns):
            return False

    return True

def filter_helper(msg_id, include_all_compiled, exclude_any_compiled, matching_msg_id):
    try:
        service = get_gmail_service()
        full_msg = get_message(service, msg_id)
        payload = full_msg.get('payload', {})
        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
        snippet = full_msg.get('snippet', '')
        body = extract_text_from_payload(payload)

        combined_text = f"{subject}\n{sender}\n{snippet}\n{body}"

        if is_match(combined_text, include_all_compiled, exclude_any_compiled):
            matching_msg_id.append(msg_id)
    except Exception as e:
        print(f"⚠️ Error in filter_helper with msg_id {msg_id}: {e}")

def filter_messages_by_keywords(service, include_all_compiled, exclude_any_compiled, max_total=NUM_MESSAGES, max_threads=8):
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
            futures = [executor.submit(filter_helper, msg['id'], include_all_compiled, exclude_any_compiled, matching_msg_id) for msg in messages]

        return matching_msg_id

    except Exception as e:
        print(f"⚠️ Error in filter_messages_by_keywords: {e}")
        return []