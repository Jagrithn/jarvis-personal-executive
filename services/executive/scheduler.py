"""Durable due records; host must approve creation/resume and call tick explicitly."""
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from workflows import TEMPLATES, _directory, _new_file, _read, _registry

_TERMINAL = {'succeeded', 'failed', 'cancelled', 'interrupted'}
_FIELDS = ('id', 'worker', 'interval', 'state', 'next_due', 'inflight', 'task_id', 'last_error')


class Scheduler:
    """One process owns a data directory. There is deliberately no daemon here.

    create/resume_all are privileged calls: approval must be enforced by caller.
    submit receives a command payload and must return an executive task with id.
    lookup receives a task ID and returns a task or None; unknown tasks block.
    """
    def __init__(self, data):
        self.data = Path(data)
        self.clock = time.time
        self.lock = threading.RLock()
        self.closed = False
        self.conn = sqlite3.connect(':memory:', check_same_thread=False)
        fd = _directory(self.data)
        try:
            try:
                raw = _read(fd, 'schedules.sqlite3')
            except FileNotFoundError:
                raw = None
            if raw is not None:
                self.conn.deserialize(raw)
                if self.conn.execute('PRAGMA user_version').fetchone()[0] != 1:
                    raise ValueError('Unsupported scheduler schema')
            else:
                self.conn.executescript('''PRAGMA user_version=1;
                    CREATE TABLE schedules(id TEXT PRIMARY KEY, worker TEXT NOT NULL,
                        interval INTEGER NOT NULL, state TEXT NOT NULL, next_due REAL NOT NULL,
                        inflight INTEGER NOT NULL DEFAULT 0, task_id TEXT, last_error TEXT);''')
            # Parent restart ends ownership of all previous in-memory tasks.
            self.restart_orphans = {r['id'] for r in self._rows() if r['inflight']}
            self.conn.execute("UPDATE schedules SET state='paused' WHERE state='active'")
            self._save()
        except Exception:
            self.conn.close()
            self.closed = True
            raise
        finally:
            os.close(fd)

    def _check_open(self):
        if self.closed:
            raise RuntimeError('Scheduler is closed')

    def _rows(self):
        return [dict(zip(_FIELDS, row)) for row in self.conn.execute(
            'SELECT ' + ','.join(_FIELDS) + ' FROM schedules ORDER BY id')]

    def _save(self):
        self.conn.commit()
        fd = _directory(self.data)
        staged = '.schedules-' + uuid.uuid4().hex + '.sqlite3'
        try:
            _new_file(fd, staged, self.conn.serialize())
            os.replace(staged, 'schedules.sqlite3', src_dir_fd=fd, dst_dir_fd=fd)
            os.fsync(fd)
        finally:
            try:
                os.unlink(staged, dir_fd=fd)
            except FileNotFoundError:
                pass
            os.close(fd)

    def _validate_worker(self, worker):
        if worker not in TEMPLATES or worker not in {w['name'] for w in _registry(self.data / 'workspace')}:
            raise ValueError('Schedule requires an approved registered fixed worker')

    def create(self, worker, interval):
        with self.lock:
            self._check_open()
            self._validate_worker(worker)
            if type(interval) is not int or not 60 <= interval <= 86400:
                raise ValueError('Schedule interval must be an integer from 60 to 86400 seconds')
            rows = self._rows()
            if sum(r['state'] != 'cancelled' for r in rows) >= 10 or len(rows) >= 1000:
                raise ValueError('Schedule limit: 10 live, 1000 lifetime records')
            schedule_id = str(uuid.uuid4())
            self.conn.execute('INSERT INTO schedules(id,worker,interval,state,next_due) VALUES (?,?,?,?,?)',
                              (schedule_id, worker, interval, 'active', self.clock() + interval))
            self._save()
            return next(r for r in self._rows() if r['id'] == schedule_id)

    def list(self):
        with self.lock:
            self._check_open()
            return self._rows()

    def cancel(self, schedule_id):
        with self.lock:
            self._check_open()
            if not isinstance(schedule_id, str) or schedule_id not in {r['id'] for r in self._rows()}:
                raise ValueError('Unknown schedule ID')
            self.conn.execute("UPDATE schedules SET state='cancelled' WHERE id=?", (schedule_id,))
            self._save()
            return next(r for r in self._rows() if r['id'] == schedule_id)

    def pause_all(self):
        with self.lock:
            self._check_open()
            self.conn.execute("UPDATE schedules SET state='paused' WHERE state='active'")
            self._save()
            return self._rows()

    def resume_all(self):
        with self.lock:
            self._check_open()
            rows = self._rows()
            for row in rows:
                if row['state'] == 'paused':
                    self._validate_worker(row['worker'])
            for row in rows:
                if row['state'] == 'paused':
                    # Only process-restart orphans are cleared. Live paused tasks
                    # retain their inflight marker, preventing overlap on resume.
                    if row['id'] in self.restart_orphans:
                        self.conn.execute('UPDATE schedules SET inflight=0,task_id=NULL WHERE id=?', (row['id'],))
                    self.conn.execute("UPDATE schedules SET state='active',next_due=? WHERE id=?",
                                      (self.clock() + row['interval'], row['id']))
            self._save()
            self.restart_orphans.clear()
            return self._rows()

    def tick(self, submit, lookup):
        with self.lock:
            self._check_open()
            dispatched = []
            now = self.clock()
            for row in self._rows():
                if row['state'] != 'active':
                    continue
                if row['inflight']:
                    task = lookup(row['task_id']) if row['task_id'] else None
                    if task is None or task.get('state') not in _TERMINAL:
                        continue
                    self.conn.execute('UPDATE schedules SET inflight=0,task_id=NULL WHERE id=?', (row['id'],))
                    self._save()
                if row['next_due'] > now:
                    continue
                # Recheck fixed template registration at dispatch time.
                try:
                    self._validate_worker(row['worker'])
                except Exception as error:
                    self.conn.execute("UPDATE schedules SET state='paused',last_error=? WHERE id=?",
                                      (str(error)[:500], row['id']))
                    self._save()
                    continue
                # Reserve durably before external submission. A crash between
                # reservation and task ID persistence never automatically replays.
                self.conn.execute('UPDATE schedules SET inflight=1,task_id=NULL,next_due=?,last_error=NULL WHERE id=?',
                                  (now + row['interval'], row['id']))
                self._save()
                try:
                    task = submit({'command': 'run worker: ' + row['worker']})
                    if not isinstance(task, dict) or not isinstance(task.get('id'), str) or not task['id']:
                        raise ValueError('Submission did not return a task ID')
                except Exception as error:
                    # Ambiguous submission can have queued a task before failing:
                    # block this schedule pending restart/review rather than retry.
                    self.conn.execute("UPDATE schedules SET state='paused',last_error=? WHERE id=?",
                                      (str(error)[:500], row['id']))
                    self._save()
                    dispatched.append({'schedule_id': row['id'], 'error': str(error)[:500]})
                    continue
                self.conn.execute('UPDATE schedules SET task_id=? WHERE id=?', (task['id'], row['id']))
                self._save()
                dispatched.append({'schedule_id': row['id'], 'task_id': task['id']})
            return dispatched

    def verify_persisted(self):
        """Independently read disk state, compare all rows, return record count."""
        with self.lock:
            self._check_open()
            fd = _directory(self.data)
            independent = sqlite3.connect(':memory:')
            try:
                independent.deserialize(_read(fd, 'schedules.sqlite3'))
                if independent.execute('PRAGMA user_version').fetchone()[0] != 1:
                    raise RuntimeError('Scheduler persisted schema mismatch')
                rows = [dict(zip(_FIELDS, row)) for row in independent.execute(
                    'SELECT ' + ','.join(_FIELDS) + ' FROM schedules ORDER BY id')]
                if rows != self._rows():
                    raise RuntimeError('Independent scheduler read-back mismatch')
                return len(rows)
            finally:
                independent.close()
                os.close(fd)

    def close(self):
        with self.lock:
            if not self.closed:
                self.conn.close()
                self.closed = True
