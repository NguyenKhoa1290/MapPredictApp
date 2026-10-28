import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch


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

    def test_admin_snapshot_returns_verified_email_and_server_schedule_without_secrets(self):
        path = self.pool.store.path('a' * 32)
        settings = json.loads(path.read_text())
        settings.update(email='verified@example.test', session_checked_at=100, session_rotated_at=90)
        path.write_text(json.dumps(settings))
        reply = self.pool.snapshot()
        self.assertEqual(reply['accounts'][0]['email'], 'verified@example.test')
        self.assertEqual(reply['accounts'][0]['rotated_at'], 90)
        self.assertEqual(reply['maintenance'], {'poll_interval_seconds': 30, 'rotate_interval_seconds': 43200, 'repair_cooldown_seconds': 300})
        self.assertNotIn('verified-test-xsrf', json.dumps(reply))
        self.assertNotIn('private-cookie', json.dumps(reply))
        self.assertNotIn('model_headers', json.dumps(reply))

    def test_manual_refresh_rotates_each_profile_and_keeps_revoked_login_visible(self):
        from gemini_web2api.google_session import UsageAuthError
        with patch('gemini_web2api.account_pool.GoogleSession') as sessions, \
                patch.object(self.pool.store, 'scan_one', return_value={'status': 'ready', 'usage': {}, 'model_available': True}) as scan:
            sessions.return_value.refresh.side_effect = [None, UsageAuthError('private-cookie-secret')]
            reply = self.pool.refresh()
        self.assertEqual(sessions.call_count, 2)
        self.assertTrue(all(call.kwargs == {'rotate': True} for call in sessions.return_value.refresh.call_args_list))
        self.assertEqual(scan.call_count, 1)
        self.assertCountEqual([row['status'] for row in reply['accounts']], ['ready', 'needs_login'])
        self.assertNotIn('private-cookie-secret', json.dumps(reply))

    def test_background_scan_respects_cached_model_discovery(self):
        with patch.object(self.pool.store, 'scan_one', return_value={'status': 'ready', 'usage': {}}) as scan:
            self.pool.scan(discover=False)
        self.assertEqual(scan.call_count, 2)
        self.assertTrue(all(call.kwargs == {'discover': False} for call in scan.call_args_list))

    def test_cookie_update_targets_one_account_preserves_verified_email_and_account_index(self):
        for index, entry in enumerate(self.pool.store.registry()['accounts']):
            path = self.pool.store.path(entry['id'])
            cookie = path.with_name('cookie.txt')
            cookie.write_text(f'SID=sid; SAPISID=sapi; __Secure-1PSID=old-{index}')
            settings = json.loads(path.read_text())
            settings.update(cookie_file=str(cookie), email=f'user{index}@example.test', auth_user=str(index))
            path.write_text(json.dumps(settings))
        with patch('gemini_web2api.google_session.GoogleSession.page', return_value={'oPEP7c': 'user0@example.test'}), \
                patch.object(self.pool.store, 'scan_one', return_value={'status': 'ready', 'usage': {}}):
            reply = self.pool.import_cookie('SID=new; SAPISID=new; __Secure-1PSID=new', 'One', account_id='a' * 32)
        settings = json.loads(self.pool.store.path('a' * 32).read_text())
        self.assertEqual(settings['auth_user'], '0')
        self.assertEqual(reply['accounts'][0]['email'], 'user0@example.test')
        self.assertNotIn('xsrf_token', settings)
        self.assertIn('old-1', self.pool.store.path('b' * 32).with_name('cookie.txt').read_text())

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

    def test_chat_effort_reaches_generation_for_both_routes_without_downgrade(self):
        import importlib.util
        import gemini_web2api
        spec = importlib.util.spec_from_file_location('effort_test_runner',
                    Path(gemini_web2api.__file__).resolve().parent.parent / 'run_gemini.py')
        runner = importlib.util.module_from_spec(spec)
        with patch('pathlib.Path.read_text', return_value='test-internal-key'), \
                patch('gemini_web2api.session_manager.SessionManager'), \
                patch('gemini_web2api.account_pool.AccountPool'):
            spec.loader.exec_module(runner)
        runner.pool.run.side_effect = lambda callback: callback(71, 4)
        handler = object.__new__(runner.ManagedGeminiHandler)
        handler.send_json = Mock()
        for model, mode in (('gemini-3.6-flash', 1), ('gemini-4-argon', 71)):
            for effort, depth in ((None, 4), ('low', 4), ('medium', 2), ('high', 0)):
                with self.subTest(model=model, effort=effort):
                    handler.send_json.reset_mock()
                    body = {'model': model, 'messages': [{'role': 'user', 'content': 'hello'}]}
                    if effort is not None:
                        body['reasoning_effort'] = effort
                    with patch('gemini_web2api.server.generate', return_value='fast') as fast, \
                            patch.object(runner, 'generate', return_value='smart') as smart:
                        handler._handle_chat(json.dumps(body).encode())
                    called, untouched = (smart, fast) if model == 'gemini-4-argon' else (fast, smart)
                    self.assertEqual(called.call_args.args[1:3], (mode, depth))
                    untouched.assert_not_called()
                    self.assertEqual(handler.send_json.call_args.args[0]['model'], model)
            with patch('gemini_web2api.server.generate') as fast, patch.object(runner, 'generate') as smart:
                handler._handle_chat(json.dumps({'model': model, 'reasoning_effort': 'invalid'}).encode())
                self.assertEqual(handler.send_json.call_args.args[1], 400)
                fast.assert_not_called()
                smart.assert_not_called()

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
