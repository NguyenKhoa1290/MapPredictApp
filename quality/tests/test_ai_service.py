from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import subprocess
import sys

from ai_service.app import create_ai_app
from backend.map_predict import create_app
from ai_service.api.assistant import RATES
from backend.map_predict.services import assistant_gateway


class AIServiceTests(unittest.TestCase):
    def test_gateway_forwards_async_preference_and_job_poll_using_internal_key(self):
        app = create_app({**self.config, 'ASSISTANT_SERVICE_URL': 'http://ai-assistant:8001'})
        remote = Mock()
        remote.__enter__ = Mock(return_value=remote)
        remote.__exit__ = Mock(return_value=False)
        remote.read.return_value = b'{"data":{"state":"pending"}}'
        remote.code = 202
        remote.headers = {'Content-Type': 'application/json'}
        opener = Mock()
        opener.open.return_value = remote
        identifier = 'a' * 43
        with patch.object(assistant_gateway, 'build_opener', return_value=opener):
            response = app.test_client().post('/api/v1/assistant/preview', data={'message': 'hello'},
                headers={'Prefer': 'respond-async', 'Authorization': 'Bearer browser-value'})
            self.assertEqual(response.status_code, 202)
            forwarded = opener.open.call_args.args[0]
            self.assertEqual(forwarded.get_header('Prefer'), 'respond-async')
            self.assertEqual(forwarded.get_header('Authorization'), 'Bearer private-test-key')
            poll = app.test_client().get('/api/v1/assistant/jobs/' + identifier)
            self.assertEqual(poll.status_code, 202)
            forwarded = opener.open.call_args.args[0]
            self.assertEqual(forwarded.full_url, 'http://ai-assistant:8001/api/v1/assistant/jobs/' + identifier)
            self.assertEqual(forwarded.method, 'GET')
            self.assertEqual(forwarded.get_header('Authorization'), 'Bearer private-test-key')

    def test_worker_can_start_without_importing_web_backend(self):
        script = '''
import importlib.abc
import sys
class BlockWebBackend(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'backend' or fullname.startswith('backend.'):
            raise ImportError('Worker must not import the web backend')
sys.meta_path.insert(0, BlockWebBackend())
from ai_service.app import create_ai_app
app = create_ai_app({'TESTING': True})
assert app.test_client().get('/health').status_code == 200
'''
        subprocess.run([sys.executable, '-B', '-c', script], check=True, timeout=45)

    def test_web_gateway_can_start_without_importing_ai_worker(self):
        script = '''
import importlib.abc
import sys
class BlockAIWorker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'ai_service' or fullname.startswith('ai_service.'):
            raise ImportError('Remote web gateway must not import the worker')
sys.meta_path.insert(0, BlockAIWorker())
from backend.map_predict import create_app
app = create_app({'TESTING': True, 'ASSISTANT_SERVICE_URL': 'http://ai-assistant:8001'})
assert app.test_client().get('/api/v1/health').status_code == 200
'''
        subprocess.run([sys.executable, '-B', '-c', script], check=True, timeout=45)

    def setUp(self):
        RATES.clear()
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.key = Path(self.folder.name) / 'key'
        self.key.write_text('private-test-key')
        self.config = {'TESTING': True, 'ASSISTANT_SECRET_FILE': str(self.key), 'ASSISTANT_ENABLED': True}

    def test_standalone_service_requires_internal_key_except_health(self):
        client = create_ai_app(self.config).test_client()
        self.assertEqual(client.get('/health').status_code, 200)
        self.assertEqual(client.get('/api/v1/assistant/status').status_code, 401)
        response = client.get('/api/v1/assistant/status', headers={'Authorization': 'Bearer private-test-key'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['data']['service'], 'worker')

    def test_web_gateway_supplies_its_own_key_and_preserves_binary_download(self):
        app = create_app({**self.config, 'ASSISTANT_SERVICE_URL': 'http://ai:8001'})
        remote = Mock()
        remote.__enter__ = Mock(return_value=remote)
        remote.__exit__ = Mock(return_value=False)
        remote.read.return_value = b'0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n'
        remote.code = 200
        remote.headers = {'Content-Type': 'application/dxf', 'Content-Disposition': 'attachment; filename=edited.dxf'}
        opener = Mock()
        opener.open.return_value = remote
        with patch.object(assistant_gateway, 'build_opener', return_value=opener):
            response = app.test_client().post('/api/v1/assistant/export', data={'token': 'signed'},
                        headers={'Origin': 'http://localhost', 'Authorization': 'Bearer client-supplied'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, remote.read.return_value)
        self.assertIn('edited.dxf', response.headers['Content-Disposition'])
        forwarded = opener.open.call_args.args[0]
        self.assertEqual(forwarded.get_header('Authorization'), 'Bearer private-test-key')
        self.assertIsNone(forwarded.get_header('Origin'))


if __name__ == '__main__':
    unittest.main()
