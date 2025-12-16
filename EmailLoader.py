import json
import time
import base64
import sqlite3
import threading
import logging
import requests
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from concurrent.futures import ThreadPoolExecutor, as_completed

class Data:
    def __init__(self):
        self.lock = threading.Lock()
        with open("config.json", "r") as f:
            config = json.load(f)
        self.batchSize = config["numMsgPerBatch"]
        self.maxWorkers = config["maxThreads"]
        self.db_path = config["dbPath"]
        self.bubble_user_id = None
        self.token = None
        self.expire_date = None
        self.latest_timestamp = None
        self.current_user = None
        self.records = []
        self.__init_db()

        self.msg_ids = None

        self.msg_id_groups = None
        self.batch_idx = 0
        self.index = 0

    def __init_db(self):
        """Create table if it does not exist."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bubble_users (
                bubble_id TEXT PRIMARY KEY,
                token TEXT,
                expire_date INTEGER,
                latest_timestamp INTEGER
            )
            """
        )

        conn.commit()
        conn.close()

    def reset(self, bubble_user_id):
        """
        Load or refresh token, expire_date, and latest_timestamp for the given bubble user.
        """
        self.bubble_user_id = bubble_user_id

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT token, expire_date, latest_timestamp
                FROM bubble_users
                WHERE bubble_id = ?
                """,
                (self.bubble_user_id,)
            )
            row = cur.fetchone()
        
        self.token, self.expire_date, self.latest_timestamp = row if row else (None, None, None)

        if not self.token or self.expire_date / 1000 < int(time.time()):
            reset_state = self.__get_token()
            if not reset_state:
                logging.error(f"Failed to get token for bubble user id: {self.bubble_user_id}")
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        "DELETE FROM bubble_users WHERE bubble_id = ? OR bubble_id IS NULL",
                        (self.bubble_user_id,)
                    )
                return False

        self.msg_ids = self.__get_all_msg_id()
        self.msg_id_groups = [
            self.msg_ids[i:i + self.batchSize]
            for i in range(0, len(self.msg_ids), self.batchSize)
        ]

        return True

    def __get_token(self):
        url = "https://auth.garde-robe.com/auth/token"
        params = {"bubble_user_id": self.bubble_user_id}

        with open("auth.json", "r") as f:
            auth = json.load(f)
        session = requests.Session()
        session.auth = (auth["auth_endpoint"]["user"], auth["auth_endpoint"]["pwd"])

        try:
            response = session.get(url, params=params, allow_redirects=True)
        except requests.RequestException as e:
            logging.error(f"Network error while requesting token: {e}")
            return False

        if not response.ok:
            logging.error(f"Token request failed with status {response.status_code}: {response.text}")
            return False

        try:
            data = response.json()
        except ValueError:
            logging.error(f"Token endpoint returned invalid JSON: {response.text}")
            return False

        token = data.get("access_token")
        expiry = data.get("expiry_date")

        self.token = token
        self.expire_date = expiry

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE bubble_users
                SET token = ?, expire_date = ?
                WHERE bubble_id = ?
                """,
                (self.token, self.expire_date, self.bubble_user_id)
            )

        if cursor.rowcount == 0:
            logging.info(f"No user found with bubble_id {self.bubble_user_id}, not updating token")
            return False
        
        logging.info(f"Updated token for user {self.bubble_user_id}")

        return True


    def __get_gmail_service(self):
        creds = None

        with open("config.json", "r") as f:
            config = json.load(f)
        SCOPES = [config["scopes"]]

        creds = Credentials(token=self.token, scopes=SCOPES)

        return build('gmail', 'v1', credentials=creds, cache_discovery=False)

    def __get_all_msg_id(self):
        service = self.__get_gmail_service()

        profile = service.users().getProfile(userId="me").execute()
        self.current_user = profile.get("emailAddress")

        start_dt = datetime.utcfromtimestamp(self.latest_timestamp)
        startDate = start_dt.strftime("%Y/%m/%d")
        endDate = datetime.utcnow().strftime("%Y/%m/%d")
        
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

            timestamp = msg.get("internalDate", "")
            if self.latest_timestamp and int(timestamp) >= self.latest_timestamp:
                self.latest_timestamp = int(timestamp)
            
            plain_text, html_text = self.__get_text(msg)

            self.records.append({
                "msg_id": msg_id,
                "current_user": self.current_user,
                "sender": next((h["value"] for h in headers if h["name"].lower() == "from"), ""),
                "subject": next((h["value"] for h in headers if h["name"].lower() == "subject"), ""),
                "timestamp": timestamp,
                "text": plain_text,
                "html": html_text
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

        return msg.get("snippet", "") + "\n" + text.strip(), html.strip()

    def __update_user_timestamp_and_expire(self):
        """Write latest_timestamp and expire_date to database."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE bubble_users
            SET latest_timestamp = ?, expire_date = ?
            WHERE bubble_id = ?
            """,
            (self.latest_timestamp / 1000, self.expire_date, self.bubble_user_id)
        )

        conn.commit()
        conn.close()


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
        
        self.__update_user_timestamp_and_expire()

    def get_next(self):
        with self.lock:
            if self.index >= len(self.records):
                self.__load_next_batch()
                if len(self.records) == 0:
                    return None
                logging.info(f"Loaded batch {self.batch_idx}/{len(self.msg_id_groups)}")
            result = self.records[self.index]
            self.index += 1
            return result