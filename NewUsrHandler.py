import queue
import json
import sqlite3

new_usr_queue = queue.Queue()

class NewUsrHandler:
    def __init__(self, instant_update_queue):
        with open("config.json", "r") as f:
            config = json.load(f)
        self.db_path = config["dbPath"]
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
            (bubble_user_id, None, 1672531200, 1672531200)
        )

        conn.commit()
        conn.close()

    def listen_new_usr(self):
        while True:
            try:
                bubble_user_id = new_usr_queue.get()
                print(f"Processing new bubble user id: {bubble_user_id}")

                # Insert into database
                self.__insert_new_user(bubble_user_id)

                # Put into shared queue for other components
                self.instant_update_queue.put(bubble_user_id)

            except queue.Empty:
                continue
