import re
import json
import base64
import sqlite3
import threading
from datetime import datetime
from email.utils import parseaddr
from config import KEYWORD_FILE, NUM_MESSAGES
from concurrent.futures import ThreadPoolExecutor
from getMailList import get_gmail_service, list_messages, get_message

db_lock = threading.Lock()


# ≡============================================================≡
#  DB INIT
# ≡============================================================≡
def init_db(db_path="matches.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matched_messages (
            id TEXT PRIMARY KEY,
            subject TEXT,
            order_id TEXT,
            sender TEXT,
            domain TEXT,
            timestamp TEXT,
            has_attachment INTEGER,
            text_length INTEGER
        )
    """)
    conn.commit()
    conn.close()



# ≡============================================================≡
#  LOAD JSON CONFIG  (uses your original function)
#  — domain section now interpreted as FLAT WORD LIST —
# ≡============================================================≡
def load_from_json(path=KEYWORD_FILE):
    """
    Load keywords from JSON:
       include_all_keywords : dict {block_name: [kw1, kw2...]}
       exclude_any_keywords : [kw1, kw2...]
       domains : FLAT LIST of domain keyword words
       order_id_patterns : [...]
    """
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # --- include_all_keywords ---
    include_all_list = cfg.get("include_all_keywords", {})
    include_all_compiled = {
        name: [re.compile(re.escape(k), re.IGNORECASE) for k in words]
        for name, words in include_all_list.items()
    }

    # --- exclude_any_keywords ---
    exclude_any_list = cfg.get("exclude_any_keywords", [])
    exclude_any_compiled = (
        re.compile("|".join(re.escape(k) for k in exclude_any_list), re.IGNORECASE)
        if exclude_any_list else None
    )

    # --- FLAT domain keywords ---
    domain_keywords = [d.lower() for d in cfg.get("domains", [])]

    # --- order ID patterns ---
    order_id_patterns = cfg.get("order_id_patterns", [])

    return include_all_compiled, exclude_any_compiled, order_id_patterns, domain_keywords



# ≡============================================================≡
#  FILTER: INCLUDE + EXCLUDE
# ≡============================================================≡
def is_match(text, include_all_compiled, exclude_any_compiled=None):

    if exclude_any_compiled and exclude_any_compiled.search(text):
        return False

    for _, patterns in include_all_compiled.items():
        if not any(p.search(text) for p in patterns):
            return False

    return True



# ≡============================================================≡
#  EXTRACT PLAIN TEXT FROM EMAIL PAYLOAD
# ≡============================================================≡
def extract_text_from_payload(payload):
    text = ""
    if "parts" in payload:
        for part in payload["parts"]:
            mime = part.get("mimeType", "")
            if mime == "text/plain":
                data = part["body"].get("data")
                if data:
                    text += base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore") + "\n"
            elif mime.startswith("multipart/"):
                text += extract_text_from_payload(part)
    else:
        data = payload["body"].get("data")
        if data:
            text += base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return text.strip()



# ≡============================================================≡
#  GET SUBJECT + SENDER + SNIPPET + BODY
# ≡============================================================≡
def get_plain_text(msg_id):
    service = get_gmail_service()
    full_msg = get_message(service, msg_id)
    payload = full_msg.get("payload", {})
    headers = payload.get("headers", [])

    subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "")
    sender  = next((h["value"] for h in headers if h["name"].lower() == "from"), "")
    snippet = full_msg.get("snippet", "")
    body = extract_text_from_payload(payload)

    return f"{subject}\n{sender}\n{snippet}\n{body}"



# ≡============================================================≡
#  EXTRACT SENDER DOMAIN (your new logic)
# ≡============================================================≡
def extract_sender_domain(sender):
    """
    Return the entire domain part after '@'
    without modifying or removing TLDs.
    """
    _, email = parseaddr(sender)
    
    if "@" not in email:
        return ""
    
    # Everything after @
    domain = email.split("@", 1)[1].lower().strip()
    
    return domain


# ≡============================================================≡
#  MESSAGE METADATA
# ≡============================================================≡
def get_message_metadata(service, msg_id):
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()

    payload = msg.get("payload", {})
    headers = payload.get("headers", [])

    subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "")
    sender  = next((h["value"] for h in headers if h["name"].lower() == "from"), "")
    timestamp = msg.get("internalDate", "")

    def _check_parts(part):
        if part.get("body", {}).get("attachmentId"):
            return True
        for sub in part.get("parts", []) or []:
            if _check_parts(sub):
                return True
        return False

    has_attachment = int(_check_parts(payload))

    return {
        "subject": subject,
        "sender": sender,
        "timestamp": timestamp,
        "has_attachment": has_attachment,
    }



# ≡============================================================≡
#  INSERT MATCH TO DB
# ≡============================================================≡
def insert_match(service, msg_id, order_id, text_length, domain, db_path="matches.db"):

    try:
        metadata = get_message_metadata(service, msg_id)

        subject = metadata["subject"]
        sender = metadata["sender"]
        timestamp = metadata["timestamp"]
        has_attachment = metadata["has_attachment"]

        with db_lock:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO matched_messages
                (id, subject, order_id, sender, domain, timestamp, has_attachment, text_length)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (msg_id, subject, order_id, sender, domain, timestamp, has_attachment, text_length))
            conn.commit()
            conn.close()

    except Exception as e:
        print(f"⚠️ Error inserting match {msg_id}: {e}")



# ≡============================================================≡
#  MAIN SINGLE MESSAGE FILTER WITH NEW DOMAIN LOGIC
# ≡============================================================≡
def single_message_matcher(msg_id,
                           include_all_compiled,
                           exclude_any_compiled,
                           order_id_patterns,
                           domain_keywords,
                           matching_msg_id):

    try:
        service = get_gmail_service()
        combined_text = get_plain_text(msg_id)
        text_length = len(combined_text or "")

        # extract sender
        full_msg = get_message(service, msg_id)
        headers = full_msg.get("payload", {}).get("headers", [])
        sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "")

        # === NEW DOMAIN LOGIC ===
        sender_domain = extract_sender_domain(sender)

        matched_domain = None
        for word in domain_keywords:
            if word in sender_domain:   # substring match OK
                matched_domain = word
                break

        if matched_domain is None:
            return  # domain failed → skip

        # keyword filtering
        if is_match(combined_text, include_all_compiled, exclude_any_compiled):
            for pat in order_id_patterns:
                match = re.search(pat, combined_text, flags=re.IGNORECASE)
                if match:
                    order_id = match.group(0).strip()
                    matching_msg_id.append(msg_id)
                    insert_match(service, msg_id, order_id, text_length, matched_domain)
                    break

    except Exception as e:
        print(f"⚠️ Error in filter_helper with msg_id {msg_id}: {e}")



# ≡============================================================≡
#  MAIN FILTER FUNCTION
# ≡============================================================≡
def filter_messages_by_keywords(service,
                                include_all_compiled,
                                exclude_any_compiled,
                                order_id_patterns,
                                domain_keywords,
                                max_total=NUM_MESSAGES,
                                max_threads=6):

    init_db()

    try:
        messages = list_messages(service)
        print(f"📬 Fetched {len(messages)} messages from Gmail.")

        matching_msg_id = []

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            for msg in messages:
                executor.submit(
                    single_message_matcher,
                    msg["id"],
                    include_all_compiled,
                    exclude_any_compiled,
                    order_id_patterns,
                    domain_keywords,
                    matching_msg_id
                )

        return matching_msg_id

    except Exception as e:
        print(f"⚠️ Error in filter_messages_by_keywords: {e}")
        return []
