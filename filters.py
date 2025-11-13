import re
import json
import base64
import sqlite3
import threading
from config import KEYWORD_FILE, NUM_MESSAGES
from concurrent.futures import ThreadPoolExecutor, as_completed
from getMailList import get_gmail_service, list_messages, get_message

db_lock = threading.Lock()

def init_db(db_path="matches.db"):
    """Initialize the SQLite database and create the matched_messages table if not exists."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matched_messages (
            id TEXT PRIMARY KEY,
            subject TEXT,
            order_id TEXT,
            timestamp TEXT,
            has_attachment INTEGER,
            text_length INTEGER
        )
    """)
    conn.commit()
    conn.close()

def load_from_json(path=KEYWORD_FILE):
    """
    Load keywords from JSON and compile regex lists for each block.
    Returns: blocks_compiled: dict[name -> list of compiled patterns], exclude_any (compiled or None)
    """
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    include_all_list = cfg.get("include_all_keywords", {})
    include_all_compiled = {}
    for name, keywords in include_all_list.items():
        # compile each keyword as a regex; you can add r"\b...\b" for whole-word matching
        include_all_compiled[name] = [re.compile(re.escape(k), re.IGNORECASE) for k in keywords]

    exclude_any_list = cfg.get("exclude_any_keywords", [])
    exclude_any_compiled = re.compile("|".join(re.escape(k) for k in exclude_any_list), re.IGNORECASE) if exclude_any_list else None

    return include_all_compiled, exclude_any_compiled, cfg.get("order_id_patterns", [])

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

def get_plain_text(msg_id):
    """Fetch the full message and extract plain text content."""
    service = get_gmail_service()
    full_msg = get_message(service, msg_id)
    payload = full_msg.get('payload', {})
    headers = payload.get('headers', [])
    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
    snippet = full_msg.get('snippet', '')
    body = extract_text_from_payload(payload)

    return f"{subject}\n{sender}\n{snippet}\n{body}"


def get_message_metadata(service, msg_id):
    """
    Fetch metadata (subject, timestamp, has_attachment) for a Gmail message.
    Uses Gmail API; 'full' format ensures attachment info is present.
    """
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()

    headers = msg.get("payload", {}).get("headers", [])
    subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "")
    timestamp = msg.get("internalDate", "")
    payload = msg.get("payload", {})

    def _check_parts(part):
        """Recursively search for attachment indicators."""
        if part.get("body", {}).get("attachmentId"):
            return True
        for subpart in part.get("parts", []) or []:
            if _check_parts(subpart):
                return True
        return False

    has_attachment = int(_check_parts(payload))
    if has_attachment:
        print("Attachment found")

    return {
        "subject": subject,
        "timestamp": timestamp,
        "has_attachment": has_attachment,
    }


def insert_match(service, msg_id, order_id, text_length, db_path="matches.db"):
    """
    Thread-safe insert of message data into SQLite.
    Fetches subject, timestamp, and attachment info via Gmail API.
    """
    try:
        metadata = get_message_metadata(service, msg_id)

        subject = metadata["subject"]
        timestamp = metadata["timestamp"]
        has_attachment = metadata["has_attachment"]

        with db_lock:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO matched_messages
                (id, subject, order_id, timestamp, has_attachment, text_length)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (msg_id, subject, order_id, timestamp, has_attachment, text_length))
            conn.commit()
            conn.close()

    except Exception as e:
        print(f"⚠️ Error inserting match {msg_id}: {e}")


def single_message_matcher(msg_id, include_all_compiled, exclude_any_compiled, order_id_patterns, matching_msg_id):
    try:
        service = get_gmail_service()
        combined_text = re.sub(r"[\u200B-\u200D\uFEFF]", "", get_plain_text(msg_id))
        text_length = len(combined_text or "")

        if is_match(combined_text, include_all_compiled, exclude_any_compiled):
            for pat in order_id_patterns:
                regex = re.compile(pat, re.IGNORECASE)
                match = regex.search(combined_text)
                if match:
                    matching_msg_id.append(msg_id)
                    order_id = match.group(0).strip()
                    insert_match(service, msg_id, order_id, text_length)
                    break
    except Exception as e:
        print(f"⚠️ Error in filter_helper with msg_id {msg_id}: {e}")


def filter_messages_by_keywords(service, include_all_compiled, exclude_any_compiled, order_id_patterns, max_total=NUM_MESSAGES, max_threads=8):
    """
    Multi-threaded Gmail keyword filter using ThreadPoolExecutor.
    Fetches all messages via pagination (list_messages) and scans them in parallel.
    """
    init_db()
    try:
        # Get all message IDs via pagination
        messages = list_messages(service, max_total=max_total)
        print(f"📬 Fetched {len(messages)} messages from Gmail.")

        matching_msg_id = []

        # Use ThreadPoolExecutor to parallelize
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = [executor.submit(single_message_matcher, msg['id'], include_all_compiled, exclude_any_compiled, order_id_patterns, matching_msg_id) for msg in messages]

        return matching_msg_id

    except Exception as e:
        print(f"⚠️ Error in filter_messages_by_keywords: {e}")
        return []