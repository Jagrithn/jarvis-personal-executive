import hashlib
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/executive'))
from policy import route
from server import Executive
from workflows import research_report_topic, verify_research_report


class ResearchWorkflowTests(unittest.TestCase):
    def test_routing_keeps_browser_research_separate(self):
        self.assertEqual(research_report_topic('Hey Jarvis, research black holes and save a report'), 'black holes')
        self.assertEqual(route('research black holes and save a report', True), 'workflows.research')
        self.assertEqual(route('research black holes', True), 'browser.research')
        self.assertIsNone(research_report_topic("don't research black holes and save a report"))

    def test_research_to_verified_local_report(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory).resolve()
            text = 'A public article about black holes. ' * 12
            article = {'source_url': 'https://example.com/black-holes', 'title': 'Black holes',
                       'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest(),
                       'scope': 'public-read', 'status': 200}
            engine = Executive(data, Path('/unused'))
            try:
                with patch('browser.research_chrome', return_value=({'url': 'https://www.google.com/search?q=black+holes'}, [{'check': 'search tab'}])), \
                     patch('browser.research_articles', return_value=[article]), \
                     patch('server.execute_knowledge', return_value={'answer': 'Black holes have strong gravity.'}):
                    task = engine.submit({'command': 'research black holes and save a report'})
                    for _ in range(300):
                        current = engine.tasks[task['id']]
                        if current['state'] not in {'queued', 'running'}:
                            break
                        time.sleep(.01)
                self.assertEqual(current['state'], 'succeeded', current.get('error'))
                report = data / 'workspace' / current['result']['filename']
                self.assertIn('Black holes have strong gravity.', report.read_text())
                self.assertIn('https://example.com/black-holes', report.read_text())
                self.assertTrue(any(item.get('check') == 'independent research report bytes and source receipts'
                                    for item in current['evidence']))
                report.write_text('tampered')
                with self.assertRaises(RuntimeError):
                    verify_research_report(current['result'], data / 'workspace')
            finally:
                engine.close()
