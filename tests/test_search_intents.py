"""Regression matrix for natural browser requests and local-search boundaries."""
import sys
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/executive'))
from browser import chrome_query
from policy import route
from server import Executive

PREFIXES = ['', 'Okay Jarvis ', 'Hey, Jarvis, ', 'Jarvis, please ', 'Can you ']
PHRASES = ['search for {q} on Google Chrome', 'search Chrome for {q}',
           'open Google Chrome and search for {q}', 'look up {q} on Google',
           'search the web for {q}', 'google {q}', 'search for {q} using Chrome',
           'open Chrome then search for {q}']
TOPICS = ['text models', 'solar energy', 'Python tutorials']

class SearchIntentTests(unittest.TestCase):
    def test_wording_matrix(self):
        for prefix in PREFIXES:
            for phrase in PHRASES:
                for topic in TOPICS:
                    command = prefix + phrase.format(q=topic)
                    with self.subTest(command=command):
                        self.assertEqual(chrome_query(command), topic)
                        self.assertEqual(route(command, True), 'browser.search')

    def test_google_open_and_local_boundaries(self):
        for prefix in PREFIXES:
            self.assertEqual(chrome_query(prefix + 'open Google'), '')
        for command in ['search memory: Chrome', 'find chemistry folder',
                        'search for my tax files', 'open Google folder',
                        "don't search Chrome for cats", 'how do I search Google?',
                        'search Chrome for cats and send to Rahul']:
            with self.subTest(command=command):
                self.assertIsNone(chrome_query(command))

    def test_service_routes_and_executes_varied_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = Executive(Path(tmp).resolve(), Path('/test-helper'))
            try:
                for phrase in PHRASES:
                    command = 'Okay Jarvis ' + phrase.format(q='text models')
                    with patch('adapters.run_process', return_value='https://www.google.com/search?q=text+models') as runner:
                        task = engine.submit({'command': command})
                        self.assertEqual(task['capability'], 'browser.search')
                        self.assertIn(task['state'], ('queued', 'running', 'succeeded'))
                        for _ in range(200):
                            with engine.lock:
                                task = engine.snapshot(engine.tasks[task['id']])
                            if task['state'] not in {'queued', 'running'}: break
                            time.sleep(.01)
                        self.assertEqual(task['state'], 'succeeded', task)
                        self.assertIn('q=text+models', task['result']['url'])
                        self.assertTrue(task['evidence'])
            finally:
                engine.close()
