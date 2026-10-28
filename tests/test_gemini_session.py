import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


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
