import pathlib
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'services/executive'))
from server import Executive
from reasoning import validate, LocalReasoner, preflight
from adapters import Cancelled, run_process

class FakeReasoner:
    enabled = True
    def __init__(self, capability='files.sample'):
        self.capability = capability
    def propose(self, command, event):
        return {'capability': self.capability, 'reason': 'Test proposal'}
    def close(self):
        pass

class ReasoningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = Executive(pathlib.Path(self.temp.name).resolve(), pathlib.Path('/missing'), reasoner=FakeReasoner())
    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()
    def wait(self, task):
        for _ in range(200):
            with self.engine.lock:
                current = self.engine.snapshot(self.engine.tasks[task['id']])
            if current['state'] not in ('queued', 'running'):
                return current
            time.sleep(.01)
        self.fail('Task did not settle')
    def test_compound_and_negated_requests_refused_before_model(self):
        for command in ('Open Finder and create a sample file', 'Open Calculator then Finder',
                        'List files; create a file', 'Open Finder & Calculator',
                        "Don't open Calculator", 'Do not open Finder'):
            self.assertIsNotNone(preflight(command))
        self.assertIsNone(preflight('Please launch Finder for me'))

    def test_schema_rejects_untrusted_shapes(self):
        for proposal in ([], {}, {'capability': 'shell', 'reason': 'Do it'}, {'capability': 'files.list', 'reason': ''}, {'capability': 'files.list', 'reason': 'ok', 'permissions': '*'}, {'capability': 'files.list', 'reason': 7}):
            with self.assertRaises(ValueError):
                validate(proposal)
    def test_proposal_never_executes_without_confirmation(self):
        task = self.wait(self.engine.submit({'command': 'Make me a demo document please'}))
        self.assertEqual(task['state'], 'awaiting_approval')
        self.assertEqual(list(self.engine.root.iterdir()), [])
        self.assertIsNone(task['result'])
        self.engine.approve(task['id'])
        finished = self.wait(task)
        self.assertEqual(finished['state'], 'succeeded')
        self.assertTrue(finished['evidence'])
        with self.assertRaises(ValueError):
            self.engine.approve(task['id'])
        self.assertEqual(len(list(self.engine.root.iterdir())), 1)
    def test_reject_and_stop_cancel_pending_approval(self):
        for method in ('cancel', 'stop'):
            task = self.wait(self.engine.submit({'command': 'Make me a demo document please'}))
            if method == 'cancel':
                self.engine.cancel(task['id'])
            else:
                self.engine.stop()
            self.assertEqual(self.engine.tasks[task['id']]['state'], 'cancelled')
            self.assertEqual(list(self.engine.root.iterdir()), [])
    def test_model_cannot_expand_scope(self):
        task = self.engine.submit({'command': 'Please list my documents', 'path': '/etc'})
        self.assertEqual(task['state'], 'failed')
        self.engine.reasoner.capability = 'shell.execute'
        task = self.wait(self.engine.submit({'command': 'Execute a shell'}))
        self.assertEqual(task['state'], 'failed')
        self.assertEqual(list(self.engine.root.iterdir()), [])
    def test_model_refusal(self):
        self.engine.reasoner.capability = 'none'
        task = self.wait(self.engine.submit({'command': 'Send email'}))
        self.assertEqual(task['state'], 'failed')
        self.assertFalse(task['evidence'])
    def test_exact_commands_bypass_model(self):
        def broken(*args):
            raise AssertionError('Model should not be invoked')
        self.engine.reasoner.propose = broken
        task = self.wait(self.engine.submit({'command': 'list files'}))
        self.assertEqual(task['state'], 'succeeded')
    def test_cancel_during_reasoning(self):
        started = threading.Event()
        def slow(command, event):
            started.set()
            event.wait(2)
            raise Cancelled('Cancelled inference')
        self.engine.reasoner.propose = slow
        task = self.engine.submit({'command': 'Can you make a sample?'})
        self.assertTrue(started.wait(1))
        self.engine.cancel(task['id'])
        self.assertEqual(self.wait(task)['state'], 'cancelled')
        self.assertEqual(list(self.engine.root.iterdir()), [])
    def test_unavailable_model_fails_without_action(self):
        def unavailable(*args):
            raise ValueError('Local model unavailable')
        self.engine.reasoner.propose = unavailable
        task = self.wait(self.engine.submit({'command': 'Please open calculator for me'}))
        self.assertEqual(task['state'], 'failed')
        self.assertIsNone(task['result'])

class InferenceProcessTests(unittest.TestCase):
    def test_private_input_and_subprocess_cancellation(self):
        cancelled = threading.Event()
        timer = threading.Timer(.15, cancelled.set)
        started = time.monotonic()
        timer.start()
        try:
            with self.assertRaises(Cancelled):
                run_process([sys.executable, '-c', 'import sys,time; sys.stdin.read(); time.sleep(10)'], cancelled, timeout=3, input_text='private request')
        finally:
            timer.cancel()
        self.assertLess(time.monotonic() - started, 2)

    def test_private_input_survives_polling(self):
        result = run_process([sys.executable, '-c', 'import sys,time; data=sys.stdin.read(); time.sleep(.15); print(data)'], threading.Event(), timeout=2, input_text='one request')
        self.assertEqual(result, 'one request')
