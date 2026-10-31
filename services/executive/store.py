import json
import sqlite3
import threading

class Store:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        self.db.execute('PRAGMA user_version=1')
        self.db.commit()

    def save(self, task):
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO tasks VALUES (?, ?)', (task['id'], json.dumps(task)))

    def all(self):
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute('SELECT body FROM tasks ORDER BY rowid DESC')]

    def close(self):
        self.db.close()
