import os
import json
import time
import queue
import base64
import sqlite3
import logging
import requests
import watchtower
import threading
from datetime import datetime
from bs4 import BeautifulSoup
from sentinels import Sentinel
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from concurrent.futures import ThreadPoolExecutor, as_completed

END = Sentinel('END')

class Data:
    def __init__(self):
        self.lock = threading.Lock()
        self.DEBUG = os.getenv("DEBUG", "0") == "1"
        with open("config.json", "r") as f:
            config = json.load(f)
        if self.DEBUG:
            debug_cfg = config.get("debug", {})
            self.startDate = debug_cfg.get("startDate")
            self.endDate = debug_cfg.get("endDate")
        self.maxWorkers = 1 if self.DEBUG else config["maxThreads"]
        self.batchSize = config["numMsgPerBatch"]
        self.db_path = config["dbPath"]
        self.filter_type = config["filterType"]
        self.bubble_user_id = None
        self.token = None
        self.expire_date = None
        self.latest_timestamp = None
        self.current_user = None
        self.raw_htmls = queue.Queue(maxsize=self.batchSize)
        self.preprocessed_records = queue.Queue(maxsize=self.batchSize)
        self.__init_db()

        self.all_msg_ids = None
        self.logger = logging.getLogger("DataReset")
        self.logger.addHandler(watchtower.CloudWatchLogHandler(log_group='Fetcher', stream_name='fetcher'))

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

    def get_current_user(self):
        return self.current_user

    def reset(self, bubble_user_id):
        """
        Load or refresh token, expire_date, and latest_timestamp for the given bubble user.
        """
        self.bubble_user_id = bubble_user_id
        self.current_user = None
        self.preprocessed_records = queue.Queue(maxsize=self.batchSize)
        self.raw_htmls = queue.Queue(maxsize=self.batchSize)

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
                self.logger.error(f"Failed to get token for bubble user id: {self.bubble_user_id}")
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        "DELETE FROM bubble_users WHERE bubble_id = ? OR bubble_id IS NULL",
                        (self.bubble_user_id,)
                    )
                return False

        self.all_msg_ids = self.__get_all_msg_id()

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
            self.logger.error(f"Network error while requesting token: {e}")
            return False

        if not response.ok:
            self.logger.error(f"Token request failed with status {response.status_code}: {response.text}")
            return False

        try:
            data = response.json()
        except ValueError:
            self.logger.error(f"Token endpoint returned invalid JSON: {response.text}")
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
            self.logger.info(f"No user found with bubble_id {self.bubble_user_id}, not updating token")
            return False
        
        self.logger.info(f"Updated token for user {self.bubble_user_id}")

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
        
        if self.DEBUG:
            startDate = self.startDate
            endDate = self.endDate
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

    def __get_html(self, msg):
        html = ""

        payload = msg.get("payload", {})

        def process_part(part):
            nonlocal html

            mime = part.get("mimeType", "")
            body = part.get("body", {})

            if mime == "text/html" and "data" in body:
                decoded = base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="ignore")
                html += decoded + "\n"

            elif mime.startswith("multipart/") and "parts" in part:
                for sub in part["parts"]:
                    process_part(sub)

        process_part(payload)

        return html.strip()

    def __get_text(self, msg):
        text = ""

        payload = msg.get("payload", {})

        def process_part(part):
            nonlocal text

            mime = part.get("mimeType", "")
            body = part.get("body", {})

            if mime == "text/plain" and "data" in body:
                decoded = base64.urlsafe_b64decode(body["data"]).decode("utf-8", errors="ignore")
                text += decoded + "\n"

            elif mime.startswith("multipart/") and "parts" in part:
                for sub in part["parts"]:
                    process_part(sub)

        process_part(payload)

        return text.strip()

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

    def __load_msg_thread(self, msg_id_list):
        """
        Worker function for each thread: fetch message, extract fields, push to records.
        """
        service = self.__get_gmail_service()
        for msg_id in msg_id_list:
            retry_count = 0
            while True:
                try:
                    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
                    payload = msg.get("payload", {})
                    headers = payload.get("headers", [])

                    timestamp = msg.get("internalDate", "")
                    with self.lock:
                        if not self.latest_timestamp or int(timestamp) > self.latest_timestamp:
                            self.latest_timestamp = int(timestamp)

                    self.raw_htmls.put({
                        "msg_id": msg_id,
                        "sender": next((h["value"] for h in headers if h["name"].lower() == "from"), ""),
                        "subject": next((h["value"] for h in headers if h["name"].lower() == "subject"), ""),
                        "timestamp": timestamp,
                        "html": self.__get_html(msg),
                        "text": self.__get_text(msg)
                    }, block=True, timeout=None)
                    break
                except Exception as e:
                    self.logger.error(f"Error fetching message {msg_id}: {e}")
                    retry_count += 1
                    if retry_count >= 3:
                        self.logger.error(f"Failed to fetch message {msg_id} after {retry_count} attempts.")
                        break
                    time.sleep(2 ** retry_count)

    def __html_preprocess_thread(self):
        '''
        HTML preprocessor prepared for ML filtering, but given the reliability of the model, using regex instead, so this is currently disabled.
        Raw HTML and text are directly passed to the next stage.
        '''
        while True:
            try:
                raw_data_block = self.raw_htmls.get(block=True, timeout=None)
                if raw_data_block is END:
                    break
                
                if self.filter_type == "regex":
                    self.preprocessed_records.put({
                        "msg_id": raw_data_block["msg_id"],
                        "sender": raw_data_block["sender"],
                        "subject": raw_data_block["subject"],
                        "timestamp": raw_data_block["timestamp"],
                        "html": raw_data_block["html"],
                        "text": raw_data_block["text"]
                    }, block=True, timeout=None)
                
                else:
                    raw_html = raw_data_block["html"]
                    soup = BeautifulSoup(raw_html, "html.parser")
                    for tag in soup(["script", "style"]):
                        tag.decompose()
                    text_in_html = soup.get_text(separator=" ", strip=True)
                    cleaned_html = str(soup)
                    self.preprocessed_records.put({
                        "msg_id": raw_data_block["msg_id"],
                        "sender": raw_data_block["sender"],
                        "subject": raw_data_block["subject"],
                        "timestamp": raw_data_block["timestamp"],
                        "html": raw_html,
                        "text": text_in_html
                    }, block=True, timeout=None)
            
            except Exception as e:
                self.logger.error(f"Error in HTML preprocessing: {e}")

    def __load_raw_msgs(self):
        def chunk_list(lst, n):
            k, m = divmod(len(lst), n)
            return [lst[i*k + min(i, m):(i+1)*k + min(i+1, m)] for i in range(n)]

        groups = chunk_list(self.all_msg_ids, self.maxWorkers)
        
        with ThreadPoolExecutor(max_workers=self.maxWorkers) as executor:
            futures = [
                executor.submit(self.__load_msg_thread, group)
                for group in groups if group
            ]
            for f in as_completed(futures):
                f.result()

        self.__update_user_timestamp_and_expire()

        for _ in range(self.maxWorkers):
            self.raw_htmls.put(END)

    def __html_preprocess(self):
        with ThreadPoolExecutor(max_workers=self.maxWorkers) as executor:
            futures = [
                executor.submit(self.__html_preprocess_thread)
                for _ in range(self.maxWorkers)
            ]
            for f in as_completed(futures):
                result = f.result()
        
        self.preprocessed_records.put(END)

    def start_loading(self):
        raw_loader_thread = threading.Thread(target=self.__load_raw_msgs)
        preprocess_thread = threading.Thread(target=self.__html_preprocess)
        raw_loader_thread.start()
        preprocess_thread.start()
        
    def get_all_bubble_user_ids(self):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT bubble_id FROM bubble_users")
            rows = cur.fetchall()
        return [row[0] for row in rows]

    def get_next(self):
        try:
            record = self.preprocessed_records.get(block=True, timeout=None)
            if record is END:
                self.preprocessed_records.put(END)
                return None
            return record
        except Exception as e:
            self.logger.error(f"Error getting next record: {e}")
            return None