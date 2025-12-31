import re
import os
import json
import time
import base64
import joblib
import sqlite3
import logging
import watchtower
from email.utils import parseaddr
from DownStreamSender import send_payload
from concurrent.futures import ThreadPoolExecutor

class Filter:
    def __init__(self):
        self.DEBUG = os.getenv("DEBUG", "0") == "1"

        with open("config.json", "r") as f:
                config = json.load(f)

        self.maxWorkers = 1 if self.DEBUG else config["maxThreads"]
        self.filter_type = config["filterType"]
        self.include_all_compiled, \
        self.exclude_any_compiled, \
        self.order_id_patterns, \
        self.domain_keywords = self.__load_keywords() if self.filter_type == "regex" else (None, None, None, None)
        self.current_user = None
        self.update_type = None
        self.full_update_magic_string = None
        self.logger = logging.getLogger("Filters")
        self.logger.addHandler(watchtower.CloudWatchLogHandler(log_group='Fetcher', stream_name='fetcher'))
        if self.filter_type == "ml":
            self.model = joblib.load(config["mlFilter"]["modelName"])
            self.threshold = config["mlFilter"]["threshold"]
        self.fetch_count = 0

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
    
    def __acquire_magic_string(self):
        return base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8').rstrip('=')

    def __single_message_matcher(self, msg_detail):
        combined_text = f"{msg_detail['subject']}\n{msg_detail['sender']}\n{msg_detail['text']}\n{msg_detail['html']}" if self.filter_type == "regex" else None
        try:
            match_flag = False
            if self.DEBUG:
                logging.info("--------------------------------------------")
                logging.info(f"Processing Message ID: {msg_detail['msg_id']}")
                logging.info(f"Timestamp: {msg_detail['timestamp']}")
                logging.info(f"Subject: {msg_detail['subject']}")
                logging.info(f"Sender: {msg_detail['sender']}")
                os.makedirs("debug", exist_ok=True)
                with open(f"debug/combined_text{msg_detail['timestamp']}.txt", "w") as f:
                    f.write(combined_text)

            if self.filter_type == "regex":
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
                            match_flag = True
                            break

            elif self.filter_type == "ml":
                prob = self.model.predict_proba([msg_detail['text']])[0][1]
                if prob > self.threshold:
                    match_flag = True

            else:
                raise ValueError(f"Unknown filter type: {self.filter_type}")
            
            if match_flag:
                self.fetch_count += 1
                magic_string = self.full_update_magic_string if self.update_type == "full" else self.__acquire_magic_string()
                send_payload(
                            subject=msg_detail['subject'],
                            sender=msg_detail['sender'],
                            current_user=self.current_user,
                            html=msg_detail['html'],
                            text=msg_detail['text'],
                            timestamp=msg_detail['timestamp'],
                            magic_string=magic_string
                        )

        except Exception as e:
            self.logger.error(f"Error in filter_helper with msg_id {msg_detail['msg_id']}: {e}")

    def filter_messages(self, data, update_type):
        self.logger = logging.getLogger("Filters")
        self.logger.addHandler(watchtower.CloudWatchLogHandler(log_group='Fetcher', stream_name='fetcher'))
        self.current_user = data.get_current_user()
        self.update_type = update_type
        self.fetch_count = 0

        def worker():
            while True:
                msg = data.get_next()
                if msg is None:
                    return
                self.__single_message_matcher(msg)

        try:
            start_time = time.monotonic()
            with ThreadPoolExecutor(max_workers=self.maxWorkers) as executor:
                futures = [executor.submit(worker) for _ in range(self.maxWorkers)]

                for f in futures:
                    f.result()

            elapsed_minutes = (time.monotonic() - start_time) / 60.0
            self.logger.info(f"Fetching completed in {elapsed_minutes:.2f} minutes")
            self.logger.info(f"Total matched messages fetched: {self.fetch_count}")

        except Exception as e:
            self.logger.error(f"Error in filter_messages: {e}")