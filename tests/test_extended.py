import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'services/executive'))
from server import Executive
from policy import route

class ExtendedPolicyTests(unittest.TestCase):
    def test_new_routes(self):
        for command, capability in [('review memory', 'memory.review'), ('forget memory', 'memory.forget'), ('export memory', 'memory.export'), ('read page: https://example.com', 'browser.read'), ('register worker: research-reporter', 'workers.register'), ('run worker: file-organizer', 'workers.run'), ('create research report', 'workflows.report')]:
            self.assertEqual(route(command), capability)

    def test_consequential_commands_wait_for_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = Executive(pathlib.Path(temp).resolve(), pathlib.Path('/unused'))
            try:
                for command in ['forget memory', 'read page: https://example.com', 'register worker: research-reporter']:
                    task = engine.submit({'command': command})
                    self.assertEqual(task['state'], 'awaiting_approval', command)
                    self.assertEqual(task['scope']['network'], command.startswith('read page:'))
                    self.assertIsNone(task['result'])
                engine.stop()
                self.assertTrue(all(t['state'] == 'cancelled' for t in engine.tasks.values()))
            finally:
                engine.close()

class ProcessBoundaryTests(unittest.TestCase):
    def test_cancelled_process_never_starts(self):
        import threading
        from adapters import run_process, Cancelled
        with tempfile.TemporaryDirectory() as temp:
            marker = pathlib.Path(temp) / 'marker'
            cancel = threading.Event()
            cancel.set()
            with self.assertRaises(Cancelled):
                run_process([sys.executable, '-c', 'from pathlib import Path; Path(' + repr(str(marker)) + ').touch()'], cancel)
            self.assertFalse(marker.exists())

    def test_timeout_terminates_descendants(self):
        import threading
        import time
        from adapters import run_process
        with tempfile.TemporaryDirectory() as temp:
            marker = pathlib.Path(temp) / 'marker'
            child = 'import time; from pathlib import Path; time.sleep(1); Path(' + repr(str(marker)) + ').touch()'
            parent = 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); time.sleep(10)'
            with self.assertRaises(TimeoutError):
                run_process([sys.executable, '-c', parent], threading.Event(), timeout=.1)
            time.sleep(1.1)
            self.assertFalse(marker.exists())

class ScheduleIntegrationTests(unittest.TestCase):
    def test_approval_stop_restart_and_dispatch(self):
        import time
        with tempfile.TemporaryDirectory() as temp:
            data = pathlib.Path(temp).resolve()
            engine = Executive(data, pathlib.Path('/unused'))
            def finish(task):
                for _ in range(300):
                    current = engine.tasks[task['id']]
                    if current['state'] not in {'queued', 'running'}:
                        return current
                    time.sleep(.01)
                self.fail('Task timed out')
            try:
                task = engine.submit({'command': 'register worker: research-reporter'})
                engine.approve(task['id'])
                self.assertEqual(finish(task)['state'], 'succeeded')
                task = engine.submit({'command': 'schedule worker: research-reporter every 60'})
                self.assertEqual(task['state'], 'awaiting_approval')
                engine.approve(task['id'])
                self.assertEqual(finish(task)['state'], 'succeeded')
                engine.scheduler.clock = lambda: 100000000000.0
                for _ in range(200):
                    if any(t['command'] == 'run worker: research-reporter' for t in engine.tasks.values()):
                        break
                    time.sleep(.01)
                self.assertTrue(any(t['command'] == 'run worker: research-reporter' for t in engine.tasks.values()))
                engine.stop()
                self.assertEqual(engine.scheduler.list()[0]['state'], 'paused')
            finally:
                engine.close()

class ReviewRegressionTests(unittest.TestCase):
    def test_stop_cancels_even_when_schedule_persistence_fails(self):
        import threading
        from unittest.mock import patch
        from adapters import Cancelled
        started = threading.Event()
        def block(cap, root, event, helper):
            started.set()
            event.wait(3)
            raise Cancelled('cancelled')
        with tempfile.TemporaryDirectory() as temp:
            engine = Executive(pathlib.Path(temp).resolve(), pathlib.Path('/unused'), executor=block)
            try:
                task = engine.submit({'command': 'list files'})
                self.assertTrue(started.wait(1))
                with patch.object(engine.scheduler, 'pause_all', side_effect=OSError('disk full')):
                    engine.stop()
                self.assertTrue(engine.cancels[task['id']].is_set())
                self.assertIn('disk full', engine.scheduler_error)
            finally:
                engine.close()

    def test_timeout_kills_detached_pipe_child_ignoring_term(self):
        import threading
        import time
        from adapters import run_process
        with tempfile.TemporaryDirectory() as temp:
            marker = pathlib.Path(temp) / 'marker'
            child = 'import signal,time; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(.7); Path(' + repr(str(marker)) + ').touch()'
            parent = 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",' + repr(child) + '],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(10)'
            with self.assertRaises(TimeoutError):
                run_process([sys.executable, '-c', parent], threading.Event(), timeout=.3)
            time.sleep(.8)
            self.assertFalse(marker.exists())

    def test_rejected_memory_answer_is_not_normal_output(self):
        import time
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            engine = Executive(pathlib.Path(temp).resolve(), pathlib.Path('/unused'))
            try:
                with patch('server.execute_knowledge', return_value={'answer': 'stale answer'}), patch('server.verify_knowledge', side_effect=RuntimeError('source changed')):
                    task = engine.submit({'command': 'ask memory: deadline'})
                    for _ in range(200):
                        current = engine.tasks[task['id']]
                        if current['state'] == 'failed': break
                        time.sleep(.01)
                    self.assertEqual(current['state'], 'failed')
                    self.assertIsNone(current['result'])
                    self.assertIn('source changed', current['error'])
            finally:
                engine.close()
