import tempfile
import io
import threading
import time
from pathlib import Path
import unittest
from unittest.mock import patch

from ai_service.app import create_ai_app
from ai_service.services import assistant_jobs, assistant
from shared.tabular import PredictionError


class AssistantJobTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        key = Path(self.folder.name) / 'key'
        key.write_text('test-internal-key')
        self.app = create_ai_app({'TESTING': True, 'ASSISTANT_SECRET_FILE': str(key)})
        self.client = self.app.test_client()
        self.headers = {'Authorization': 'Bearer test-internal-key', 'Prefer': 'respond-async'}
        self.addCleanup(lambda: assistant_jobs.JOBS.clear())

    def wait_result(self, identifier):
        for _ in range(100):
            response = self.client.get('/api/v1/assistant/jobs/' + identifier, headers=self.headers)
            if response.status_code != 202:
                return response
            time.sleep(.01)
        self.fail('Background preview did not finish')

    def test_slow_preview_returns_pending_without_blocking_health_and_preserves_result(self):
        entered, finish = threading.Event(), threading.Event()
        def slow(*args, **kwargs):
            self.assertEqual(args[2], b'id,x1\nA1,3\n')
            entered.set()
            if not finish.wait(2):
                raise TimeoutError()
            return {'answer': 'finished', 'token': 'signed-preview'}
        with patch.object(assistant, 'preview', side_effect=slow):
            try:
                response = self.client.post('/api/v1/assistant/preview', headers=self.headers,
                    data={'scope': 'prediction', 'message': 'hello', 'csv': (io.BytesIO(b'id,x1\nA1,3\n'), 'criteria.csv')})
                self.assertEqual(response.status_code, 202)
                identifier = response.json['data']['job_id']
                self.assertTrue(entered.wait(1))
                self.assertEqual(self.client.get('/health').status_code, 200)
                self.assertEqual(self.client.get('/api/v1/assistant/jobs/' + identifier, headers=self.headers).status_code, 202)
                self.assertEqual(self.client.get('/api/v1/assistant/jobs/' + identifier).status_code, 401)
            finally:
                finish.set()
            done = self.wait_result(identifier)
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.json['data'], {'answer': 'finished', 'token': 'signed-preview'})
        self.assertEqual(done.headers['Cache-Control'], 'no-store')

    def test_background_errors_keep_status_and_do_not_repeat_model_call(self):
        with patch.object(assistant, 'preview', side_effect=PredictionError('ARGON_PASSCODE_REQUIRED', 'passcode required', 403)) as model:
            response = self.client.post('/api/v1/assistant/preview', headers=self.headers,
                data={'scope': 'prediction', 'message': 'hello'})
            result = self.wait_result(response.json['data']['job_id'])
        self.assertEqual(result.status_code, 403)
        self.assertEqual(result.json['error']['code'], 'ARGON_PASSCODE_REQUIRED')
        self.assertEqual(model.call_count, 1)
        self.assertEqual(self.client.get('/api/v1/assistant/jobs/unknown', headers=self.headers).status_code, 404)

    def test_argon_has_transport_margin_while_other_models_stay_at_80(self):
        for model, expected in [('gemini-4-argon', 320), ('gemini-3.8-flash', 80)]:
            config = {'ASSISTANT_MODEL': model, 'ASSISTANT_SUPPORTED_EFFORTS': ['auto']}
            with patch('ai_service.services.ai_settings.model_config', return_value=config), \
                    patch('ai_service.services.ai_settings.require_argon_cookie'), \
                    patch('ai_service.services.ai_settings.authorize_pro'), \
                    patch.object(assistant, 'call_model', return_value={'answer': 'ok'}) as call:
                assistant.preview(None, b'', b'', {'scope': 'map', 'inspector': 'true', 'message': 'hello'}, {})
            self.assertEqual(call.call_args.args[1]['ASSISTANT_CALL_TIMEOUT'], expected)

    def test_finished_jobs_expire_and_active_jobs_are_not_removed(self):
        with patch.object(assistant_jobs.time, 'monotonic', return_value=1000):
            assistant_jobs.JOBS.update(old={'finished_at': 0, 'result': ({}, 200)}, active={'finished_at': None, 'result': None})
            assistant_jobs.prune()
            self.assertNotIn('old', assistant_jobs.JOBS)
            self.assertIn('active', assistant_jobs.JOBS)
