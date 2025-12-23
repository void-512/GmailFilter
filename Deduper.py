import sqlite3
import threading
import queue
from datetime import datetime
from typing import Iterator
from DownStreamSender import send_payload


class Deduper:
    def __init__(self) -> None:
        self._queue = queue.Queue()
        self._drain_event = threading.Event()
        self._drain_event.set()

        self._worker = threading.Thread(
            target=self._db_worker,
            name="DeduperWorker",
            daemon=True,
        )
        self._worker.start()

    # ============================
    # Public API (UNCHANGED)
    # ============================

    def emplace(
        self,
        subject: str,
        sender: str,
        current_user: str,
        html: str,
        text: str,
        timestamp,
        order_id: str,
    ) -> None:
        self._drain_event.clear()
        self._queue.put((
            "insert",
            subject,
            sender,
            current_user,
            html,
            text,
            timestamp,
            order_id,
        ))

    def dedup(self) -> None:
        self._barrier()
        self._queue.put(("dedup",))
        self._barrier()

    def reset(self) -> None:
        self._barrier()
        self._queue.put(("reset",))
        self._barrier()

    def send(self) -> None:
        self._barrier()
        self._queue.put(("send",))
        self._barrier()

    # ============================
    # Internal synchronization
    # ============================

    def _barrier(self) -> None:
        self._queue.join()
        self._drain_event.wait()

    # ============================
    # Worker thread (SQLite owner)
    # ============================

    def _db_worker(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        self._create_schema(conn)

        while True:
            item = self._queue.get()
            try:
                op = item[0]

                if op == "insert":
                    self._handle_insert(conn, *item[1:])
                elif op == "dedup":
                    self._handle_dedup(conn)
                elif op == "reset":
                    self._handle_reset(conn)
                elif op == "send":
                    self._handle_send(conn)

            finally:
                self._queue.task_done()
                if self._queue.empty():
                    self._drain_event.set()

    # ============================
    # DB operations (single thread)
    # ============================

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                subject TEXT NOT NULL,
                sender TEXT NOT NULL,
                current_user TEXT NOT NULL,
                html TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                order_id TEXT NOT NULL
            )
            """
        )
        conn.commit()

    def _handle_insert(
        self,
        conn: sqlite3.Connection,
        subject: str,
        sender: str,
        current_user: str,
        html: str,
        text: str,
        timestamp,
        order_id: str,
    ) -> None:
        # Normalize timestamp safely
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat(sep=" ")

        conn.execute(
            """
            INSERT INTO messages (
                subject,
                sender,
                current_user,
                html,
                text,
                timestamp,
                order_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subject,
                sender,
                current_user,
                html,
                text,
                timestamp,
                order_id,
            ),
        )
        conn.commit()

    def _handle_dedup(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            DELETE FROM messages
            WHERE rowid NOT IN (
                SELECT rowid
                FROM messages
                GROUP BY order_id
                HAVING MIN(timestamp)
            )
            """
        )
        conn.commit()

    def _handle_reset(self, conn: sqlite3.Connection) -> None:
        conn.execute("DELETE FROM messages")
        conn.commit()

    def _handle_send(self, conn: sqlite3.Connection) -> None:
        cursor = conn.execute(
            """
            SELECT
                subject,
                sender,
                current_user,
                html,
                text,
                timestamp
            FROM messages
            ORDER BY timestamp ASC
            """
        )

        for row in cursor:
            send_payload(
                row["subject"],
                row["sender"],
                row["current_user"],
                row["html"],
                row["text"],
                row["timestamp"],
            )
