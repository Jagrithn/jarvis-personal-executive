#!/usr/bin/env python3
"""Real macOS integration smoke: launches Calculator/Finder and writes isolated demo files."""
import json
import pathlib
import select
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / 'artifacts/smoke-data'
HELPER = ROOT / '.build/JARVIS.app/Contents/Resources/verify-app'
receipts = []

def launch():
    token = uuid.uuid4().hex + uuid.uuid4().hex
    p = subprocess.Popen([sys.executable, str(ROOT / 'services/executive/server.py'), '--data', str(DATA), '--helper', str(HELPER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p.stdin.write(token + '\n')
    p.stdin.flush()
    if not select.select([p.stdout], [], [], 8)[0]:
        p.kill()
        raise RuntimeError('Startup timeout')
    line = p.stdout.readline()
    if not line:
        raise RuntimeError(p.stderr.read())
    port = json.loads(line)['port']
    return p, token, port

def call(token, port, path, body=None):
    req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/{path}',
        headers={'Authorization': 'Bearer ' + token}, data=None if body is None else json.dumps(body).encode())
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)

def stop(p):
    p.stdin.close()
    p.wait(timeout=15)
    assert p.returncode == 0, p.stderr.read()

p, token, port = launch()
try:
    assert call(token, port, 'health')['status'] == 'ok'
    for command in ['open calculator', 'open finder', 'create sample file', 'list demo folder']:
        task = call(token, port, 'tasks', {'command': command})
        for _ in range(150):
            task = call(token, port, 'tasks/' + task['id'])
            if task['state'] not in ['queued', 'running']:
                break
            time.sleep(.1)
        receipts.append(task)
        assert task['state'] == 'succeeded', task
        assert task['evidence'], task
    denial = call(token, port, 'tasks', {'command': 'list files', 'path': '/etc'})
    assert denial['state'] == 'failed'
    receipts.append(denial)
    assert call(token, port, 'stop-all', {})['paused']
    assert not call(token, port, 'resume', {})['paused']
finally:
    stop(p)
p, token, port = launch()
try:
    history = call(token, port, 'tasks')
    assert all(any(t['id'] == r['id'] for t in history) for r in receipts)
finally:
    stop(p)
(ROOT / 'artifacts/smoke-results.json').write_text(json.dumps({'commands': receipts, 'restart_persistence': True, 'graceful_shutdown': True}, indent=2))
print('PASS: four real macOS commands, evidence, rejected path, stop/resume, restart persistence, parent-pipe shutdown')
