import re
import json
import base64
import sqlite3
from email.utils import parseaddr
from getMailList import get_gmail_service, list_messages, get_message


# =============================================================
# Load return keywords from JSON
# =============================================================
def load_return_keywords(path="keywords.json"):
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    return_keywords = cfg.get("return_keywords", [])

    if not return_keywords:
        print("⚠️ No return_keywords found in JSON.")
        return None

    # Compile into regex for fast matching
    return re.compile("|".join(re.escape(k) for k in return_keywords), re.IGNORECASE)


# =============================================================
# Extract plain text from Gmail payload
# =============================================================
def extract_text(payload):
    text = ""
    if "parts" in payload:
        for part in payload["parts"]:
            mime = part.get("mimeType", "")
            if mime == "text/plain":
                data = part["body"].get("data")
                if data:
                    text += base64.urlsafe_b64decode(data).decode("utf-8", "ignore") + "\n"
            elif mime.startswith("multipart/"):
                text += extract_text(part)
    else:
        data = payload.get("body", {}).get("data")
        if data:
            text += base64.urlsafe_b64decode(data).decode("utf-8", "ignore")
    return text.strip()


# =============================================================
# Get full plain text (subject + from + snippet + body)
# =============================================================
def get_email_text(service, msg_id):
    msg = get_message(service, msg_id)
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])

    subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "")
    sender  = next((h["value"] for h in headers if h["name"].lower() == "from"), "")
    snippet = msg.get("snippet", "")
    body    = extract_text(payload)

    # return f"{subject}\n{sender}\n{snippet}\n{body}"
    return f"{subject}"


# =============================================================
# Main scanner
# =============================================================
def scan_for_returns(db_path="matches.db", json_path="keywords.json"):
    """
    Re-scan emails. If matching DB entries have order_id AND contain return keywords,
    update DB return_flag = 1.
    """

    # Load return keywords
    return_re = load_return_keywords(json_path)
    if return_re is None:
        return

    # Connect to DB
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Fetch all rows with an order_id (we only want to re-scan matched messages)
    cursor.execute("SELECT id, order_id FROM matched_messages WHERE order_id IS NOT NULL")
    rows = cursor.fetchall()

    if not rows:
        print("⚠️ No stored matched messages found.")
        conn.close()
        return

    service = get_gmail_service()

    updated_count = 0

    for msg_id, order_id in rows:
        try:
            text = get_email_text(service, msg_id)

            # Detect return / refund keywords
            if return_re.search(text):
                cursor.execute(
                    "UPDATE matched_messages SET return_flag = 1 WHERE id = ?",
                    (msg_id,)
                )
                updated_count += 1
            else :
                cursor.execute(
                    "UPDATE matched_messages SET return_flag = 0 WHERE id = ?",
                    (msg_id,)
                )
        except Exception as e:
            print(f"⚠️ Error scanning message {msg_id}: {e}")

    conn.commit()
    conn.close()

    print(f"✅ Completed. Updated {updated_count} messages with return_flag = 1.")


# =============================================================
# Run
# =============================================================
if __name__ == "__main__":
    scan_for_returns()
