#!/usr/bin/env python3
"""Real API, native memory, browser and workflow smoke with isolated disposable notes."""
import json
import pathlib
import select
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
receipts = []
with tempfile.TemporaryDirectory(prefix='.jarvis-smoke-', dir=ROOT) as folder:
    data = pathlib.Path(folder)
    (data / 'workspace').mkdir()
    (data / 'workspace/mission.md').write_text('Aurora launch is November 12. Owner: Demo Team.\n')
    token = uuid.uuid4().hex + uuid.uuid4().hex
    process = subprocess.Popen([sys.executable, str(ROOT / 'services/executive/server.py'), '--data', str(data), '--helper', str(ROOT / '.build/JARVIS.app/Contents/Resources/verify-app')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    process.stdin.write(token + '\n'); process.stdin.flush()
    try:
        if not select.select([process.stdout], [], [], 10)[0]:
            raise RuntimeError('Startup timed out')
        line = process.stdout.readline()
        if not line:
            raise RuntimeError(process.stderr.read())
        port = json.loads(line)['port']
        def call(path, body=None):
            request = urllib.request.Request(f'http://127.0.0.1:{port}/v1/{path}', data=None if body is None else json.dumps(body).encode(), headers={'Authorization': 'Bearer ' + token})
            with urllib.request.urlopen(request, timeout=6) as response:
                return json.load(response)
        def run(command):
            task = call('tasks', {'command': command})
            if task['state'] == 'awaiting_approval':
                assert task['result'] is None
                call('tasks/' + task['id'] + '/approve', {})
            for _ in range(600):
                task = call('tasks/' + task['id'])
                if task['state'] not in {'queued', 'running'}:
                    break
                time.sleep(.1)
            receipts.append(task)
            assert task['state'] == 'succeeded', task
            assert task['evidence'], task
            return task
        for command in ['index workspace', 'search memory: Aurora', 'review memory', 'export memory', 'create research report', 'draft workspace summary', 'plan file organization', 'register worker: research-reporter', 'register worker: file-organizer', 'run worker: research-reporter', 'run worker: file-organizer', 'list workers', 'schedule worker: research-reporter every 60', 'list schedules', 'read page: https://example.com']:
            run(command)
        (data / 'workspace/mission.md').write_text('Aurora launch moved to December 20.\n')
        stale = run('search memory: Aurora')
        assert not stale['result']['matches']
        run('forget memory')
        assert (data / 'workspace/mission.md').exists()
        call('stop-all', {})
        call('resume', {})
        schedules = run('list schedules')
        assert all(s['state'] == 'paused' for s in schedules['result']['schedules'])
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()
        if process.returncode:
            raise RuntimeError(process.stderr.read())
(ROOT / 'artifacts/smoke-extended.json').write_text(json.dumps({'tasks': receipts, 'graceful_shutdown': True}, indent=2))
print(f'PASS: {len(receipts)} real API tasks, native memory, stale filtering, browser, workflows, schedules and shutdown')
