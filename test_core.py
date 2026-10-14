import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from core import RankResult, normalize_domain, matches
from scraper import GoogleBrowserProvider
from google_parser import destination
from storage import History, comparison

class Page:
    url = 'https://www.google.com/search'
    def goto(self, *args, **kwargs): pass
    def wait_for_timeout(self, *args): pass

class Tests(unittest.TestCase):
    def test_domains(self):
        self.assertEqual(normalize_domain('https://www.Example.com/path'), 'example.com')
        self.assertTrue(matches('https://blog.example.com/a', 'example.com'))
        self.assertFalse(matches('https://example.com.evil.org/a', 'example.com'))
    def test_redirect(self):
        self.assertEqual(destination('https://www.google.com/url?q=https%3A%2F%2Fexample.com'), 'https://example.com')
        self.assertEqual(destination('https://www.google.com/search?q=test'), '')
    def test_depth_and_incomplete(self):
        provider = GoogleBrowserProvider()
        provider.page = Page()
        provider.read_results = lambda: [f'https://other.org/{i}' for i in range(60)]
        with patch('scraper.is_challenge', return_value=False):
            result = provider.check('example.com', 'us', 'en', 'test', threading.Event(), 50)
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.depth, 50)
        provider.read_results = lambda: []
        with patch('scraper.is_challenge', return_value=False):
            result = provider.check('example.com', 'us', 'en', 'test', threading.Event(), 100)
        self.assertEqual(result.status, 'incomplete')
    def test_cancel(self):
        cancel = threading.Event(); cancel.set()
        result = GoogleBrowserProvider().check('example.com', 'us', 'en', 'test', cancel)
        self.assertEqual(result.status, 'cancelled')
    def test_history(self):
        with tempfile.TemporaryDirectory() as directory:
            history = History(Path(directory) / 'test.sqlite3')
            result = RankResult('example.com', 'us', 'en', 'test', '2026-10-14', position=37)
            self.assertIsNone(history.previous(result))
            history.save(result)
            result.position = 20
            self.assertEqual(comparison(result, history.previous(result)), ('37', '↑ 17'))
            result.country = 'gb'
            self.assertIsNone(history.previous(result))

if __name__ == '__main__': unittest.main()
