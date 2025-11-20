import os
from config import SCOPES, NUM_MESSAGES
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            try:
                creds = flow.run_local_server(port=8888)
            except Exception:
                print("No Browser")
                auth_url, _ = flow.authorization_url(prompt='consent')
                print("Open browser with following link")
                print(auth_url)
                code = input("Code: ")
                creds = flow.fetch_token(code=code)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

def list_messages(service, user_id='me', before_date="2023/12/31", after_date="2023/01/01"):
    query = f"after:{after_date} before:{before_date}"
    
    all_messages = []
    page_token = None

    while True:
        response = service.users().messages().list(
            userId=user_id,
            q=query,
            maxResults=500,
            pageToken=page_token
        ).execute()

        all_messages.extend(response.get('messages', []))

        page_token = response.get('nextPageToken')
        if not page_token:
            break

    return all_messages


def get_message(service, msg_id, user_id='me', format='full'):
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id, format=format).execute()
        return message
    except Exception as e:
        print(f'⚠️ Error in get_message with msg_id: {msg_id}: {e}')
        return None