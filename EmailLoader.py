import os
import json
import base64
import threading
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from concurrent.futures import ThreadPoolExecutor, as_completed

class Data:
    def __init__(self):
        self.lock = threading.Lock()
        with open("config.json", "r") as f:
            config = json.load(f)
        self.batchSize = config["numMsgPerBatch"]
        self.maxWorkers = config["maxThreads"]
        self.records = []

        self.msg_ids = self.__get_all_msg_id()

        self.msg_id_groups = [
            self.msg_ids[i:i + self.batchSize]
            for i in range(0, len(self.msg_ids), self.batchSize)
        ]
        self.batch_idx = 0
        self.index = 0

    def __get_gmail_service(self):
        creds = None

        with open("config.json", "r") as f:
            config = json.load(f)
        SCOPES = [config["scopes"]]
        TOKEN_FILE = config["tokenFile"]
        CREDENTIALS_FILE = config["credentialsFile"]

        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                try:
                    creds = flow.run_local_server(port=8888)
                except Exception:
                    print("No Browser")
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    print("Open browser with following link")
                    print(auth_url)
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

        return build('gmail', 'v1', credentials=creds)

    def __get_all_msg_id(self):
        service = self.__get_gmail_service()
        with open("config.json", "r") as f:
            config = json.load(f)
        startDate = config["startDate"]
        endDate = config["endDate"]
        numWorkers = config["maxThreads"]
        
        query = f"after:{startDate} before:{endDate}"
        
        all_messages = []
        page_token = None

        while True:
            response = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=500,
                pageToken=page_token
            ).execute()

            all_messages.extend(response.get('messages', []))

            page_token = response.get('nextPageToken')
            if not page_token:
                break

        return [msg['id'] for msg in all_messages]

    def __process_msg_thread(self, msg_id_list):
        """
        Worker function for each thread: fetch message, extract fields, push to records.
        """
        service = self.__get_gmail_service()
        for msg_id in msg_id_list:
            msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])

            self.records.append({
                "msg_id": msg_id,
                "sender": next((h["value"] for h in headers if h["name"].lower() == "from"), ""),
                "subject": next((h["value"] for h in headers if h["name"].lower() == "subject"), ""),
                "timestamp": msg.get("internalDate", ""),
                "text": self.__get_text(msg)
            })

    def __get_text(self, msg):
        text = ""
        html = ""

        payload = msg.get("payload", {})

        def process_part(part):
            nonlocal text, html

            mime = part.get("mimeType", "")
            body = part.get("body", {})

            # text/plain
            if mime == "text/plain" and "data" in body:
                decoded = base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="ignore")
                text += decoded + "\n"

            # text/html
            elif mime == "text/html" and "data" in body:
                decoded = base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="ignore")
                html += decoded + "\n"

            # multipart/*
            elif mime.startswith("multipart/") and "parts" in part:
                for sub in part["parts"]:
                    process_part(sub)

        process_part(payload)

        return msg.get("snippet", "") + "\n" + text.strip() + "\n" + html.strip()

    def __load_next_batch(self):
        def chunk_list(lst, n):
            k, m = divmod(len(lst), n)
            return [lst[i*k + min(i, m):(i+1)*k + min(i+1, m)] for i in range(n)]

        self.records = []

        if self.batch_idx >= len(self.msg_id_groups):
            return None

        batch = self.msg_id_groups[self.batch_idx]
        self.batch_idx += 1
        self.index = 0

        groups = chunk_list(batch, self.maxWorkers)

        with ThreadPoolExecutor(max_workers=self.maxWorkers) as executor:
            futures = [
                executor.submit(self.__process_msg_thread, group)
                for group in groups if group
            ]
            for f in as_completed(futures):
                f.result()

    def get_next(self):
        with self.lock:
            if self.index >= len(self.records):
                self.__load_next_batch()
                if len(self.records) == 0:
                    return None
                print(f"Loaded batch {self.batch_idx}/{len(self.msg_id_groups)}")
            result = self.records[self.index]
            self.index += 1
            return result