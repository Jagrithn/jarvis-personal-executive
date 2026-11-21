import importlib
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/executive'))
from workflows import execute_workflow


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name).resolve()
        self.root = self.data / 'workspace'
        self.root.mkdir()
        execute_workflow('workers.register', 'register worker: research-reporter', self.root, threading.Event())
        self.schedulers = []

    def tearDown(self):
        for scheduler in self.schedulers:
            scheduler.close()
        self.tmp.cleanup()

    def scheduler(self):
        self.assertIsNotNone(importlib.util.find_spec('scheduler'), 'durable scheduler missing')
        s = importlib.import_module('scheduler').Scheduler(self.data)
        self.schedulers.append(s)
        return s

    def due(self, scheduler):
        # Controlled clock: move clock forward, not alter persisted implementation state.
        scheduler.clock = lambda: 100000000000.0

    def test_create_requires_registered_fixed_template_and_bounded_interval(self):
        s = self.scheduler()
        for name, interval in [('shell', 60), ('file-organizer', 60), ('research-reporter', 59), ('research-reporter', 86401), ('research-reporter', True)]:
            with self.assertRaises(ValueError):
                s.create(name, interval)
        item = s.create('research-reporter', 60)
        self.assertEqual(item['worker'], 'research-reporter')
        self.assertEqual(item['state'], 'active')
        self.assertEqual(len(s.list()), 1)
        for _ in range(9):
            s.create('research-reporter', 60)
        with self.assertRaises(ValueError):
            s.create('research-reporter', 60)

    def test_tick_is_at_most_once_no_overlap_and_no_replay(self):
        s = self.scheduler()
        record = s.create('research-reporter', 60)
        calls = []
        def submit(payload):
            calls.append(payload)
            return {'id': 'task-1', 'state': 'running'}
        self.assertEqual(s.tick(submit, lambda _: None), [])
        self.due(s)
        self.assertEqual(len(s.tick(submit, lambda _: None)), 1)
        self.assertEqual(calls, [{'command': 'run worker: research-reporter'}])
        s.tick(submit, lambda _: {'state': 'running'})
        self.assertEqual(len(calls), 1)
        s.tick(submit, lambda _: {'state': 'succeeded'})
        self.assertEqual(len(calls), 1)
        self.assertEqual(s.list()[0]['next_due'], s.clock() + 60)
        s.clock = lambda: 100000000061.0
        s.tick(submit, lambda _: {'state': 'succeeded'})
        self.assertEqual(len(calls), 2)
        self.assertEqual(s.list()[0]['id'], record['id'])

    def test_pause_cancel_and_restart_require_explicit_resume(self):
        s = self.scheduler()
        item = s.create('research-reporter', 60)
        s.pause_all()
        self.due(s)
        self.assertEqual(s.tick(lambda _: self.fail('paused dispatch'), lambda _: None), [])
        s.resume_all()
        self.assertEqual(s.list()[0]['state'], 'active')
        s.close()
        restarted = self.scheduler()
        self.assertEqual(restarted.list()[0]['state'], 'paused')
        self.due(restarted)
        self.assertEqual(restarted.tick(lambda _: self.fail('restart dispatch'), lambda _: None), [])
        restarted.cancel(item['id'])
        restarted.resume_all()
        self.assertEqual(restarted.list()[0]['state'], 'cancelled')
        with self.assertRaises(ValueError):
            restarted.cancel('../outside')

    def test_failed_submission_consumes_occurrence_without_retry(self):
        s = self.scheduler()
        s.create('research-reporter', 60)
        self.due(s)
        def fail(_):
            raise RuntimeError('submit unavailable')
        result = s.tick(fail, lambda _: None)
        self.assertEqual(len(result), 1)
        self.assertIn('submit unavailable', result[0]['error'])
        self.assertEqual(s.tick(lambda _: self.fail('retried'), lambda _: None), [])

    def test_restart_unknown_inflight_pauses_and_resume_clears_orphan(self):
        s = self.scheduler()
        s.create('research-reporter', 60)
        self.due(s)
        s.tick(lambda _: {'id': 'lost-task', 'state': 'running'}, lambda _: None)
        s.close()
        restarted = self.scheduler()
        self.assertEqual(restarted.list()[0]['task_id'], 'lost-task')
        restarted.resume_all()
        self.assertIsNone(restarted.list()[0]['task_id'])
        self.assertEqual(restarted.list()[0]['state'], 'active')

    def test_symlink_database_is_rejected(self):
        (self.data / 'schedules.sqlite3').symlink_to(self.data / 'outside')
        with self.assertRaises((ValueError, OSError)):
            self.scheduler()
        self.assertFalse((self.data / 'outside').exists())

    def test_resume_does_not_clear_a_live_inflight_task(self):
        s = self.scheduler()
        s.create('research-reporter', 60)
        self.due(s)
        s.tick(lambda _: {'id': 'still-running'}, lambda _: None)
        s.pause_all()
        s.resume_all()
        self.assertEqual(s.list()[0]['task_id'], 'still-running')
        s.clock = lambda: 100000001000.0
        self.assertEqual(s.tick(lambda _: self.fail('overlap'), lambda _: {'state': 'running'}), [])
        self.assertEqual(s.tick(lambda _: self.fail('unknown task overlap'), lambda _: None), [])

    def test_submission_error_is_paused_with_durable_inflight_reservation(self):
        s = self.scheduler()
        s.create('research-reporter', 60)
        self.due(s)
        s.tick(lambda _: None, lambda _: None)
        row = s.list()[0]
        self.assertEqual(row['state'], 'paused')
        self.assertEqual(row['inflight'], 1)
        self.assertIsNone(row['task_id'])
        s.resume_all()
        s.clock = lambda: 100000001000.0
        self.assertEqual(s.tick(lambda _: self.fail('ambiguous submit replay'), lambda _: None), [])

    def test_worker_registry_rechecked_at_dispatch(self):
        s = self.scheduler()
        s.create('research-reporter', 60)
        (self.data / 'workers.sqlite3').unlink()
        self.due(s)
        self.assertEqual(s.tick(lambda _: self.fail('unregistered dispatch'), lambda _: None), [])
        self.assertEqual(s.list()[0]['state'], 'paused')
        with self.assertRaises(ValueError):
            s.resume_all()

    def test_independent_persisted_verification_rejects_replaced_database(self):
        s = self.scheduler()
        initial_bytes = (self.data / 'schedules.sqlite3').read_bytes()
        s.create('research-reporter', 60)
        self.assertTrue(hasattr(s, 'verify_persisted'), 'independent scheduler verifier missing')
        self.assertEqual(s.verify_persisted(), 1)
        (self.data / 'schedules.sqlite3').write_bytes(initial_bytes)
        with self.assertRaises(RuntimeError):
            s.verify_persisted()
