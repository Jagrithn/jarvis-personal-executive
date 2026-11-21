import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/executive'))
from browser import research_query, research_chrome, read_chrome_results, research_articles
from policy import route


class ResearchTests(unittest.TestCase):
    def test_natural_requests_and_negation(self):
        for text in ['research black holes', 'Hey Jarvis, research black holes',
                     'Can you research about black holes?']:
            with self.subTest(text=text):
                self.assertEqual(research_query(text), 'black holes')
                self.assertEqual(route(text, True), 'browser.research')
        self.assertIsNone(research_query("don't research black holes"))
        self.assertIsNone(research_query('research black holes and send to Alice'))

    def test_research_opens_then_reads_same_tab(self):
        event = threading.Event()
        url = 'https://www.google.com/search?q=black+holes'
        with patch('browser.search_chrome', return_value=({'url':url}, [{'check':'opened'}])), \
             patch('browser.read_chrome_results', return_value={'url':url, 'text':'result ' * 30}) as read:
            page, receipts = research_chrome('research black holes', event, Path('/helper'))
            read.assert_called_once_with(event, expected_url=url)
            self.assertEqual(page['url'], url)
            self.assertEqual(len(receipts), 1)

    def test_wrong_active_tab_is_rejected(self):
        with patch('adapters.run_process', return_value='https://www.google.com/search?q=other\nSome result'):
            with self.assertRaisesRegex(ValueError, 'tab changed'):
                read_chrome_results(threading.Event(), expected_url='https://www.google.com/search?q=desired')

    def test_cancel_before_read(self):
        event = threading.Event()
        event.set()
        with patch('browser.search_chrome', return_value=({'url':'https://www.google.com/search?q=x'}, [])), \
             patch('browser.read_chrome_results') as read:
            with self.assertRaises(Exception):
                research_chrome('research x', event, Path('/helper'))
            read.assert_not_called()

    def test_articles_skip_private_and_failures_and_keep_read_sources(self):
        urls = '["http://127.0.0.1/test", "https://one.example/a", "https://two.example/b"]'
        article = {'source_url': 'https://two.example/b', 'text': 'article ' * 50}
        with patch('adapters.run_process', return_value=urls), \
             patch('browser.execute_browser', side_effect=[ValueError('blocked'), article]) as reader:
            result = research_articles({'url':'https://www.google.com/search?q=x'}, Path('/tmp/workspace'), threading.Event())
        self.assertEqual(result, [article])
        self.assertEqual(reader.call_count, 2)

    def test_no_readable_articles_reports_failure(self):
        with patch('adapters.run_process', return_value='["http://127.0.0.1/"]'):
            with self.assertRaisesRegex(ValueError, 'no result articles'):
                research_articles({'url':'https://www.google.com/search?q=x'}, Path('/tmp/workspace'), threading.Event())
