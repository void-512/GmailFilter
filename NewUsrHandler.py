import json
import queue
import logging
import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta

new_usr_queue = queue.Queue()

class NewUsrHandler:
    def __init__(self, instant_update_queue):
        with open("config.json", "r") as f:
            config = json.load(f)

        self.db_path = config["dbPath"]

        months_ago = int(config["defaultStartMonthsAgo"])
        start_dt = datetime.now() - relativedelta(months=months_ago)
        self.defaultStartDate = int(start_dt.timestamp())

        self.instant_update_queue = instant_update_queue
        self.__init_db()

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

    def __insert_new_user(self, bubble_user_id):
        """Insert a new user into the DB."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(
            """
            INSERT OR IGNORE INTO bubble_users 
            (bubble_id, token, expire_date, latest_timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (bubble_user_id, None, 0, self.defaultStartDate)
        )

        conn.commit()
        conn.close()

    def listen_new_usr(self):
        while True:
            try:
                bubble_user_id = new_usr_queue.get()
                logging.info(f"Received new bubble user id: {bubble_user_id}")

                # Insert into database
                self.__insert_new_user(bubble_user_id)

                # Put into shared queue for other components
                self.instant_update_queue.put(bubble_user_id)

            except Exception as e:
                logging.error(f"Error handling new bubble user id {bubble_user_id}: {e}")
                continue
