"""Exercise browser requests through an isolated executive with real macOS callbacks."""
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'services/executive'))
from server import Executive

commands = ['Okay Jarvis search for text models on Google Chrome',
            'Okay Jarvis open Google', 'Please search Chrome for astronomy',
            'Hey, Jarvis, look up solar energy on Google',
            'Can you search the web for Python tutorials',
            'Open Chrome then search for local voice models',
            'Search for public libraries using Chrome',
            'Google computer history',
            'Jarvis, please open Google Chrome and search for renewable energy',
            'Search online for space exploration']
receipts = []
with tempfile.TemporaryDirectory(prefix='.search-test-', dir=ROOT) as tmp:
    engine = Executive(Path(tmp).resolve(), ROOT/'.build/JARVIS.app/Contents/Resources/verify-app')
    try:
        for command in commands:
            task = engine.submit({'command': command})
            if task['state'] == 'awaiting_approval': engine.approve(task['id'])
            deadline = time.monotonic()+30
            while time.monotonic() < deadline:
                with engine.lock: task = engine.snapshot(engine.tasks[task['id']])
                if task['state'] not in {'queued', 'running'}: break
                time.sleep(.05)
            receipts.append(task)
            print(command, task['state'], task['error'], flush=True)
    finally:
        engine.close()
(ROOT/'artifacts/search-acceptance.json').write_text(json.dumps(receipts, indent=2))
assert all(t['state']=='succeeded' and t['evidence'] for t in receipts)
