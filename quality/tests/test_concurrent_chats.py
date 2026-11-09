import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


class ConcurrentChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import httpx
        except ImportError:
            raise unittest.SkipTest('Gemini dependencies are installed in its service image')
        cls.previous_path = list(sys.path)
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'integrations'))

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'previous_path'):
            sys.path[:] = cls.previous_path

    def setUp(self):
        from gemini_web2api.account_pool import AccountPool
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.pool = AccountPool(self.folder.name, threading.RLock())
        self.entries = [{'id': value * 32, 'label': value} for value in ('a', 'b')]
        self.pool.store.registry_path.write_text(json.dumps({'accounts': self.entries}))
        for number, entry in enumerate(self.entries):
            path = self.pool.store.path(entry['id'])
            path.parent.mkdir(parents=True)
            path.with_name('cookie.txt').write_text('SAPISID=' + entry['label'])
            path.write_text(json.dumps({'model_checked_at': 10**12, 'xsrf_token': entry['label'],
                'cookie_file': str(path.with_name('cookie.txt')),
                'extra_models': {'gemini-3.1-pro': {'mode': number + 3, 'think': 1}},
                'model_headers': {str(number + 3): {'x-goog-ext-525001261-jspb': '[1]'}}}))
        for name in ('maintain', 'refresh'):
            mock = patch('gemini_web2api.account_pool.GoogleSession.' + name)
            mock.start()
            self.addCleanup(mock.stop)

    def test_two_chats_use_distinct_accounts_then_release_slots_and_continue_same_cid(self):
        from gemini_web2api.config import CONFIG
        from gemini_web2api.gemini import load_cookie, _build_payload
        from gemini_web2api.chat_retention import ChatRetention
        from gemini_web2api.quota_guard import QuotaRejected
        from urllib.parse import parse_qs
        entered = [threading.Event(), threading.Event()]
        release = threading.Event()
        results, errors, profiles = {}, [], {}
        def run(index):
            def generate(mode, level):
                before = (CONFIG['xsrf_token'], load_cookie()[0])
                ChatRetention(CONFIG['audit_config_path']).update_session('chat-' + str(index), 'c_' + str(index), token='token-' + str(index))
                profiles[index] = before
                entered[index].set()
                if not release.wait(3):
                    raise TimeoutError()
                self.assertEqual((CONFIG['xsrf_token'], load_cookie()[0]), before)
                return 'answer'
            try:
                results[index] = self.pool.run_chat(generate, 'gemini-3.1-pro', 'chat-' + str(index))
            except Exception as error:
                errors.append(error)
        threads = [threading.Thread(target=run, args=(index,)) for index in (0, 1)]
        try:
            threads[0].start()
            self.assertTrue(entered[0].wait(2))
            threads[1].start()
            self.assertTrue(entered[1].wait(2))
            self.assertNotEqual(profiles[0], profiles[1])
            with self.assertRaises(QuotaRejected) as busy:
                self.pool.run_chat(lambda *args: 'wrong', 'gemini-3.1-pro', 'third')
            self.assertEqual(busy.exception.code, 'accounts_busy')
            with self.assertRaises(QuotaRejected) as same:
                self.pool.run_chat(lambda *args: 'wrong', 'gemini-3.1-pro', 'chat-0')
            self.assertEqual(same.exception.code, 'conversation_busy')
        finally:
            release.set()
            for thread in threads:
                if thread.ident:
                    thread.join(3)
        self.assertFalse(errors, errors)
        self.assertEqual(len(results), 2)
        def continuation(mode, level):
            self.assertEqual(CONFIG['xsrf_token'], profiles[1][0])
            payload = json.loads(json.loads(parse_qs(_build_payload('next', mode, level))['f.req'][0])[1])
            self.assertEqual(payload[71][0], 'c_1')
            self.assertEqual(payload[71][7], 'token-1')
            return 'continued'
        self.assertEqual(self.pool.run_chat(continuation, 'gemini-3.1-pro', 'chat-1'), 'continued')
        self.assertEqual(self.pool.run_chat(lambda *args: 'new', 'gemini-3.1-pro', 'new-chat'), 'new')

    def test_exception_releases_lease_and_does_not_move_an_existing_chat(self):
        from gemini_web2api.chat_retention import ChatRetention
        from gemini_web2api.config import CONFIG
        from gemini_web2api.quota_guard import QuotaRejected
        path = self.pool.store.path(self.entries[0]['id'])
        ChatRetention(path).update_session('pinned', 'c_existing')
        used = []
        def fail(*args):
            used.append(CONFIG['xsrf_token'])
            raise TimeoutError()
        with self.assertRaises(QuotaRejected):
            self.pool.run_chat(fail, 'gemini-3.1-pro', 'pinned')
        self.assertEqual(used, ['a'])
        self.assertEqual(self.pool.run_chat(lambda *args: 'ready', 'gemini-3.1-pro', 'new'), 'ready')
