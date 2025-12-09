import re
import os
import json
import sqlite3
import logging
from email.utils import parseaddr
from DownStreamSender import send_payload
from concurrent.futures import ThreadPoolExecutor


class Filter:
    def __init__(self):
        self.DEBUG = os.getenv("DEBUG", "0") == "1"

        with open("config.json", "r") as f:
                config = json.load(f)

        self.max_threads = config["maxThreads"]
        self.__create_conn()
        self.include_all_compiled, \
        self.exclude_any_compiled, \
        self.order_id_patterns, \
        self.domain_keywords = self.__load_keywords()
    def __create_conn(self):
        with open("config.json", "r") as f:
            config = json.load(f)
        db_path = "matches.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matched_messages (
                id TEXT PRIMARY KEY,
                subject TEXT,
                order_id TEXT,
                sender TEXT,
                domain TEXT,
                timestamp TEXT
            )
        """)
        conn.commit()
        conn.close()

    def __load_keywords(self):
        with open("config.json", "r") as f:
            config = json.load(f)
        kw_path = config["keywordFile"]

        with open(kw_path, "r", encoding="utf-8") as f:
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

    def __extract_sender_domain(self, sender):
        _, email = parseaddr(sender)
        
        if "@" not in email:
            return ""
        
        # Everything after @
        return email.split("@", 1)[1].lower().strip()

    def __match_by_keywords(self, text):
        if self.exclude_any_compiled and self.exclude_any_compiled.search(text):
            if self.DEBUG:
                logging.info("Excluded by keyword")
            return False

        for _, patterns in self.include_all_compiled.items():
            if not any(p.search(text) for p in patterns):
                if self.DEBUG:
                    logging.info("Excluded by missing keyword in block")
                return False

        return True

    def __insert_match(self, metadata):

        try:
            msg_id = metadata["msg_id"]
            subject = metadata["subject"]
            order_id = metadata["order_id"]
            domain = metadata["domain"]
            sender = metadata["sender"]
            timestamp = metadata["timestamp"]

            with open("config.json", "r") as f:
                config = json.load(f)

            db_path = "matches.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO matched_messages
                (id, subject, order_id, sender, domain, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (msg_id, subject, order_id, sender, domain, timestamp))
            conn.commit()
            conn.close()

        except Exception as e:
            logging.error(f"Error inserting match {msg_id}: {e}")

    def __single_message_matcher(self, msg_detail):

        try:
            if self.DEBUG:
                logging.info("--------------------------------------------")
                logging.info(f"Processing Message ID: {msg_detail['msg_id']}")
                logging.info(f"Subject: {msg_detail['subject']}")
                logging.info(f"Sender: {msg_detail['sender']}")

            # === domain matcher ===
            sender_domain = self.__extract_sender_domain(msg_detail['sender'])
            matched_domain = None
            for word in self.domain_keywords:
                if word in sender_domain:
                    matched_domain = word
                    if self.DEBUG:
                        logging.info(f"Matched domain: {matched_domain}")
                    break

            if matched_domain is None:
                return

            combined_text = f"{msg_detail['subject']}\n{msg_detail['sender']}\n{msg_detail['text']}\n{msg_detail['html']}"
            # keyword filtering
            if self.__match_by_keywords(combined_text):
                if self.DEBUG:
                    logging.info(f"Keyword match found")
                # order ID matcher
                for pat in self.order_id_patterns:
                    match = re.search(pat, combined_text, flags=re.IGNORECASE)
                    if match:
                        if self.DEBUG:
                            logging.info(f"Order ID match found: {match.group(0).strip()}")
                        order_id = match.group(0).strip()
                        
                        send_payload(
                            subject=msg_detail['subject'],
                            sender=msg_detail['sender'],
                            text=msg_detail['text'],
                            html=msg_detail['html'],
                            timestamp=msg_detail['timestamp']
                        )
                        '''
                        self.__insert_match({
                            "msg_id": msg_detail['msg_id'],
                            "subject": msg_detail['subject'],
                            "order_id": order_id,
                            "sender": msg_detail['sender'],
                            "domain": matched_domain,
                            "timestamp": msg_detail['timestamp']
                        })
                        '''
                        
                        break

        except Exception as e:
            logging.error(f"Error in filter_helper with msg_id {msg_detail['msg_id']}: {e}")

    def filter_messages(self, data):

        def worker():
            while True:
                msg = data.get_next()
                if msg is None:
                    return     # no more data
                self.__single_message_matcher(msg)

        try:
            with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                futures = [executor.submit(worker) for _ in range(self.max_threads)]

                # Wait for all threads
                for f in futures:
                    f.result()

            logging.info("Fetching completed")

        except Exception as e:
            logging.error(f"Error in filter_messages: {e}")
