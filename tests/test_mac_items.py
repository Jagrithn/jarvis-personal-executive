import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/executive'))
import mac_items


class MacItemsTests(unittest.TestCase):
    def test_repeat_is_remembered_across_executive_restarts(self):
        from server import Executive
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp).resolve() / 'data'
            folder = Path(tmp).resolve() / 'target'
            folder.mkdir()
            command = 'open ' + str(folder)
            def submit_and_wait(engine):
                task = engine.submit({'command': command})
                for _ in range(300):
                    with engine.lock:
                        task = engine.snapshot(engine.tasks[task['id']])
                    if task['state'] not in {'queued', 'running'}: return task
                    time.sleep(.01)
                self.fail('task timed out')
            with patch.object(mac_items, 'run_process', return_value='com.apple.finder'):
                engine = Executive(data, Path('/helper'))
                try:
                    first = submit_and_wait(engine)
                    self.assertFalse(first['result']['reused_previous_target'])
                finally: engine.close()
                engine = Executive(data, Path('/helper'))
                try:
                    second = submit_and_wait(engine)
                    self.assertEqual(second['state'], 'succeeded')
                    self.assertTrue(second['result']['reused_previous_target'])
                    self.assertEqual(second['evidence'][0]['path'], str(folder))
                finally: engine.close()
    def test_verified_repeat_reuses_unchanged_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve() / 'notes'
            folder.mkdir()
            with patch.object(mac_items, 'candidates', return_value=[folder]) as search, \
                 patch.object(mac_items, 'run_process', return_value='com.apple.finder'):
                first = mac_items.perform('open my notes folder', threading.Event(), Path('/helper'))
                second = mac_items.perform('open my notes folder', threading.Event(), Path('/helper'), remembered=first['opened'])
            self.assertEqual(search.call_count, 1)
            self.assertTrue(second['reused_previous_target'])
            self.assertEqual(second['opened'][0]['path'], str(folder))

    def test_changed_folder_identity_forces_fresh_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve() / 'notes'
            folder.mkdir()
            stale = [{'path':str(folder), 'device':-1, 'inode':-1}]
            with patch.object(mac_items, 'candidates', return_value=[folder]) as search, \
                 patch.object(mac_items, 'run_process', return_value='com.apple.finder'):
                result = mac_items.perform('open notes folder', threading.Event(), Path('/helper'), remembered=stale)
            search.assert_called_once()
            self.assertFalse(result['reused_previous_target'])
    def test_applications_means_standard_applications_folder(self):
        self.assertEqual(mac_items.candidates('open Applications folder', threading.Event()), [Path('/Applications')])

    def test_system_safari_target_is_eligible(self):
        safari = Path('/Applications/Safari.app')
        if not safari.exists(): self.skipTest('Safari not installed')
        self.assertTrue(mac_items.eligible(safari.resolve()))

    def test_short_folder_name_excludes_substrings(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'PES'
            noise = Path(tmp)/'types'
            target.mkdir()
            noise.mkdir()
            with patch.object(mac_items, 'run_process', return_value=f'{noise}\0{target}\0'):
                self.assertEqual(mac_items.candidates('open pes folder', threading.Event()), [target.resolve()])

    def test_alias_and_duplicate_install_prefer_applications(self):
        with patch.object(mac_items, 'installed_apps', return_value=[Path('/Applications/YouTube.app'), Path('/Users/test/Applications/YouTube.app')]):
            self.assertEqual(mac_items.candidates('open youtube', threading.Event()), [Path('/Applications/YouTube.app')])
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)/'Visual Studio Code.app'
            app.mkdir()
            with patch.object(mac_items, 'APP_BASES', (Path(tmp),)):
                self.assertEqual(mac_items.installed_apps('vs code'), [app.resolve()])

    def test_ambiguous_open_does_not_invoke_open_helper(self):
        with patch.object(mac_items, 'candidates', return_value=[Path('/a/PES'), Path('/b/PES')]), patch.object(mac_items, 'run_process') as runner:
            result = mac_items.perform('open pes folder', threading.Event(), Path('/helper'))
            self.assertEqual(result['outcome'], 'needs_clarification')
            self.assertEqual(result['opened'], [])
            runner.assert_not_called()

    def test_missing_open_reports_not_found(self):
        with patch.object(mac_items, 'candidates', return_value=[]):
            self.assertEqual(mac_items.perform('open missing folder', threading.Event(), Path('/helper'))['outcome'], 'not_found')
