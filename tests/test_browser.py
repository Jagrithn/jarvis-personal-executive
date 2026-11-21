import hashlib
import importlib.util
import http.server
import pathlib
import socket
import sys
import threading
import tempfile
import json
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'services/executive'))
import browser

class BrowserTests(unittest.TestCase):
    def test_rejects_non_public_and_ambiguous_urls(self):
        for url in ['file:///etc/passwd', 'http://localhost/', 'http://127.0.0.1/',
                    'http://10.0.0.1/', 'http://224.0.0.1/', 'http://[ff02::1]/', 'http://169.254.169.254/', 'http://[::1]/',
                    'http://[::ffff:127.0.0.1]/', 'http://user:pass@example.com/',
                    'http://example.com:8080/', 'http://example.com/\nHeader:x']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                browser.validate_url(url)

    def test_dns_mixed_public_private_is_rejected(self):
        records = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443)),
                   (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]
        with patch('browser.socket.getaddrinfo', return_value=records), self.assertRaises(ValueError):
            browser.public_addresses('https://example.com/')

    def test_redirect_private_target_is_rejected(self):
        with patch('browser.fetch_once', return_value=(302, {'location': 'http://127.0.0.1/'}, b'')):
            with self.assertRaises(ValueError):
                browser.fetch_document('https://example.com/')

    def test_rejects_download_and_excessive_body(self):
        for headers, body in [({'content-type': 'application/octet-stream'}, b'x'),
                              ({'content-type': 'text/html', 'content-disposition': 'attachment'}, b'x'),
                              ({'content-type': 'text/html'}, b'x' * (browser.MAX_BYTES + 1))]:
            with patch('browser.fetch_once', return_value=(200, headers, body)), self.assertRaises(ValueError):
                browser.fetch_document('https://example.com/')

    def test_verification_detects_text_tamper(self):
        result = {'source_url': 'https://example.com/', 'title': 'Example', 'text': 'hello',
                  'sha256': hashlib.sha256(b'hello').hexdigest(), 'scope': 'public-read',
                  'status': 200, 'truncated': False}
        self.assertTrue(browser.verify_browser('browser.read', result, None))
        result['text'] = 'changed'
        with self.assertRaises(ValueError):
            browser.verify_browser('browser.read', result, None)

    def test_packaged_module_uses_workspace_project_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            project = pathlib.Path(directory)
            runtime = project / '.runtime/browser/bin/python'
            runtime.parent.mkdir(parents=True)
            runtime.touch()
            root = project / 'data/workspace'
            result = {'source_url': 'https://example.com/', 'title': 'Example', 'text': 'hello',
                      'sha256': hashlib.sha256(b'hello').hexdigest(), 'scope': 'public-read',
                      'status': 200, 'truncated': False}
            def process(args, cancel, timeout):
                self.assertEqual(args[0], str(runtime))
                self.assertEqual(args[-2:], ['--project', str(project)])
                return json.dumps(result)
            with patch('adapters.run_process', side_effect=process):
                observed = browser.execute_browser('browser.read', 'read page: https://example.com/', root, threading.Event())
            self.assertEqual(observed['text'], 'hello')

    def test_capability_and_command_are_bounded(self):
        for capability, command in [('browser.click', 'read page: https://example.com/'),
                                    ('browser.read', 'click https://example.com/')]:
            with self.assertRaises(ValueError):
                browser.execute_browser(capability, command, None, threading.Event())

@unittest.skipUnless(importlib.util.find_spec('playwright'), 'isolated browser runtime required')
class BrowserRenderingTests(unittest.TestCase):
    def test_fixture_blocks_script_and_private_subresources(self):
        hits = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                self.send_response(200)
                self.end_headers()
            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = ('<html><head><title>Reader fixture</title></head><body>Hello fixture'
                    '<script>document.body.innerText="unsafe script ran"</script>'
                    '<img src="http://127.0.0.1:%s/private">'
                    '<iframe src="http://127.0.0.1:%s/frame"></iframe></body></html>' %
                    (server.server_port, server.server_port)).encode()
            result = browser.render_document('https://example.com', 'text/html', body)
            self.assertEqual(result['title'], 'Reader fixture')
            self.assertEqual(result['text'], 'Hello fixture')
            self.assertEqual(hits, [])
            self.assertTrue(browser.verify_browser('browser.read', result, None))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

if __name__ == '__main__':
    unittest.main()
