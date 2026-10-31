import concurrent.futures
import json
import pathlib
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'services/executive'))
from server import Executive, Server
from policy import route, authorize
from adapters import execute, Cancelled
from verification import verify

class ExecutiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = pathlib.Path(self.temp.name).resolve()
        self.engine = Executive(self.data, pathlib.Path('/missing-helper'))
    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()
    def wait(self, task):
        for _ in range(200):
            with self.engine.lock:
                current = self.engine.snapshot(self.engine.tasks[task['id']])
            if current['state'] not in {'queued', 'running'}:
                return current
            time.sleep(.01)
        self.fail('Task did not finish')
    def test_routing_and_unsupported_commands(self):
        self.assertEqual(route('  OPEN Calculator. '), 'apps.calculator')
        result = self.engine.submit({'command': 'delete everything'})
        self.assertEqual(result['state'], 'failed')
        self.assertIsNone(result['result'])
    def test_request_validation(self):
        for body in ([], {}, {'command': 2}, {'command': ''}, {'command': 'x' * 501}, {'command': 'list files', 'shell': 'ls'}, {'command': 'list files', 'path': 3}):
            with self.assertRaises(ValueError):
                self.engine.submit(body)
    def test_path_rejection(self):
        for path in ('../outside', '/etc', str(self.data / 'outside')):
            task = self.engine.submit({'command': 'list files', 'path': path})
            self.assertEqual(task['state'], 'failed')
            self.assertIn('reject', task['error'].lower())
    def test_symlink_rejection(self):
        (self.engine.root / 'escape').symlink_to('/tmp')
        with self.assertRaises(ValueError):
            authorize(self.engine.root, 'files.list', 'escape')
        self.engine.root.rename(self.data / 'original')
        self.engine.root.symlink_to(self.data / 'original')
        with self.assertRaises(ValueError):
            authorize(self.engine.root, 'files.list')
    def test_create_list_and_evidence(self):
        created = self.wait(self.engine.submit({'command': 'create sample file'}))
        self.assertEqual(created['state'], 'succeeded')
        self.assertEqual(created['events'][-1]['state'], 'succeeded')
        self.assertTrue(created['evidence'][0]['sha256'])
        listed = self.wait(self.engine.submit({'command': 'list files'}))
        self.assertIn(created['result']['filename'], listed['result']['entries'])
    def test_no_overwrite(self):
        from unittest.mock import patch
        (self.engine.root / 'sample-fixed.txt').write_text('preserve')
        with patch('adapters.uuid.uuid4', return_value='fixed'):
            task = self.wait(self.engine.submit({'command': 'create sample file'}))
        self.assertEqual(task['state'], 'failed')
        self.assertEqual((self.engine.root / 'sample-fixed.txt').read_text(), 'preserve')
    def test_verification_failure_preserves_effect(self):
        def reject(*args):
            raise RuntimeError('Read-back failed')
        self.engine.checker = reject
        task = self.wait(self.engine.submit({'command': 'create sample file'}))
        self.assertEqual(task['state'], 'failed')
        self.assertTrue((self.engine.root / task['result']['filename']).exists())
        self.assertFalse(task['evidence'])
    def test_restart_and_interrupted_recovery(self):
        task = self.wait(self.engine.submit({'command': 'list files'}))
        broken = dict(task, id='interrupted-example', state='running')
        self.engine.store.save(broken)
        self.engine.close()
        self.engine = Executive(self.data, pathlib.Path('/missing'))
        self.assertEqual(self.engine.tasks[task['id']]['state'], 'succeeded')
        self.assertEqual(self.engine.tasks['interrupted-example']['state'], 'interrupted')
    def test_cancel_and_stop_resume(self):
        started = threading.Event()
        def blocking(capability, root, cancelled, helper):
            started.set()
            if cancelled.wait(2):
                raise Cancelled('Stopped; no effect')
            raise RuntimeError('Timeout')
        self.engine.executor = blocking
        running = self.engine.submit({'command': 'list files'})
        self.assertTrue(started.wait(1))
        queued = self.engine.submit({'command': 'list files'})
        self.engine.stop()
        self.assertEqual(self.wait(running)['state'], 'cancelled')
        self.assertEqual(self.wait(queued)['state'], 'cancelled')
        with self.assertRaises(ValueError):
            self.engine.submit({'command': 'list files'})
        self.engine.paused = False
        self.engine.executor = execute
        self.assertEqual(self.wait(self.engine.submit({'command': 'list files'}))['state'], 'succeeded')
    def test_concurrent_submissions(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            tasks = list(pool.map(lambda _: self.engine.submit({'command': 'create sample file'}), range(12)))
        results = [self.wait(t) for t in tasks]
        self.assertTrue(all(t['state'] == 'succeeded' for t in results))
        self.assertEqual(len({t['result']['filename'] for t in results}), 12)

class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = Executive(pathlib.Path(self.temp.name).resolve(), pathlib.Path('/missing'))
        self.server = Server(self.engine, 'a' * 64)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.engine.close()
        self.temp.cleanup()
    def call(self, path, body=None, token='a' * 64, extra=None):
        headers = {'Authorization': 'Bearer ' + token, **(extra or {})}
        req = urllib.request.Request(self.url + path, headers=headers, data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.load(error)
    def test_auth_origin_host_and_routes(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        for path in ['/v1/health', '/v1/capabilities', '/v1/tasks', '/v1/tasks/missing']:
            self.assertEqual(self.call(path, token='wrong')[0], 401)
        for path in ['/v1/tasks', '/v1/stop-all', '/v1/resume', '/v1/shutdown']:
            self.assertEqual(self.call(path, {}, token='wrong')[0], 401)
        self.assertEqual(self.call('/v1/health', extra={'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.call('/v1/health', extra={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.call('/v1/health')[1]['status'], 'ok')
        self.assertEqual(len(self.call('/v1/capabilities')[1]), 4)
        self.assertEqual(self.call('/v1/nope')[0], 404)
    def test_task_and_control_endpoints(self):
        code, task = self.call('/v1/tasks', {'command': 'list files'})
        self.assertEqual(code, 200)
        self.assertEqual(self.call('/v1/tasks/' + task['id'])[1]['id'], task['id'])
        self.assertEqual(len(self.call('/v1/tasks')[1]), 1)
        self.assertEqual(self.call('/v1/tasks/' + task['id'] + '/cancel', {})[0], 200)
        self.assertTrue(self.call('/v1/stop-all', {})[1]['paused'])
        self.assertEqual(self.call('/v1/tasks', {'command': 'list files'})[0], 400)
        self.assertFalse(self.call('/v1/resume', {})[1]['paused'])
        self.assertEqual(self.call('/v1/tasks', {'command': []})[0], 400)
        self.assertEqual(self.call('/v1/tasks/missing')[0], 404)

if __name__ == '__main__':
    unittest.main()
