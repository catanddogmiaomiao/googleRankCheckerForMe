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
    def test_loaded_results_resume_without_challenge_check(self):
        provider = GoogleBrowserProvider()
        provider.page = Page()
        provider.scroll_results = lambda cancel: None
        provider.diagnostics = lambda reason: None
        provider.page.is_closed = lambda: False
        provider.read_results = lambda: ['https://example.com']
        with patch('scraper.is_challenge', side_effect=AssertionError('stale iframe')):
            self.assertEqual(provider.wait_for_results(threading.Event()), (['https://example.com'], 'ok'))

    def test_pagination_after_first_page(self):
        provider = GoogleBrowserProvider()
        provider.page = Page()
        provider.scroll_results = lambda cancel: None
        provider.diagnostics = lambda reason: None
        provider.read_results = lambda: []
        provider.page.goto = lambda target, **kwargs: setattr(provider.page, 'url', target)
        cancel = threading.Event()
        with patch.object(provider, 'wait_for_results', side_effect=[
                (['https://other.org/1'], 'ok'), (['https://example.com'], 'ok')]), \
                patch('scraper.click_next', side_effect=lambda page: (setattr(page, 'url', 'https://www.google.com/search?q=test&start=10') or True)), \
                patch('scraper.random.uniform', return_value=0):
            result = provider.check('example.com', 'us', 'en', 'test', cancel)
        self.assertEqual(result.position, 2)
        self.assertIn('start=10', provider.page.url)

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
        provider.scroll_results = lambda cancel: None
        provider.diagnostics = lambda reason: None
        provider.read_results = lambda: [f'https://other.org/{i}' for i in range(60)]
        with patch.object(provider, 'wait_for_results', return_value=(provider.read_results(), 'ok')):
            result = provider.check('example.com', 'us', 'en', 'test', threading.Event(), 50)
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.depth, 50)
        provider.read_results = lambda: []
        with patch.object(provider, 'wait_for_results', return_value=(provider.read_results(), 'ok')):
            result = provider.check('example.com', 'us', 'en', 'test', threading.Event(), 100)
        self.assertEqual(result.status, 'parse_error')
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
