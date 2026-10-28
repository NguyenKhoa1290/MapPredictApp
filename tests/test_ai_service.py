from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from ai_app import create_ai_app
from backend.map_predict import create_app
from backend.map_predict.api.v1.assistant import RATES
from backend.map_predict.services import assistant_gateway


class AIServiceTests(unittest.TestCase):
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
