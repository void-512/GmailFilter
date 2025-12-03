import os
import json
import redis
import base64
import threading
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_gmail_service():
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

def get_all_msg_id():
    service = get_gmail_service()
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

class Data:
    def __init__(self):
        self.lock = threading.Lock()
        with open("config.json", "r") as f:
            config = json.load(f)
        self.batchSize = config["numMsgPerBatch"]
        self.maxWorkers = config["maxThreads"]

        self.msg_ids = get_all_msg_id()

        self.msg_id_groups = [
            self.msg_ids[i:i + self.batchSize]
            for i in range(0, len(self.msg_ids), self.batchSize)
        ]
        self.batch_idx = 0
        self.index = 0

        self.keys = ["msg_id", "sender", "subject", "timestamp", "text"]

        self.redis = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
        self.redis.flushdb()

    def __del__(self):
        try:
            self.redis.flushdb()
        except Exception:
            pass

    def _process_msg_thread(self, msg_id):
        """
        Worker function for each thread: fetch message, extract fields, push to Redis.
        """
        service = get_gmail_service()
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])

        self.redis.rpush("msg_id", msg_id)
        self.redis.rpush("sender", next((h["value"] for h in headers if h["name"].lower() == "from"), ""))
        self.redis.rpush("subject", next((h["value"] for h in headers if h["name"].lower() == "subject"), ""))
        self.redis.rpush("timestamp", msg.get("internalDate", ""))
        self.redis.rpush("text", self._get_text(msg))

    def _get_text(self, msg):
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

    def _load_next_batch(self):
        """
        Loads the next batch, processes it, stores it in Redis.
        """
        for k in self.keys:
            self.redis.delete(k)

        if self.batch_idx >= len(self.msg_id_groups):
            return None

        batch = self.msg_id_groups[self.batch_idx]
        self.batch_idx += 1
        self.index = 0

        with ThreadPoolExecutor(max_workers=self.maxWorkers) as executor:
            futures = [executor.submit(self._process_msg_thread, msg_id) for msg_id in batch]
            for f in as_completed(futures):
                f.result()

    def _get_record(self, index):
        return {
            "msg_id": self.redis.lindex("msg_id", index),
            "sender": self.redis.lindex("sender", index),
            "subject": self.redis.lindex("subject", index),
            "timestamp": self.redis.lindex("timestamp", index),
            "text": self.redis.lindex("text", index)
        }

    def get_next(self):
        with self.lock:
            if self.index >= self.redis.llen("msg_id"):
                self._load_next_batch()
                if self.redis.llen("msg_id") == 0:
                    return None
                print(f"Loaded batch {self.batch_idx}/{len(self.msg_id_groups)}")
            record = self._get_record(self.index)
            self.index += 1
            return record