import os
import sqlite3
import base64
from datetime import datetime
from getMailList import get_gmail_service, get_message


# ============================================================
#  TIMESTAMP CONVERSION (ms → readable)
# ============================================================
def format_timestamp(ms_timestamp):
    """
    Gmail internalDate is milliseconds since epoch.
    Convert to: YYYY-MM-DD_HH-MM-SS
    """
    try:
        ts = int(ms_timestamp) / 1000
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d_%H-%M-%S")
    except:
        return ms_timestamp  # fallback


# ============================================================
#  HELPER: Extract HTML
# ============================================================
def extract_html_from_payload(payload):
    html = ""

    if "parts" in payload:
        for part in payload["parts"]:
            mime = part.get("mimeType", "")
            body = part.get("body", {})

            if mime == "text/html" and "data" in body:
                html += base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="ignore") + "\n"

            elif mime.startswith("multipart/"):
                html += extract_html_from_payload(part)

    else:
        mime = payload.get("mimeType", "")
        body = payload.get("body", {})

        if mime == "text/html" and "data" in body:
            html = base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="ignore")

    return html.strip()



# ============================================================
#  HELPER: Extract attachments
# ============================================================
def extract_attachments(service, msg_id, payload):
    attachments = []

    def walk(part):
        body = part.get("body", {})

        if "attachmentId" in body:
            att_id = body["attachmentId"]
            filename = part.get("filename", "file")
            mime = part.get("mimeType", "application/octet-stream")

            att_obj = service.users().messages().attachments().get(
                userId="me", messageId=msg_id, id=att_id
            ).execute()

            file_bytes = base64.urlsafe_b64decode(att_obj["data"])

            attachments.append((filename, file_bytes, mime))

        for p in part.get("parts", []) or []:
            walk(p)

    walk(payload)
    return attachments



# ============================================================
#  MAIN EXPORT FUNCTION
# ============================================================
def export_from_db(db_path="matches.db"):
    os.makedirs("html", exist_ok=True)
    os.makedirs("attachments", exist_ok=True)

    service = get_gmail_service()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT id, timestamp FROM matched_messages")
    rows = cursor.fetchall()
    conn.close()

    print(f"Found {len(rows)} matched messages in database.")

    for msg_id, ms_timestamp in rows:
        try:
            readable_ts = format_timestamp(ms_timestamp)
            print(f"Processing {msg_id} → {readable_ts}")

            full_msg = get_message(service, msg_id)
            payload = full_msg.get("payload", {})

            # === HTML export ===
            html_body = extract_html_from_payload(payload)
            if html_body:
                html_path = os.path.join("html", f"{readable_ts}.html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_body)
                print(f"  ✓ HTML saved: {html_path}")

            # === Attachment export ===
            attachments = extract_attachments(service, msg_id, payload)

            for filename, data, mime in attachments:
                safe_name = filename.replace("/", "_").replace("\\", "_")
                att_path = os.path.join("attachments", f"{readable_ts}_{safe_name}")

                with open(att_path, "wb") as f:
                    f.write(data)

                print(f"  ✓ Attachment saved: {att_path}")

        except Exception as e:
            print(f"⚠️ Error processing message {msg_id}: {e}")


# ============================================================
#  RUN
# ============================================================
if __name__ == "__main__":
    export_from_db()

