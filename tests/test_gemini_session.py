import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import contextlib


class GeminiSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import httpx
        except ImportError:
            raise unittest.SkipTest('Session adapter dependency is installed in its own Docker image')
        import sys
        cls.previous = list(sys.path)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integrations'))
        from gemini_web2api.session_manager import SessionManager
        cls.manager_type = SessionManager

    @classmethod
    def tearDownClass(cls):
        import sys
        if hasattr(cls, 'previous'):
            sys.path[:] = cls.previous

    def test_import_and_refresh_never_return_secrets_and_portable_lock_works(self):
        from gemini_web2api.google_session import private_lock
        with tempfile.TemporaryDirectory() as folder:
            manager = self.manager_type(folder)
            self.assertEqual(manager.status()['state'], 'not_configured')
            with private_lock(Path(folder) / 'test.lock'):
                pass
            with patch.object(manager, 'refresh', return_value={'state': 'ready'}):
                reply = manager.import_cookie('SID=secret1; SAPISID=secret2; __Secure-1PSID=secret3')
            self.assertEqual(reply, {'state': 'ready'})
            self.assertNotIn('secret', str(manager.status()))
            with patch.object(manager.session, 'refresh', side_effect=RuntimeError('cookie-secret')):
                reply = manager.refresh(rotate=True)
            self.assertEqual(reply['state'], 'needs_attention')
            self.assertNotIn('cookie-secret', str(reply))
            self.assertTrue(manager.cookie.exists())

    def test_invalid_cookie_cannot_replace_existing_session(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = self.manager_type(folder)
            with self.assertRaises(ValueError):
                manager.import_cookie('SID=missing-required-cookies')
            self.assertFalse(manager.path.exists())
            with self.assertRaises(ValueError):
                manager.import_cookie(None)

    def test_regular_page_checks_do_not_postpone_ten_minute_rotation(self):
        import httpx
        from gemini_web2api.google_session import GoogleSession
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            cookie = Path(folder) / 'cookie.txt'
            cookie.write_text('SID=one; SAPISID=two; __Secure-1PSID=three')
            path.write_text(json.dumps({'cookie_file': str(cookie), 'session_rotated_at': 1000,
                                        'session_maintenance_started_at': 1000}))
            calls = []
            def handle(request):
                calls.append(request.url.path)
                if request.url.path == '/RotateCookies':
                    return httpx.Response(200, headers={'Set-Cookie': '__Secure-1PSIDTS=new; Domain=.google.com; Path=/; Secure'})
                return httpx.Response(200, text='{"SNlM0e":"xsrf"}')
            session = GoogleSession(path)
            @contextlib.contextmanager
            def client(pairs):
                cookies = httpx.Cookies()
                for name, value in pairs.items():
                    cookies.set(name, value, domain='.google.com', path='/')
                with httpx.Client(transport=httpx.MockTransport(handle), cookies=cookies) as c:
                    yield c
            with patch.object(session, 'client', client):
                # Each successful poll is only 30 seconds before the next one.
                for now in range(1030, 1601, 30):
                    with patch('gemini_web2api.google_session.time.time', return_value=now):
                        session.maintain()
                        session.refresh()
            self.assertEqual(calls.count('/RotateCookies'), 1)
            settings = json.loads(path.read_text())
            self.assertEqual(settings['session_rotated_at'], 1600)
            self.assertEqual(settings['refresh_attempt_at'], 1600)

    def test_rotated_cookie_survives_failed_followup_page(self):
        import httpx
        from gemini_web2api.google_session import GoogleSession
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            cookie = Path(folder) / 'cookie.txt'
            original = 'SID=one; SAPISID=two; __Secure-1PSID=three; __Secure-1PSIDTS=old'
            cookie.write_text(original)
            path.write_text(json.dumps({'cookie_file': str(cookie)}))
            def handle(request):
                if request.url.path == '/RotateCookies':
                    return httpx.Response(200, headers={'Set-Cookie': '__Secure-1PSIDTS=new; Domain=.google.com; Path=/; Secure'})
                return httpx.Response(503)
            session = GoogleSession(path)
            @contextlib.contextmanager
            def client(pairs):
                cookies = httpx.Cookies()
                for name, value in pairs.items():
                    cookies.set(name, value, domain='.google.com', path='/')
                with httpx.Client(transport=httpx.MockTransport(handle), cookies=cookies) as c:
                    yield c
            with patch.object(session, 'client', client), self.assertRaises(httpx.HTTPStatusError):
                session.refresh(rotate=True)
            self.assertIn('__Secure-1PSIDTS=new', cookie.read_text())
            self.assertNotIn('__Secure-1PSIDTS=old', cookie.read_text())
            self.assertNotIn('session_rotated_at', json.loads(path.read_text()))

    def test_inflight_rotation_cannot_replace_manual_cookie_update(self):
        import httpx
        from gemini_web2api.google_session import GoogleSession
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            cookie = Path(folder) / 'cookie.txt'
            cookie.write_text('SID=manual; SAPISID=two; __Secure-1PSID=three')
            path.write_text(json.dumps({'cookie_file': str(cookie)}))
            with httpx.Client(cookies={'SID': 'stale'}) as client:
                result = GoogleSession(path).persist({}, cookie, 'SID=old', client)
            self.assertIsNone(result)
            self.assertIn('SID=manual', cookie.read_text())
