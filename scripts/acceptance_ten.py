#!/usr/bin/env python3
"""Run varied real assistant requests in an isolated executive and keep receipts."""
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/executive'))
from server import Executive

commands = [
    ('chat', 'Hi'), ('chat', 'What is 17 plus 25?'),
    ('chat', 'Explain gravity in one sentence.'), ('chat', 'What is the capital of Japan?'),
    ('chat', 'Give one example of a renewable energy source.'),
    ('chat', 'Tell me this code word back: saffron42.'),
    ('chat', 'What code word did I just tell you?'),
    ('chat', 'What is water made of?'), ('chat', 'Give a short study tip.'),
    ('chat', 'How many minutes are in two hours?'),
    ('mac', 'open pes folder'), ('mac', 'open physics folder'),
    ('mac', 'open chemistry folder'), ('mac', 'open vs code'),
    ('mac', 'open youtube'), ('mac', 'open whatsapp'),
    ('mac', 'open Documents'), ('mac', 'open Downloads'),
    ('mac', 'open Desktop'), ('mac', 'open TextEdit'),
]
receipts = []
with tempfile.TemporaryDirectory(prefix='.acceptance-', dir=ROOT) as folder:
    data = Path(folder)
    (data / 'enable-local-model').touch()
    engine = Executive(data, ROOT / '.build/JARVIS.app/Contents/Resources/verify-app')
    try:
        for domain, command in commands:
            task = engine.submit({'command': command})
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                with engine.lock:
                    task = engine.snapshot(engine.tasks[task['id']])
                if task['state'] not in {'queued', 'running'}: break
                time.sleep(.1)
            receipts.append({'domain': domain, 'command': command, 'state': task['state'], 'capability': task['capability'], 'result': task['result'], 'error': task['error'], 'evidence': task['evidence']})
            print(json.dumps(receipts[-1]), flush=True)
    finally:
        engine.close()
(ROOT / 'artifacts/acceptance-ten.json').write_text(json.dumps(receipts, indent=2))
