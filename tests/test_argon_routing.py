import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


class ArgonRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import httpx
        except ImportError:
            raise unittest.SkipTest('Gemini dependencies are installed in the Gemini image')
        cls.previous = list(sys.path)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integrations'))
        from gemini_web2api.account_pool import AccountPool
        cls.pool_type = AccountPool

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'previous'):
            sys.path[:] = cls.previous

    def setUp(self):
        from gemini_web2api.config import CONFIG
        self.previous_config = dict(CONFIG)
        self.addCleanup(lambda: (CONFIG.clear(), CONFIG.update(self.previous_config)))
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.pool = self.pool_type(self.folder.name, threading.RLock())
        entries = [{'id': 'a' * 32, 'label': 'One'}, {'id': 'b' * 32, 'label': 'Two'}]
        self.pool.store.registry_path.write_text(json.dumps({'accounts': entries}))
        for index, entry in enumerate(entries):
            path = self.pool.store.path(entry['id'])
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'model_checked_at': 10**12, 'model_available': True,
                'xsrf_token': 'verified-test-xsrf', 'cookie_file': 'private-cookie-' + str(index),
                'extra_models': {'gemini-4-argon': {'mode': 71 + index, 'think': 4}},
                'model_headers': {str(71 + index): {'x-goog-ext-525001261-jspb': '[1]'}}}))

    def test_exhausted_account_switches_to_same_model_on_next_account(self):
        from gemini_web2api.quota_guard import QuotaRejected
        from gemini_web2api.config import CONFIG
        original = CONFIG.get('cookie_file')
        seen = []
        def generate(mode, think):
            seen.append((mode, CONFIG['cookie_file']))
            return 'verified argon response'
        with patch('gemini_web2api.account_pool.QuotaGuard.check', side_effect=[QuotaRejected('limit'), {}, {}]):
            result = self.pool.run(generate)
        self.assertEqual(result, 'verified argon response')
        self.assertEqual(seen, [(72, 'private-cookie-1')])
        self.assertEqual(CONFIG.get('cookie_file'), original)

    def test_all_exhausted_or_unverified_never_generate_anonymous_answer(self):
        from gemini_web2api.quota_guard import QuotaRejected
        for error, expected in ((QuotaRejected('limit'), 'quota_exhausted'),
                                (QuotaRejected('unknown', status=503, code='quota_unverified'), 'quota_unverified')):
            with patch('gemini_web2api.account_pool.QuotaGuard.check', side_effect=error), \
                    patch('gemini_web2api.gemini.generate') as generate:
                with self.assertRaises(QuotaRejected) as result:
                    self.pool.run(generate)
                self.assertEqual(result.exception.code, expected)
                generate.assert_not_called()

    def test_post_generation_limit_discards_answer_and_tries_next_account(self):
        from gemini_web2api.quota_guard import QuotaRejected
        seen = []
        with patch('gemini_web2api.account_pool.QuotaGuard.check', side_effect=[{}, QuotaRejected('limit'), {}, {}]):
            result = self.pool.run(lambda mode, think: seen.append(mode) or str(mode))
        self.assertEqual(seen, [71, 72])
        self.assertEqual(result, '72')

    def test_unverified_model_route_cannot_generate(self):
        from gemini_web2api.quota_guard import QuotaRejected
        for entry in self.pool.store.registry()['accounts']:
            path = self.pool.store.path(entry['id'])
            settings = json.loads(path.read_text())
            settings['model_available'] = False
            path.write_text(json.dumps(settings))
        with patch('gemini_web2api.account_pool.QuotaGuard.check', return_value={}), \
                patch('gemini_web2api.gemini.generate') as generate:
            with self.assertRaises(QuotaRejected):
                self.pool.run(generate)
            generate.assert_not_called()

    def test_unknown_model_never_falls_back_to_flash(self):
        from gemini_web2api.models import resolve_model
        self.assertIsNotNone(resolve_model('unknown-pro-model')[3])
        self.assertIsNotNone(resolve_model('gemini-4-argon')[3])

    def test_quota_requires_both_finite_windows(self):
        from gemini_web2api.quota_guard import QuotaGuard, QuotaRejected
        from unittest.mock import Mock
        for usage in ({'current_5h': {'used_fraction': 0}}, {'current_5h': {'used_fraction': float('nan')}, 'weekly': {'used_fraction': 0}}):
            with self.assertRaises(QuotaRejected):
                QuotaGuard(Mock(fetch=lambda: usage)).check()

    def test_cookie_cache_never_crosses_account_files_with_equal_timestamps(self):
        import os
        from gemini_web2api import gemini
        from gemini_web2api.config import CONFIG
        one = Path(self.folder.name) / 'one.txt'
        two = Path(self.folder.name) / 'two.txt'
        one.write_text('SAPISID=account_one')
        two.write_text('SAPISID=account_two')
        for path in (one, two):
            os.utime(path, (10000, 10000))
        CONFIG['cookie_file'] = str(one)
        self.assertEqual(gemini.load_cookie()[1], 'account_one')
        CONFIG['cookie_file'] = str(two)
        self.assertEqual(gemini.load_cookie()[1], 'account_two')
        two.write_text('{broken json')
        self.assertEqual(gemini.load_cookie(), ('', None))

    def test_argon_header_cannot_be_sent_anonymously_even_if_cookie_read_fails(self):
        from gemini_web2api import gemini
        from gemini_web2api.config import CONFIG
        CONFIG.update(cookie_file='/not-a-cookie-file', xsrf_token='verified-token',
                      model_headers={'71': {'x-goog-ext-525001261-jspb': '[1]'}})
        with self.assertRaises(RuntimeError):
            gemini._build_headers(71)
