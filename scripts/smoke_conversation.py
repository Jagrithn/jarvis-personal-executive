#!/usr/bin/env python3
"""Real local-model conversation acceptance, without touching personal notes."""
import json
from pathlib import Path
import sys
import tempfile
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/executive'))
from server import Executive

receipts = []
with tempfile.TemporaryDirectory(prefix='.conversation-smoke-', dir=ROOT) as folder:
    data = Path(folder)
    (data / 'enable-local-model').touch()
    engine = Executive(data, ROOT / '.build/JARVIS.app/Contents/Resources/verify-app')
    try:
        for _ in range(100):
            if engine.reasoner.describe()['installed']: break
            time.sleep(.1)
        for command in ['Hi', 'Explain gravity and give one simple example.', 'Tell me this code word back: saffron42.', 'What code word did I just tell you?']:
            started = time.monotonic()
            task = engine.submit({'command': command})
            while time.monotonic() - started < 85:
                with engine.lock:
                    task = engine.snapshot(engine.tasks[task['id']])
                if task['state'] not in {'queued', 'running'}: break
                time.sleep(.1)
            assert task['state'] == 'succeeded', task
            assert task['capability'] == 'chat.local', task
            answer = task['result']['answer']
            assert answer.strip() and '<think>' not in answer and '</think>' not in answer, answer
            assert not any(phrase in answer.lower() for phrase in ['the user said', 'the user asked', 'let me check the instructions', 'i need to respond']), answer
            if command == 'Hi':
                assert len(answer) < 500, 'Greeting must be concise, not drafting text'
            if command.startswith('What code word'):
                assert 'saffron42' in answer.lower(), answer
            assert not list(engine.root.iterdir()), 'Conversation unexpectedly wrote workspace files'
            receipts.append({'command': command, 'answer': answer, 'seconds': round(time.monotonic()-started, 2), 'evidence': task['evidence']})
    finally:
        engine.close()
(ROOT / 'artifacts/conversation-smoke.json').write_text(json.dumps(receipts, indent=2))
print(json.dumps(receipts, indent=2))
