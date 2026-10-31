#!/usr/bin/env python3
import argparse
import hmac
import json
import os
import queue
import signal
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from adapters import execute, Cancelled
from policy import CAPABILITIES, route, authorize
from store import Store
from verification import verify

TERMINAL = {'succeeded', 'failed', 'cancelled', 'interrupted'}
def now():
    return datetime.now(timezone.utc).isoformat()

class Executive:
    def __init__(self, data, helper, executor=execute, checker=verify):
        data.mkdir(parents=True, exist_ok=True)
        self.root = data / 'workspace'
        self.root.mkdir(exist_ok=True)
        self.helper, self.executor, self.checker = helper, executor, checker
        self.store = Store(data / 'tasks.sqlite3')
        self.tasks = {t['id']: t for t in self.store.all()}
        self.lock = threading.RLock()
        self.queue = queue.Queue()
        self.cancels = {}
        self.paused = False
        self.closing = False
        for task in self.tasks.values():
            if task['state'] not in TERMINAL:
                self.transition(task, 'interrupted', 'Service restarted; task was not replayed')
        self.worker = threading.Thread(target=self.work, daemon=True)
        self.worker.start()

    def transition(self, task, state, message):
        task['state'] = state
        task['updated_at'] = now()
        task['events'].append({'time': now(), 'state': state, 'message': message})
        self.store.save(task)

    def submit(self, body):
        if not isinstance(body, dict) or set(body) - {'command', 'path'}:
            raise ValueError('Expected command and optional path only')
        if not isinstance(body.get('command'), str) or not 0 < len(body['command'].strip()) <= 500:
            raise ValueError('command must be 1–500 characters')
        if 'path' in body and not isinstance(body['path'], str):
            raise ValueError('path must be a string')
        with self.lock:
            if self.paused or self.closing:
                raise ValueError('Dispatch is paused; Resume before submitting work')
            task = {'id': str(uuid.uuid4()), 'command': body['command'], 'capability': None,
                    'scope': {}, 'approval': {}, 'state': 'queued', 'created_at': now(),
                    'updated_at': now(), 'events': [], 'result': None, 'error': None, 'evidence': []}
            self.tasks[task['id']] = task
            try:
                task['capability'] = route(body['command'])
                grant = authorize(self.root, task['capability'], body.get('path'))
                task['approval'] = grant
                task['scope'] = {'paths': grant['paths'], 'network': False}
            except ValueError as error:
                task['error'] = str(error)
                self.transition(task, 'failed', str(error))
                return self.snapshot(task)
            self.cancels[task['id']] = threading.Event()
            self.transition(task, 'queued', 'Scope approved; awaiting execution')
            self.queue.put(task['id'])
            return self.snapshot(task)

    def snapshot(self, value):
        return json.loads(json.dumps(value))

    def cancel(self, task_id):
        with self.lock:
            task = self.tasks[task_id]
            if task['state'] not in TERMINAL:
                self.cancels[task_id].set()
                if task['state'] == 'queued':
                    self.transition(task, 'cancelled', 'Cancelled before execution')
                else:
                    task['events'].append({'time': now(), 'state': task['state'], 'message': 'Cancellation requested; completed effects are retained'})
                    self.store.save(task)
            return self.snapshot(task)

    def stop(self):
        with self.lock:
            self.paused = True
            for key in self.tasks:
                self.cancel(key)
        return {'paused': True}

    def work(self):
        while True:
            key = self.queue.get()
            if key is None:
                return
            with self.lock:
                task = self.tasks[key]
                if task['state'] != 'queued':
                    continue
                event = self.cancels[key]
                self.transition(task, 'running', 'Executing allowlisted adapter')
            try:
                authorize(self.root, task['capability'])
                result = self.executor(task['capability'], self.root, event, self.helper)
                with self.lock:
                    task['result'] = result
                    self.store.save(task)
                evidence = self.checker(task['capability'], result, self.root, event, self.helper)
                with self.lock:
                    task['evidence'] = evidence
                    self.transition(task, 'succeeded', 'Outcome independently verified; any late cancellation cannot undo it')
            except Exception as error:
                with self.lock:
                    task['error'] = str(error)
                    state = 'cancelled' if isinstance(error, Cancelled) else 'failed'
                    self.transition(task, state, str(error))

    def close(self):
        self.closing = True
        self.stop()
        self.queue.put(None)
        self.worker.join(timeout=15)
        if self.worker.is_alive():
            raise RuntimeError('Worker failed to stop')
        self.store.close()

class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, executive, token):
        self.executive, self.token = executive, token
        super().__init__(('127.0.0.1', 0), Handler)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.handle_api(False)

    def do_POST(self):
        self.handle_api(True)

    def handle_api(self, post):
        self.connection.settimeout(5)
        if self.headers.get('Origin') is not None:
            return self.reply(403, {'error': 'Browser origins are not allowed'})
        expected_host = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != expected_host:
            return self.reply(403, {'error': 'Invalid host'})
        if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + self.server.token):
            return self.reply(401, {'error': 'Authentication required'})
        path = urlsplit(self.path).path
        engine = self.server.executive
        try:
            body = {}
            if post:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 <= size <= 4096:
                    return self.reply(413, {'error': 'Request too large'})
                body = json.loads(self.rfile.read(size) or b'{}')
            with engine.lock:
                if not post and path == '/v1/health':
                    result = {'status': 'ok', 'api_version': 1, 'paused': engine.paused}
                elif not post and path == '/v1/capabilities':
                    result = [{'id': k, 'title': v[0], 'commands': v[1]} for k, v in CAPABILITIES.items()]
                elif not post and path == '/v1/tasks':
                    result = sorted(engine.snapshot(list(engine.tasks.values())), key=lambda t: t['created_at'], reverse=True)
                elif post and path == '/v1/tasks':
                    result = engine.submit(body)
                elif path.startswith('/v1/tasks/'):
                    parts = path.split('/')
                    if len(parts) == 4 and not post:
                        result = engine.snapshot(engine.tasks[parts[3]])
                    elif len(parts) == 5 and parts[4] == 'cancel' and post:
                        result = engine.cancel(parts[3])
                    else:
                        raise KeyError(path)
                elif post and path == '/v1/stop-all':
                    result = engine.stop()
                elif post and path == '/v1/resume':
                    engine.paused = False
                    result = {'paused': False}
                elif post and path == '/v1/shutdown':
                    engine.stop()
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    result = {'stopping': True}
                else:
                    raise KeyError(path)
            self.reply(200, result)
        except KeyError:
            self.reply(404, {'error': 'Not found'})
        except (ValueError, TypeError) as error:
            self.reply(400, {'error': str(error)})
        except Exception:
            self.reply(500, {'error': 'Internal service error'})

def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--helper', type=Path, required=True)
    args = parser.parse_args()
    # Token arrives over the private parent pipe, never command line or disk.
    import sys
    token = sys.stdin.readline().strip()
    if len(token) < 32:
        raise SystemExit('Missing private launch token')
    engine = Executive(args.data.absolute(), args.helper)
    server = Server(engine, token)
    def shutdown(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    def watch_parent():
        sys.stdin.read()
        shutdown()
    threading.Thread(target=watch_parent, daemon=True).start()
    print(json.dumps({'port': server.server_port}), flush=True)
    try:
        server.serve_forever(poll_interval=.1)
    finally:
        server.server_close()
        engine.close()

if __name__ == '__main__':
    main()
