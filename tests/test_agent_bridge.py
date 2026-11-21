import pathlib
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'services/executive'))
from server import Executive
from agent import plain_chat

class BridgeTests(unittest.TestCase):
    def test_plain_chat_does_not_swallow_action_requests(self):
        for prompt in ('Hi', 'What is a black hole?', 'How are you?'):
            self.assertTrue(plain_chat(prompt), prompt)
        for prompt in ('Open Spotify', 'Can you text Alice?', 'Please search Chrome for black holes',
                       'Hey Jarvis open Finder'):
            self.assertFalse(plain_chat(prompt), prompt)
    def settle(self, engine, task):
        for _ in range(300):
            current = engine.snapshot(engine.tasks[task['id']])
            if current['state'] not in {'running','queued'}:
                return current
            time.sleep(.01)
        self.fail('Task did not settle')

    def test_plan_approval_and_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            engine = Executive(pathlib.Path(d).resolve(), pathlib.Path('/missing'))
            try:
                with patch('server.execute_knowledge', return_value={'answer':'Planned','actions':['files.sample','files.list']}):
                    task = self.settle(engine, engine.submit({'command':'Please make a sample then list the folder'}))
                self.assertEqual(task['state'], 'awaiting_approval')
                self.assertEqual(list(engine.root.iterdir()), [])
                self.assertEqual(task['proposal']['capability'], 'agent.plan')
                engine.approve(task['id'])
                task = self.settle(engine, task)
                self.assertEqual(task['state'], 'succeeded', task)
                self.assertEqual(len(task['evidence']), 2)
                self.assertEqual(len(list(engine.root.iterdir())), 1)
            finally:
                engine.close()

    def test_invalid_plan_has_no_effect(self):
        with tempfile.TemporaryDirectory() as d:
            engine = Executive(pathlib.Path(d).resolve(), pathlib.Path('/missing'))
            try:
                with patch('server.execute_knowledge', return_value={'answer':'bad','actions':['shell.execute']}):
                    task = self.settle(engine, engine.submit({'command':'Do something'}))
                self.assertEqual(task['state'], 'failed')
                self.assertEqual(list(engine.root.iterdir()), [])
            finally:
                engine.close()
