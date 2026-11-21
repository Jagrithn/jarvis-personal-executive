import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/executive'))
import coding
from adapters import Cancelled

HTML = b'<!doctype html><html><head><title>Assignment Tracker</title><style>body{color:cyan}</style></head><body><h1>Assignment Tracker</h1><table><tr><th>Assignment</th><th>Due</th><th>Status</th></tr><tr><td>Math</td><td>Tomorrow</td><td>Pending</td></tr></table></body></html>'

class CodingTests(unittest.TestCase):
    def test_static_output_checks(self):
        self.assertTrue(coding.inspect_html(HTML))
        for bad in [b'worker says success', HTML.replace(b'</body>', b'<script>alert(1)</script></body>'), HTML.replace(b'<table>', b'<table onclick="bad()">'), HTML.replace(b'body{color:cyan}', b'@import "https://example.com/x";'), HTML.replace(b'<table>', b'<iframe src="https://example.com"></iframe><table>')]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                coding.inspect_html(bad)

    def test_policy_is_scoped(self):
        p = coding.sandbox_policy(Path('/private/tmp/job'), Path('/opt/homebrew/Cellar/opencode/1/bin/opencode'))
        self.assertIn('(deny default)', p)
        self.assertIn('localhost:11435', p)
        self.assertNotIn('(allow network*)', p)
        self.assertNotIn('(subpath "/Users")', p)
        self.assertIn('(subpath "/private/tmp/job/work")', p)

    def test_bad_command_and_absent_runtime(self):
        with tempfile.TemporaryDirectory() as d:
            for cap, cmd in [('coding.shell', 'build demo app'), ('coding.build', 'rm -rf x')]:
                with self.assertRaises(ValueError): coding.execute_coding(cap, cmd, Path(d).resolve(), threading.Event())
            with patch.object(coding, 'OPENCODE', Path('/missing/opencode')), self.assertRaisesRegex(RuntimeError, 'OpenCode'):
                coding.execute_coding('coding.build', 'build demo app', Path(d).resolve(), threading.Event())

    def test_cancel_before_start(self):
        cancel = threading.Event(); cancel.set()
        with self.assertRaises(Cancelled): coding.execute_coding('coding.build', 'build demo app', Path('/missing'), cancel)

    def test_symlink_root_and_forged_result(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d).resolve(); link = base / 'link'; link.symlink_to(base, target_is_directory=True)
            with self.assertRaises(ValueError): coding.safe_directory(link)
            for result in [{'job': '../escape'}, {'job': 'jarvis-code-' + '0' * 32, 'sha256': hashlib.sha256(HTML).hexdigest()}]:
                with self.assertRaises((ValueError, FileNotFoundError)):
                    coding.verify_coding('coding.build', result, base)

    def test_worker_environment_does_not_inherit_credentials(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'secret', 'HTTPS_PROXY': 'secret'}):
            env = coding.worker_environment(Path('/private/tmp/job'))
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertNotIn('HTTPS_PROXY', env)
        self.assertTrue(env['HOME'].startswith('/private/tmp/job/work/'))
        config = json.loads(env['OPENCODE_CONFIG_CONTENT'])
        self.assertEqual(config['model'], 'local/qwen2.5:7b')
        self.assertEqual(config['provider']['local']['models']['qwen2.5:7b']['limit']['output'], 1200)

    def test_running_process_cancel_and_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            job = Path(d).resolve(); (job / 'work').mkdir()
            cancel = threading.Event()
            timer = threading.Timer(0.15, cancel.set); timer.start()
            try:
                with self.assertRaises(Cancelled):
                    coding.run_bounded([sys.executable, '-I', '-c', 'import time;time.sleep(30)'], job, {}, cancel, job / 'cancel.log')
            finally: timer.join()
            with self.assertRaises(TimeoutError):
                coding.run_bounded([sys.executable, '-I', '-c', 'import time;time.sleep(30)'], job, {}, threading.Event(), job / 'timeout.log', 0.1)

    def test_verifier_rejects_tampered_result_artifact_and_log(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve(); job = root / ('jarvis-code-' + 'a' * 32)
            control = job / 'control'; control.mkdir(parents=True)
            log = (json.dumps({'type':'text','part':{'text':HTML.decode()}}) + '\n').encode()
            result = {'job':job.name,'filename':job.name+'/control/index.html',
                      'sha256':hashlib.sha256(HTML).hexdigest(),
                      'worker_log_sha256':hashlib.sha256(log).hexdigest(),'sandbox_preflight':True}
            (control/'index.html').write_bytes(HTML); (control/'worker.log').write_bytes(log)
            (control/'probe.log').write_bytes(b'SANDBOX_PROBE_OK')
            (control/'result.json').write_text(json.dumps(result))
            self.assertTrue(coding.verify_coding('coding.build',result,root))
            with self.assertRaises(ValueError): coding.verify_coding('coding.build',dict(result,sha256='forged'),root)
            (control/'index.html').write_bytes(HTML+b'changed')
            with self.assertRaises(ValueError): coding.verify_coding('coding.build',result,root)
            (control/'index.html').unlink(); (control/'index.html').symlink_to(control/'worker.log')
            with self.assertRaises(OSError): coding.verify_coding('coding.build',result,root)

    def test_failed_preflight_never_launches_worker(self):
        with tempfile.TemporaryDirectory() as d, patch.object(coding, '_preflight', side_effect=RuntimeError('sandbox denied')), patch.object(coding, 'run_bounded') as run:
            with self.assertRaisesRegex(RuntimeError, 'sandbox denied'):
                coding.execute_coding('coding.build','build demo app',Path(d).resolve(),threading.Event())
            run.assert_not_called()
