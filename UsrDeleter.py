import json
import queue
import logging
import sqlite3

delete_queue = queue.Queue()

class UsrDeleter:
    def __init__(self):
        with open("config.json", "r") as f:
            config = json.load(f)
        self.db_path = config["dbPath"]

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

    def __delete_usr(self, bubble_user_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM bubble_users WHERE bubble_id = ?",
                (bubble_user_id,)
            )
        logging.info(f"Deleted user with bubble_id {bubble_user_id} from database")

    def listen_delete_usr(self):
        while True:
            try:
                bubble_user_id = delete_queue.get()
                logging.info(f"Received delete request for bubble user id: {bubble_user_id}")

                self.__delete_usr(bubble_user_id)

            except queue.Empty:
                continue