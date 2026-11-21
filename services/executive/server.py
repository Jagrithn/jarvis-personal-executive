#!/usr/bin/env python3
import argparse
import hmac
import json
import os
import queue
import re
import signal
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from adapters import execute, Cancelled
from policy import CAPABILITIES, APPROVALS, route, authorize
from store import Store
from scheduler import Scheduler
from verification import verify
from reasoning import LocalReasoner
from knowledge import execute_knowledge, verify_knowledge

TERMINAL = {'succeeded', 'failed', 'cancelled', 'interrupted'}
def now():
    return datetime.now(timezone.utc).isoformat()

class Executive:
    def __init__(self, data, helper, executor=execute, checker=verify, reasoner=None):
        data.mkdir(parents=True, exist_ok=True)
        self.root = data / 'workspace'
        self.root.mkdir(exist_ok=True)
        self.helper, self.executor, self.checker = helper, executor, checker
        self.reasoner = reasoner or LocalReasoner(data)
        self.native_agent = reasoner is None
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
        self.scheduler = Scheduler(data)
        self.scheduler_error = None
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
                    'updated_at': now(), 'events': [], 'result': None, 'error': None, 'evidence': [],
                    'requested_path': body.get('path'), 'proposal': None}
            self.tasks[task['id']] = task
            try:
                try:
                    task['capability'] = route(body['command'], general_conversation=self.native_agent)
                except ValueError:
                    if not self.reasoner.enabled:
                        raise
                    # Validate requested path before passing intent to local inference.
                    authorize(self.root, 'files.list', body.get('path'))
                    self.cancels[task['id']] = threading.Event()
                    self.transition(task, 'queued', 'Awaiting local interpretation; no action authorized')
                    self.queue.put(task['id'])
                    return self.snapshot(task)
                grant = authorize(self.root, task['capability'], body.get('path'))
                task['approval'] = grant
                task['scope'] = {'paths': grant['paths'], 'network': grant['network']}
                if task['capability'].startswith('memory.'):
                    from knowledge import memory_folder
                    task['scope']['paths'] = [memory_folder(self.root) or str(self.root)]
                    task['approval']['paths'] = task['scope']['paths']
            except ValueError as error:
                task['error'] = str(error)
                self.transition(task, 'failed', str(error))
                return self.snapshot(task)
            self.cancels[task['id']] = threading.Event()
            if task['capability'] in APPROVALS:
                task['approval'] = {'kind': 'pending', 'source': APPROVALS[task['capability']]}
                self.transition(task, 'awaiting_approval', APPROVALS[task['capability']])
                return self.snapshot(task)
            self.transition(task, 'queued', 'Scope approved; awaiting execution')
            self.queue.put(task['id'])
            return self.snapshot(task)

    def snapshot(self, value):
        return json.loads(json.dumps(value))

    def change_memory_folder(self, body):
        from knowledge import set_memory_folder
        if not isinstance(body, dict) or set(body) != {'path'} or not isinstance(body['path'], str):
            raise ValueError('Expected a folder path.')
        with self.lock:
            if any(task['state'] not in TERMINAL for task in self.tasks.values()):
                raise ValueError('Finish or cancel active tasks before changing the memory folder.')
            return set_memory_folder(self.root, body['path'])

    def cancel(self, task_id):
        with self.lock:
            task = self.tasks[task_id]
            if task['state'] not in TERMINAL:
                self.cancels[task_id].set()
                if task['state'] in {'queued', 'awaiting_approval'}:
                    self.transition(task, 'cancelled', 'Cancelled before execution')
                else:
                    task['events'].append({'time': now(), 'state': task['state'], 'message': 'Cancellation requested; completed effects are retained'})
                    self.store.save(task)
            return self.snapshot(task)

    def approve(self, task_id):
        with self.lock:
            task = self.tasks[task_id]
            if self.paused or self.closing:
                raise ValueError('Dispatch is paused')
            if task['state'] != 'awaiting_approval':
                raise ValueError('Task is not awaiting approval')
            grant = authorize(self.root, task['capability'], task.get('requested_path'))
            if task['capability'].startswith('memory.'):
                from knowledge import memory_folder
                grant['paths'] = [memory_folder(self.root) or str(self.root)]
            grant['source'] = 'owner confirmed: ' + APPROVALS.get(task['capability'], 'local model proposal')
            task['approval'] = grant
            self.transition(task, 'queued', 'Owner confirmed scoped action')
            self.queue.put(task_id)
            return self.snapshot(task)

    def stop(self):
        with self.lock:
            self.paused = True
            for key in self.tasks:
                self.cancel(key)
            try:
                self.scheduler.pause_all()
            except Exception as error:
                self.scheduler_error = 'Could not persist schedule pause: ' + str(error)
        return {'paused': True}

    def work(self):
        while True:
            try:
                key = self.queue.get(timeout=.5)
            except queue.Empty:
                with self.lock:
                    if not self.paused and not self.closing:
                        try:
                            self.scheduler.tick(self.submit, self.tasks.get)
                            self.scheduler_error = None
                        except Exception as error:
                            self.scheduler_error = str(error)
                continue
            if key is None:
                return
            with self.lock:
                task = self.tasks[key]
                if task['state'] != 'queued':
                    continue
                event = self.cancels[key]
                self.transition(task, 'running', 'Interpreting locally' if task['capability'] is None else 'Executing allowlisted adapter')
            try:
                if task['capability'] is None:
                    proposal = self.reasoner.propose(task['command'], event)
                    with self.lock:
                        task['proposal'] = proposal
                        if event.is_set():
                            raise Cancelled('Cancelled during interpretation; no action executed')
                        if proposal['capability'] == 'none':
                            raise ValueError('Cannot safely determine a supported action: ' + proposal['reason'])
                        grant = authorize(self.root, proposal['capability'], task.get('requested_path'))
                        task['capability'] = proposal['capability']
                        task['scope'] = {'paths': grant['paths'], 'network': grant['network']}
                        task['approval'] = {'kind': 'pending', 'source': 'model proposal requires owner confirmation'}
                        self.transition(task, 'awaiting_approval', 'Proposed ' + CAPABILITIES[task['capability']][0] + '; confirm before execution')
                    continue
                authorize(self.root, task['capability'], task.get('requested_path'))
                knowledge = task['capability'].startswith(('chat.', 'memory.'))
                if task['capability'] == 'mac.items':
                    from mac_items import perform
                    with self.lock:
                        previous = sorted((old for old in self.tasks.values()
                                           if old['id'] != task['id'] and old['command'] == task['command']
                                           and old['capability'] == 'mac.items' and old['state'] == 'succeeded'
                                           and isinstance(old.get('result'), dict)
                                           and old['result'].get('outcome') == 'opened'
                                           and old.get('evidence')), key=lambda old: old['created_at'])
                        remembered = previous[-1]['result'].get('opened') if previous else None
                    result = perform(task['command'], event, self.helper, remembered=remembered)
                    checker = lambda: [{'check':'macOS open callback', **item} for item in result['opened']] or [{'check':'search results', 'count':len(result['matches'])}]
                elif task['capability'] == 'agent.plan':
                    from agent import ALLOWED
                    actions = task['proposal']['actions']
                    if not isinstance(actions, list) or not 1 <= len(actions) <= 4 or any(a not in ALLOWED for a in actions):
                        raise ValueError('Invalid action plan')
                    result = {'steps': []}
                    evidence = []
                    for action in actions:
                        if event.is_set():
                            raise Cancelled('Plan cancelled; completed effects remain in task history')
                        authorize(self.root, action, task.get('requested_path'))
                        outcome = self.executor(action, self.root, event, self.helper)
                        with self.lock:
                            result['steps'].append({'capability':action, 'result':outcome})
                            task['result'] = result
                            self.store.save(task)
                        evidence.extend(self.checker(action, outcome, self.root, event, self.helper))
                        with self.lock:
                            task['evidence'] = list(evidence)
                            self.transition(task, 'running', 'Verified ' + action)
                    checker = lambda: evidence
                elif task['capability'].startswith('schedules.'):
                    with self.lock:
                        if event.is_set():
                            raise Cancelled('Schedule action cancelled')
                        result = self.schedule_action(task['capability'], task['command'])
                    checker = lambda: [{'check': 'scheduler persisted state read-back', 'records': self.scheduler.verify_persisted()}]
                elif task['capability'] == 'coding.build':
                    from coding import execute_coding, verify_coding
                    result = execute_coding(task['capability'], task['command'], self.root, event)
                    checker = lambda: verify_coding(task['capability'], result, self.root)
                elif task['capability'] == 'workflows.research':
                    from browser import research_chrome, research_articles, verify_browser
                    from workflows import research_report_topic, save_research_report, verify_research_report
                    topic = research_report_topic(task['command'])
                    if not topic:
                        raise ValueError('Expected: research TOPIC and save a report')
                    page, search_receipts = research_chrome('research ' + topic, event, self.helper)
                    articles = research_articles(page, self.root, event)
                    excerpts = '\n\n'.join('Source: ' + a['source_url'] + '\n' + a['text'][:3500] for a in articles)
                    summary = execute_knowledge('browser.article_summary', excerpts, self.root, event)['answer']
                    result = save_research_report(topic, summary, articles, self.root, event)
                    checker = lambda: (search_receipts +
                                       [receipt for article in articles for receipt in verify_browser('browser.read', article, self.root)] +
                                       verify_research_report(result, self.root))
                elif task['capability'] in {'browser.results', 'browser.research'}:
                    from browser import read_chrome_results, research_chrome, research_articles, verify_browser
                    import hashlib
                    if task['capability'] == 'browser.research':
                        page, search_receipts = research_chrome(task['command'], event, self.helper)
                    else:
                        page, search_receipts = read_chrome_results(event), []
                    if task['capability'] == 'browser.research':
                        articles = research_articles(page, self.root, event)
                        excerpts = '\n\n'.join('Source: ' + a['source_url'] + '\n' + a['text'][:3500] for a in articles)
                        result = execute_knowledge('browser.article_summary', excerpts, self.root, event)
                        result['sources'] = [a['source_url'] for a in articles]
                        result['notice'] = 'Summary of retrieved article text; facts are not independently verified.'
                        checker = lambda: search_receipts + [item for article in articles for item in verify_browser('browser.read', article, self.root)]
                    else:
                        result = execute_knowledge('browser.summary', page['text'], self.root, event)
                        result['sources'] = [page['url']]
                        result['notice'] = 'Summary of Google search snippets. Linked articles were not read; facts are not independently verified.'
                        checker = lambda: search_receipts + [{'check': 'Chrome visible search text captured', 'source_url': page['url'], 'sha256': hashlib.sha256(page['text'].encode()).hexdigest(), 'factual_accuracy_verified': False}]
                elif task['capability'] == 'browser.search':
                    from browser import search_chrome
                    result, receipts = search_chrome(task['command'], event, self.helper)
                    checker = lambda: receipts
                elif task['capability'] == 'browser.read':
                    from browser import execute_browser, verify_browser
                    result = execute_browser(task['capability'], task['command'], self.root, event)
                    checker = lambda: verify_browser(task['capability'], result, self.root)
                elif task['capability'].startswith(('workflows.', 'workers.')):
                    from workflows import execute_workflow, verify_workflow
                    result = execute_workflow(task['capability'], task['command'], self.root, event)
                    checker = lambda: verify_workflow(task['capability'], result, self.root)
                else:
                    execution_started = time.monotonic()
                    result = (execute_knowledge(task['capability'], task['command'], self.root, event,
                                                history=self.chat_history(task['id']) if task['capability'] == 'chat.local' else None)
                              if knowledge else self.executor(task['capability'], self.root, event, self.helper))
                    if knowledge:
                        with self.lock:
                            self.transition(task, 'running', f'Local execution finished in {time.monotonic() - execution_started:.2f}s; verifying result')
                    checker = lambda: (verify_knowledge(task['capability'], result, self.root) if knowledge
                                       else self.checker(task['capability'], result, self.root, event, self.helper))
                if task['capability'] == 'chat.local' and result.get('actions'):
                    from agent import ALLOWED
                    actions = result['actions']
                    if not isinstance(actions, list) or not 1 <= len(actions) <= 4 or any(a not in ALLOWED for a in actions):
                        raise ValueError('Invalid proposed actions')
                    with self.lock:
                        if event.is_set():
                            raise Cancelled('Cancelled before plan approval')
                        task['proposal'] = {'capability':'agent.plan', 'actions': actions, 'reason':'Approve in order: ' + ', '.join(actions)}
                        task['capability'] = 'agent.plan'
                        task['approval'] = {'kind':'pending', 'source':'Approve in order: ' + ', '.join(actions)}
                        self.transition(task, 'awaiting_approval', task['approval']['source'])
                    continue
                with self.lock:
                    if task['capability'] not in {'memory.answer', 'memory.search'}:
                        task['result'] = result
                        self.store.save(task)
                verification_started = time.monotonic()
                evidence = checker()
                if knowledge:
                    with self.lock:
                        self.transition(task, 'running', f'Result verified in {time.monotonic() - verification_started:.2f}s')
                with self.lock:
                    task['result'] = result
                    task['evidence'] = evidence
                    if task['capability'] == 'mac.items' and result.get('outcome') in {'needs_clarification', 'not_found'}:
                        task['error'] = result['message'] + ' Nothing was opened.'
                        self.transition(task, 'failed', task['error'])
                    else:
                        message = ('macOS accepted the open request; opened items may remain open.' if task['capability'] == 'mac.items' and result.get('opened')
                                   else 'Search completed; nothing opened.' if task['capability'] == 'mac.items'
                                   else 'Response received; AI factual accuracy is not verified' if 'answer' in result
                                   else 'Outcome independently verified; any late cancellation cannot undo it')
                        self.transition(task, 'succeeded', message)
            except Exception as error:
                with self.lock:
                    task['error'] = str(error)
                    if task['capability'] in {'memory.answer', 'memory.search'} and task['result'] is not None:
                        task['result'] = None
                        task['events'].append({'time': now(), 'state': 'failed', 'message': 'Rejected retrieval content withheld from output'})
                    state = 'cancelled' if isinstance(error, Cancelled) else 'failed'
                    self.transition(task, state, str(error))

    def chat_history(self, current_id):
        with self.lock:
            current = self.tasks[current_id]
            prior = sorted((t for t in self.tasks.values() if t['id'] != current_id
                            and t['created_at'] < current['created_at'] and t['state'] == 'succeeded'
                            and t['capability'] == 'chat.local' and isinstance(t.get('result'), dict)
                            and t['result'].get('conversation_version') == (2 if self.native_agent else 1)
                            and isinstance(t['result'].get('answer'), str)), key=lambda t: t['created_at'])[-3:]
            messages = []
            for task in prior:
                messages.extend([{'role': 'user', 'content': task['command'][:2000]},
                                 {'role': 'assistant', 'content': task['result']['answer'][:2000]}])
            return messages

    def schedule_action(self, capability, command):
        if capability == 'schedules.create':
            match = re.fullmatch(r'schedule worker:\s*([a-z-]+) every ([0-9]+)', command.strip(), re.IGNORECASE)
            if not match:
                raise ValueError('Use schedule worker: research-reporter every 3600 (seconds)')
            return {'schedule': self.scheduler.create(match[1].lower(), int(match[2]))}
        if capability == 'schedules.cancel':
            record = self.scheduler.cancel(command.split(':', 1)[1].strip())
            if record['task_id'] in self.tasks:
                self.cancel(record['task_id'])
            return {'schedule': record}
        if capability == 'schedules.resume':
            return {'schedules': self.scheduler.resume_all()}
        return {'schedules': self.scheduler.list(), 'error': self.scheduler_error}

    def close(self):
        self.closing = True
        self.stop()
        self.queue.put(None)
        self.worker.join(timeout=15)
        if self.worker.is_alive():
            raise RuntimeError('Worker failed to stop')
        self.scheduler.close()
        self.reasoner.close()
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
                    result = {'status': 'ok', 'api_version': 1, 'paused': engine.paused, 'scheduler_error': engine.scheduler_error}
                elif not post and path == '/v1/model':
                    result = engine.reasoner.describe()
                elif not post and path == '/v1/memory/folder':
                    from knowledge import memory_folder
                    folder = memory_folder(engine.root)
                    result = {'path': folder or str(engine.root), 'kind': 'selected' if folder else 'workspace'}
                elif post and path == '/v1/memory/folder':
                    result = engine.change_memory_folder(body)
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
                    elif len(parts) == 5 and parts[4] == 'approve' and post:
                        result = engine.approve(parts[3])
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
