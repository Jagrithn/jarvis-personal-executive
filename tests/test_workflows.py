import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/executive'))


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name).resolve()
        self.root = self.data / 'workspace'
        self.root.mkdir()
        (self.root / 'notes.md').write_text('Revenue was 12 units.\nNext: review budget.\n')
        self.cancel = threading.Event()

    def tearDown(self):
        self.tmp.cleanup()

    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('workflows'), 'workflow implementation missing')
        return importlib.import_module('workflows')

    def run_workflow(self, cap, command):
        return self.api().execute_workflow(cap, command, self.root, self.cancel)

    def test_report_draft_and_manifest_are_verified_unique_artifacts(self):
        for cap, cmd in [('workflows.report', 'create research report'), ('workflows.draft', 'draft workspace summary'), ('workflows.organize', 'plan file organization')]:
            result = self.run_workflow(cap, cmd)
            artifact = self.root / result['filename']
            self.assertTrue(artifact.is_file())
            self.assertEqual(artifact.stat().st_mode & 0o777, 0o600)
            self.assertTrue(self.api().verify_workflow(cap, result, self.root))
            again = self.run_workflow(cap, cmd)
            self.assertNotEqual(result['filename'], again['filename'])
            artifact.write_text('tampered')
            with self.assertRaises(RuntimeError):
                self.api().verify_workflow(cap, result, self.root)
        self.assertIn('Revenue was 12', (self.root / 'notes.md').read_text())

    def test_report_cites_source_and_changes_fail_verification(self):
        result = self.run_workflow('workflows.report', 'create research report')
        self.assertIn('notes.md', (self.root / result['filename']).read_text())
        (self.root / 'notes.md').write_text('changed')
        with self.assertRaises(RuntimeError):
            self.api().verify_workflow('workflows.report', result, self.root)

    def test_cancellation_no_writes(self):
        self.cancel.set()
        from adapters import Cancelled
        for cap, cmd in [('workflows.report', 'create research report'), ('workers.register', 'register worker: research-reporter')]:
            with self.assertRaises(Cancelled):
                self.run_workflow(cap, cmd)
        self.assertEqual(list(self.root.iterdir()), [self.root / 'notes.md'])
        self.assertFalse((self.data / 'workers.sqlite3').exists())

    def test_symlinks_are_not_followed_and_verification_rejects_escape(self):
        (self.data / 'secret.txt').write_text('SECRET')
        (self.root / 'link.md').symlink_to(self.data / 'secret.txt')
        result = self.run_workflow('workflows.report', 'create research report')
        self.assertNotIn('SECRET', (self.root / result['filename']).read_text())
        result['filename'] = '../secret.txt'
        with self.assertRaises((ValueError, RuntimeError)):
            self.api().verify_workflow('workflows.report', result, self.root)
        link = self.data / 'linked'
        link.symlink_to(self.root)
        with self.assertRaises((ValueError, OSError)):
            self.api().execute_workflow('workflows.report', 'create research report', link, self.cancel)

    def test_registry_restart_versions_and_fixed_templates(self):
        self.assertEqual(self.run_workflow('workers.list', 'list workers')['workers'], [])
        for name in ['research-reporter', 'file-organizer']:
            with self.assertRaises(ValueError):
                self.run_workflow('workers.run', 'run worker: ' + name)
            result = self.run_workflow('workers.register', 'register worker: ' + name)
            self.assertEqual(result['evaluation']['checks'], ['functional output', 'scope exclusion', 'tamper rejection'])
            self.assertTrue(self.api().verify_workflow('workers.register', result, self.root))
            importlib.reload(self.api())
            execution = self.run_workflow('workers.run', 'run worker: ' + name)
            self.assertTrue(self.api().verify_workflow('workers.run', execution, self.root))
        result = self.run_workflow('workers.register', 'register worker: research-reporter')
        self.assertEqual(result['worker']['revision'], 2)
        self.assertEqual(len(self.run_workflow('workers.list', 'list workers')['workers']), 2)
        for name in ['shell', '../evil', 'research-reporter; ls']:
            with self.assertRaises(ValueError):
                self.run_workflow('workers.register', 'register worker: ' + name)

    def test_failed_trial_does_not_register_worker(self):
        api = self.api()
        with patch.object(api, 'evaluate_template', side_effect=RuntimeError('trial failed')):
            with self.assertRaisesRegex(RuntimeError, 'trial failed'):
                self.run_workflow('workers.register', 'register worker: research-reporter')
        self.assertFalse((self.data / 'workers.sqlite3').exists())
        self.assertEqual(self.run_workflow('workers.list', 'list workers')['workers'], [])

    def test_registry_symlink_rejected_and_commands_bound(self):
        (self.data / 'workers.sqlite3').symlink_to(self.data / 'outside')
        with self.assertRaises((ValueError, OSError)):
            self.run_workflow('workers.register', 'register worker: research-reporter')
        with self.assertRaises(ValueError):
            self.run_workflow('workflows.report', 'send email')
        self.assertFalse((self.data / 'outside').exists())

    def test_generated_artifacts_are_excluded_before_note_size_limits(self):
        (self.root / 'jarvis-report-old.md').write_text('x' * 70000)
        result = self.run_workflow('workflows.report', 'create research report')
        self.assertEqual([s['source'] for s in result['sources']], ['notes.md'])
        self.assertTrue(self.api().verify_workflow('workflows.report', result, self.root))

    def test_read_only_workspace_cannot_write(self):
        import os
        if os.geteuid() == 0:
            self.skipTest('Root bypasses mode permissions')
        self.root.chmod(0o500)
        try:
            with self.assertRaises(PermissionError):
                self.run_workflow('workflows.report', 'create research report')
        finally:
            self.root.chmod(0o700)

    def test_cancellation_between_source_read_and_write(self):
        class CancelOnThirdCheck:
            checks = 0
            def is_set(self):
                self.checks += 1
                return self.checks >= 3
        from adapters import Cancelled
        with self.assertRaises(Cancelled):
            self.api().execute_workflow('workflows.report', 'create research report', self.root, CancelOnThirdCheck())
        self.assertEqual([p.name for p in self.root.iterdir()], ['notes.md'])
