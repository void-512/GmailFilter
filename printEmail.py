import base64
from getMailList import get_gmail_service, list_messages

def print_message_details(service, msg_id, print_body=False):
    """Fetch a single message and extract useful info."""
    msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()

    headers = msg['payload'].get('headers', [])
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "(No Subject)")
    sender = next((h['value'] for h in headers if h['name'] == 'From'), "(Unknown Sender)")
    snippet = msg.get('snippet', '')

    # Try to extract plain text body
    body = ''
    payload = msg['payload']
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    break
    else:
        data = payload['body'].get('data')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

    print(f"Message ID: {msg_id}\nFrom: {sender}\nSubject: {subject}\nSnippet: {snippet}\n")

    if print_body:
        print("Body:\n")
        print(body.strip() if body else "(No body text)")
        print("-" * 80)

def display_full_message(service, msg_id):
    """
    Fetch and display all available details of a Gmail message.
    """
    try:
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()

        print("=" * 80)
        print(f"Message ID: {msg.get('id')}")
        print(f"Thread ID: {msg.get('threadId')}")
        print(f"Labels: {', '.join(msg.get('labelIds', []))}")
        print("-" * 80)

        # Extract headers
        headers = msg['payload'].get('headers', [])
        header_map = {h['name']: h['value'] for h in headers}

        print(f"From: {header_map.get('From', '(Unknown)')}")
        print(f"To: {header_map.get('To', '(Unknown)')}")
        print(f"CC: {header_map.get('Cc', '(None)')}")
        print(f"BCC: {header_map.get('Bcc', '(None)')}")
        print(f"Date: {header_map.get('Date', '(No Date)')}")
        print(f"Subject: {header_map.get('Subject', '(No Subject)')}")
        print("-" * 80)
        print(f"Snippet: {msg.get('snippet', '')}")
        print("-" * 80)

        # Decode the body
        def extract_body(payload):
            """Recursively extract plain text body from message parts."""
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        data = part['body'].get('data')
                        if data:
                            return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    elif part['mimeType'].startswith('multipart/'):
                        inner_body = extract_body(part)
                        if inner_body:
                            return inner_body
            else:
                data = payload['body'].get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            return ''

        body = extract_body(msg['payload'])
        print("Body:\n")
        print(body.strip() if body else "(No body text)")
        print("-" * 80)

        # List attachments (if any)
        attachments = []
        def find_attachments(payload):
            if 'parts' in payload:
                for part in payload['parts']:
                    if part.get('filename'):
                        attachments.append({
                            'filename': part['filename'],
                            'mimeType': part.get('mimeType'),
                            'attachmentId': part['body'].get('attachmentId')
                        })
                    if part.get('parts'):
                        find_attachments(part)

        find_attachments(msg['payload'])
        if attachments:
            print("Attachments:")
            for a in attachments:
                print(f"  - {a['filename']} ({a['mimeType']})")
        else:
            print("Attachments: None")

        print("=" * 80 + "\n")

    except Exception as e:
        print(f"An error occurred while displaying message {msg_id}: {e}")

def print_full_message(service):

    messages = list_messages(service)

    if not messages:
        print("No messages found.")
    else:
        print(f"🛒 Fetched {len(messages)} emails:\n")
        for i, msg in enumerate(messages, start=1):
            print_message_details(service, msg['id'])
