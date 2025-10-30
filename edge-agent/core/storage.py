"""
Local buffer storage for UER events (SQLite backend).
"""
import sqlite3
import json
import threading
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SqliteBuffer:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.execute(
                """CREATE TABLE IF NOT EXISTS queue 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 uer TEXT NOT NULL, 
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS dlq 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 uer TEXT NOT NULL, 
                 reason TEXT, 
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
            )
            conn.execute(
                """CREATE INDEX IF NOT EXISTS idx_queue_created 
                ON queue(created_at)"""
            )
            conn.commit()
            conn.close()

    def enqueue(self, uer: dict):
        """Add UER to queue."""
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.execute("INSERT INTO queue (uer) VALUES (?)", (json.dumps(uer),))
            conn.commit()
            conn.close()
        logger.debug(f"Enqueued UER: {uer.get('uid', 'no-uid')}")

    def dequeue_batch(self, n: int = 500) -> List[dict]:
        """Retrieve batch of UERs from queue."""
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            cursor = conn.execute(
                "SELECT id, uer FROM queue ORDER BY id ASC LIMIT ?", (n,)
            )
            rows = cursor.fetchall()
            ids = [row[0] for row in rows]
            uers = [json.loads(row[1]) for row in rows]

            if ids:
                placeholders = ",".join("?" * len(ids))
                conn.execute(f"DELETE FROM queue WHERE id IN ({placeholders})", ids)
                conn.commit()
            conn.close()

        logger.debug(f"Dequeued {len(uers)} UERs")
        return uers

    def dead_letter(self, uer: dict, reason: str):
        """Move UER to dead letter queue."""
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.execute("INSERT INTO dlq (uer, reason) VALUES (?, ?)", (json.dumps(uer), reason))
            conn.commit()
            conn.close()
        logger.warning(f"DLQ: {reason} - {uer.get('uid', 'no-uid')}")

    def get_queue_size(self) -> int:
        """Get current queue size."""
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            cursor = conn.execute("SELECT COUNT(*) FROM queue")
            size = cursor.fetchone()[0]
            conn.close()
        return size

    def get_dlq_size(self) -> int:
        """Get current DLQ size."""
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            cursor = conn.execute("SELECT COUNT(*) FROM dlq")
            size = cursor.fetchone()[0]
            conn.close()
        return size

    def clear_dlq(self):
        """Clear dead letter queue (use with caution)."""
        with self.lock:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.execute("DELETE FROM dlq")
            conn.commit()
            conn.close()

