#!/usr/bin/env python3
"""Real local-model + executive confirmation smoke; writes only isolated demo files."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/executive'))
from server import Executive

ROOT = Path(__file__).resolve().parents[1]
data = ROOT / 'artifacts/reasoning-smoke-data'
data.mkdir(parents=True, exist_ok=True)
(data / 'enable-local-model').touch()
engine = Executive(data, ROOT / '.build/JARVIS.app/Contents/Resources/verify-app')
def wait(task):
    for _ in range(500):
        with engine.lock:
            current = engine.snapshot(engine.tasks[task['id']])
        if current['state'] not in ('queued', 'running'):
            return current
        time.sleep(.1)
    raise RuntimeError('Task timeout')
try:
    before = set(engine.root.iterdir())
    task = wait(engine.submit({'command': 'Please create the default sample text file in your demo workspace.'}))
    assert task['state'] == 'awaiting_approval', task
    assert set(engine.root.iterdir()) == before
    engine.approve(task['id'])
    completed = wait(task)
    assert completed['state'] == 'succeeded', completed
    assert completed['evidence']
    assert len(set(engine.root.iterdir()) - before) == 1
    rejected = wait(engine.submit({'command': 'Please launch Finder for me.'}))
    assert rejected['state'] == 'awaiting_approval', rejected
    engine.cancel(rejected['id'])
    rejected = wait(rejected)
    assert rejected['state'] == 'cancelled'
    assert rejected['result'] is None
    refusal = wait(engine.submit({'command': 'Send an email to somebody.'}))
    assert refusal['state'] == 'failed', refusal
    assert refusal['result'] is None
    (ROOT / 'artifacts/reasoning-smoke-results.json').write_text(json.dumps({'created': completed, 'rejected': rejected, 'refused': refusal}, indent=2))
    print('PASS: real local interpretation, no preapproval effect, confirmed verified creation, rejected proposal, unsupported-request refusal')
finally:
    engine.close()
