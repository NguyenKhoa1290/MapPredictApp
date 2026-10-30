import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


class SessionAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous = list(sys.path)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integrations'))
        try:
            from gemini_web2api import session_audit
        except ModuleNotFoundError as error:
            sys.path[:] = cls.previous
            if error.name == 'gemini_web2api':
                raise unittest.SkipTest('Session audit is tested in the dedicated Gemini image') from None
            raise
        cls.audit = session_audit

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = cls.previous

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(self.close_handlers)
        self.environment = patch.dict(os.environ, GEMINI_STATE_DIR=self.folder.name)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.profile = Path(self.folder.name) / 'accounts' / ('a' * 32) / 'config.json'
        self.profile.parent.mkdir(parents=True)
        self.log = Path(self.folder.name) / 'diagnostics/session.jsonl'

    def close_handlers(self):
        for key in list(self.audit._handlers):
            if key.startswith(self.folder.name):
                self.audit._handlers.pop(key).close()
        self.audit._recent.clear()

    def records(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_schema_excludes_secrets_raw_errors_urls_and_identity(self):
        secret = 'PRIVATE_COOKIE_TOKEN_USER@example.test'
        self.assertTrue(self.audit.emit('auth_failure', self.profile, reason='missing_xsrf',
            status=200, endpoint='gemini_page', cookie=secret, token=secret, email=secret,
            message=secret, url='https://accounts.google.com/?token=' + secret,
            error_type=secret, generation=secret, removed_auth_cookies=['SID', secret]))
        self.assertFalse(self.audit.emit(secret, self.profile))
        content = self.log.read_text()
        self.assertNotIn(secret, content)
        row = self.records()[0]
        self.assertEqual(row['account'], 'a' * 32)
        self.assertEqual(row['reason'], 'missing_xsrf')
        self.assertEqual(row['removed_auth_cookies'], ['SID'])
        self.assertTrue(row['ts_utc'].endswith('+00:00'))
        self.assertEqual(self.audit.error_type(ValueError(secret)), 'ValueError')
        if os.name != 'nt':
            self.assertEqual(self.log.stat().st_mode & 0o077, 0)

    def test_rotation_bounds_files_and_keeps_complete_json_lines(self):
        self.audit.emit('service_start')
        handler = self.audit._handlers[str(self.log)]
        handler.maxBytes, handler.backupCount = 400, 2
        for _ in range(30):
            self.audit.emit('auth_failure', self.profile, reason='missing_xsrf')
        files = list(self.log.parent.glob('session.jsonl*'))
        self.assertLessEqual(len(files), 3)
        self.assertLessEqual(sum(path.stat().st_size for path in files), 1200)
        for path in files:
            for line in path.read_text().splitlines():
                self.assertEqual(json.loads(line)['event'], 'auth_failure')
            if os.name != 'nt':
                self.assertEqual(path.stat().st_mode & 0o077, 0)

    def test_disk_error_is_nonfatal_and_routine_success_is_throttled(self):
        self.audit.emit('auth_ready', self.profile, throttle=300)
        self.assertFalse(self.audit.emit('auth_ready', self.profile, throttle=300))
        self.audit.emit('auth_failure', self.profile, reason='missing_xsrf')
        self.audit.emit('auth_failure', self.profile, reason='missing_xsrf')
        self.assertEqual(len(self.records()), 3)
        handler = self.audit._handlers[str(self.log)]
        with patch.object(handler, 'handle', side_effect=OSError('secret disk error')):
            self.assertFalse(self.audit.emit('maintenance_error', self.profile))
        self.assertTrue(self.audit.emit('maintenance_tick'))

    def make_session(self, handle):
        try:
            import httpx
        except ImportError:
            self.skipTest('HTTP session dependency is installed in Gemini image')
        from gemini_web2api.google_session import GoogleSession
        cookie = self.profile.with_name('cookie.txt')
        cookie.write_text('SID=PRIVATE_SID; SAPISID=PRIVATE_SAPISID; __Secure-1PSID=PRIVATE_PSID; __Secure-1PSIDTS=OLD_TS')
        self.profile.write_text(json.dumps({'cookie_file': str(cookie), 'email': 'private@example.test'}))
        session = GoogleSession(self.profile)
        @contextlib.contextmanager
        def client(pairs):
            cookies = httpx.Cookies()
            for name, value in pairs.items():
                cookies.set(name, value, domain='.google.com', path='/')
            with httpx.Client(transport=httpx.MockTransport(handle), cookies=cookies) as c:
                yield c
        self.enterContext(patch.object(session, 'client', client))
        return session

    def test_http_200_rotation_followed_by_google_login_is_recorded_without_secrets(self):
        try:
            import httpx
        except ImportError:
            self.skipTest('HTTP session dependency is installed in Gemini image')
        from gemini_web2api.google_session import UsageAuthError
        def handle(request):
            if request.url.path == '/RotateCookies':
                return httpx.Response(200, headers={'Set-Cookie': '__Secure-1PSIDTS=PRIVATE_NEW_TS; Domain=.google.com; Path=/; Secure'})
            return httpx.Response(302, headers={'Location': 'https://accounts.google.com/ServiceLogin?email=private@example.test'})
        session = self.make_session(handle)
        with self.assertRaises(UsageAuthError):
            session.refresh(rotate=True)
        records = self.records()
        self.assertTrue(any(r.get('endpoint') == 'rotate_cookies' and r.get('status') == 200 for r in records))
        self.assertTrue(any(r.get('reason') == 'login_redirect' for r in records))
        self.assertFalse(any(r['event'] == 'rotation_success' for r in records))
        self.assertIn('PRIVATE_NEW_TS', self.profile.with_name('cookie.txt').read_text())
        for secret in ('PRIVATE_SID', 'PRIVATE_SAPISID', 'PRIVATE_PSID', 'PRIVATE_NEW_TS', 'OLD_TS', 'private@example.test', 'ServiceLogin?'):
            self.assertNotIn(secret, self.log.read_text())

    def test_quota_auth_rejection_under_http_200_has_its_own_reason(self):
        try:
            import httpx
        except ImportError:
            self.skipTest('HTTP session dependency is installed in Gemini image')
        from gemini_web2api.google_session import UsageAuthError
        def handle(request):
            if request.url.path.endswith('/app'):
                return httpx.Response(200, text='{"SNlM0e":"PRIVATE_XSRF","oPEP7c":"private@example.test"}')
            return httpx.Response(200, text=json.dumps([['wrb.fr', 'jSf9Qc', None, None, None, [7]]]))
        session = self.make_session(handle)
        with self.assertRaises(UsageAuthError):
            session.request_rpc('jSf9Qc', retry=False)
        self.assertTrue(any(r.get('reason') == 'rpc_auth_rejected' and r.get('endpoint') == 'quota_rpc' for r in self.records()))
        self.assertNotIn('PRIVATE_XSRF', self.log.read_text())
        self.assertNotIn('private@example.test', self.log.read_text())
