import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash
from ai_app import create_ai_app
from backend.map_predict import create_app
from backend.map_predict.api.v1.ai_admin import FAILURES, REVOKED, COOKIE
from backend.map_predict.services import ai_settings, assistant, knowledge


class AiAdminTests(unittest.TestCase):
    def setUp(self):
        FAILURES.clear()
        REVOKED.clear()
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        folder = Path(self.folder.name)
        self.key = folder / 'key'
        self.key.write_text('private-test-service-key')
        self.password = folder / 'password'
        self.password.write_text(generate_password_hash('admin-test-password'))
        self.config = {'TESTING': True, 'ASSISTANT_SECRET_FILE': str(self.key),
                       'AI_ADMIN_PASSWORD_FILE': str(self.password),
                       'AI_SETTINGS_FILE': str(folder / 'settings.json')}
        self.app = create_ai_app(self.config)
        self.client = self.app.test_client()
        self.headers = {'Authorization': 'Bearer private-test-service-key'}

    def login(self):
        reply = self.client.post('/api/v1/ai-admin/login', json={'password': 'admin-test-password'}, headers=self.headers)
        self.assertEqual(reply.status_code, 200, reply.json)
        self.csrf = reply.json['data']['csrf']
        return reply

    def post(self, action, body):
        return self.client.post('/api/v1/ai-admin/' + action, json=body,
                                headers={**self.headers, 'X-Admin-CSRF': self.csrf})

    def test_service_requires_internal_key_and_admin_password_independently(self):
        self.assertEqual(self.client.get('/api/v1/ai-admin/state').status_code, 401)
        self.assertEqual(self.client.get('/api/v1/ai-admin/state', headers=self.headers).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/ai-admin/login', json={'password': 'wrong'}, headers=self.headers).status_code, 401)
        response = self.login()
        self.assertIn('HttpOnly', response.headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', response.headers['Set-Cookie'])
        with patch('backend.map_predict.api.v1.ai_admin.gemini_request', return_value={'state': 'ready'}):
            state = self.client.get('/api/v1/ai-admin/state', headers=self.headers)
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.json['data']['chatbot_retrieval'], 'ragwire_hybrid')
        self.assertNotIn('api_key', state.json['data']['settings']['models']['fast'])

    def test_csrf_logout_revocation_and_password_change(self):
        self.login()
        self.assertEqual(self.client.post('/api/v1/ai-admin/settings', json={}, headers=self.headers).status_code, 403)
        cookie = self.client.get_cookie(COOKIE, path='/api/v1/ai-admin').value
        self.assertEqual(self.post('logout', {}).status_code, 200)
        self.client.set_cookie(COOKIE, cookie, path='/api/v1/ai-admin')
        self.assertEqual(self.client.get('/api/v1/ai-admin/state', headers=self.headers).status_code, 401)
        self.login()
        self.password.write_text(generate_password_hash('new-admin-password'))
        self.assertEqual(self.client.get('/api/v1/ai-admin/state', headers=self.headers).status_code, 401)

    def test_password_attempts_are_bounded(self):
        for _ in range(5):
            self.assertEqual(self.client.post('/api/v1/ai-admin/login', json={'password': 'wrong'}, headers=self.headers).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/ai-admin/login', json={'password': 'wrong'}, headers=self.headers).status_code, 429)

    def test_authenticated_session_refresh_targets_account_pool(self):
        self.login()
        with patch('backend.map_predict.api.v1.ai_admin.gemini_request', return_value={'accounts': []}) as remote:
            response = self.post('tools/accounts-refresh', {})
        self.assertEqual(response.status_code, 200)
        remote.assert_called_once_with('/refresh', {}, accounts=True)

    def test_settings_persist_and_keys_are_never_returned_or_sent_to_gemini(self):
        self.login()
        settings = ai_settings.defaults(self.app.config)
        settings['models']['fast'].update(provider='compatible', url='https://example.test/v1', api_key='external-private-key')
        result = self.post('settings', settings)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertNotIn('external-private-key', result.text)
        reloaded = ai_settings.model_config(self.app.config, 'fast')
        self.assertEqual(reloaded['ASSISTANT_API_KEY'], 'external-private-key')
        self.assertEqual(reloaded['ASSISTANT_URL'], 'https://example.test/v1')
        self.assertEqual(ai_settings.model_config(self.app.config, 'smart')['ASSISTANT_PROVIDER'], 'gemini')
        settings = result.json['data']
        self.assertEqual(self.post('settings', settings).status_code, 200)
        self.assertEqual(ai_settings.load(self.app.config)['models']['fast']['api_key'], 'external-private-key')
        settings['models']['fast']['url'] = 'file:///private'
        self.assertEqual(self.post('settings', settings).status_code, 400)

    def test_web_cannot_bypass_service_authentication_and_rejects_cross_origin(self):
        web = create_app({**self.config, 'ASSISTANT_SERVICE_URL': 'http://private.test'}).test_client()
        self.assertEqual(web.post('/api/v1/ai-admin/login', json={'password': 'x'}, headers={'Origin': 'https://other.test'}).status_code, 403)
        from backend.map_predict.services import assistant_gateway
        with patch.object(assistant_gateway, 'forward', return_value=({'error': 'service login required'}, 401)) as forward:
            self.assertEqual(web.get('/api/v1/ai-admin/state').status_code, 401)
            forward.assert_called_once_with('state', admin=True)

    def test_embedding_tools_require_session_and_unload_after_request(self):
        self.assertEqual(self.client.post('/api/v1/ai-admin/tools/embedding-test', json={'text': 'test'}, headers=self.headers).status_code, 401)
        self.login()
        with patch('backend.map_predict.api.v1.ai_admin.json_request', return_value={'embeddings': [[.1] * 1024]}) as call:
            response = self.post('tools/embedding-test', {'text': 'test'})
        self.assertEqual(response.json['data']['dimensions'], 1024)
        self.assertEqual(call.call_args.args[1]['keep_alive'], '0s')
        self.assertNotIn('embeddings', response.json['data'])

    def test_chatbot_modes_are_allowlisted_and_use_saved_embedding_for_ragwire(self):
        from backend.map_predict.services.prediction import PredictionError
        with self.assertRaises(PredictionError):
            ai_settings.model_config(self.app.config, 'https://untrusted.test')
        config = ai_settings.model_config(self.app.config, 'smart')
        self.assertEqual(config['ASSISTANT_RETRIEVAL_MODE'], 'ragwire')
        self.assertEqual(config['ASSISTANT_EMBEDDING_MODEL'], ai_settings.load(self.app.config)['embedding']['model'])
        self.assertEqual(config['ASSISTANT_EMBEDDING_URL'], ai_settings.load(self.app.config)['embedding']['url'])

    def test_external_model_does_not_receive_internal_service_secret(self):
        settings = ai_settings.defaults(self.app.config)
        settings['models']['fast'].update(provider='compatible', url='https://example.test/v1', api_key='external-private-key')
        ai_settings.save(self.app.config, settings)
        captured = []
        class Remote:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return json.dumps({'choices': [{'message': {'content': '{"answer":"ok"}'}}]}).encode()
        class Opener:
            def open(self, request, **kwargs):
                captured.append(request)
                return Remote()
        with patch.object(assistant, 'build_opener', return_value=Opener()):
            assistant.call_model([], ai_settings.model_config(self.app.config, 'fast'))
        self.assertEqual(captured[0].get_header('Authorization'), 'Bearer external-private-key')
        self.assertNotIn('private-test-service-key', repr(captured[0].headers))

    def test_argon_requires_service_side_passcode_before_reading_files_or_using_llm(self):
        from backend.map_predict.services.prediction import PredictionError
        config = self.app.config
        with patch.object(ai_settings, 'require_argon_cookie'), patch.object(assistant, 'load') as load, patch.object(assistant, 'call_model') as model:
            with self.assertRaises(PredictionError) as error:
                assistant.preview(Path('/unused'), b'', b'', {'mode': 'smart', 'message': 'test'}, config)
            self.assertEqual(error.exception.code, 'ARGON_DISABLED')
            ai_settings.set_passcode(config, 'separate-pro-passcode')
            for value in ('', 'wrong-passcode'):
                with self.assertRaises(PredictionError) as error:
                    assistant.preview(Path('/unused'), b'', b'', {'mode': 'smart', 'passcode': value}, config)
                self.assertEqual(error.exception.code, 'ARGON_PASSCODE_REQUIRED')
            load.assert_not_called()
            model.assert_not_called()
        ai_settings.authorize_pro(ai_settings.model_config(config, 'smart'), 'separate-pro-passcode')
        ai_settings.set_passcode(config, 'rotated-pro-passcode')
        with self.assertRaises(PredictionError):
            ai_settings.authorize_pro(ai_settings.model_config(config, 'smart'), 'separate-pro-passcode')
        settings = ai_settings.defaults(config)
        settings['models']['fast']['model'] = 'gemini-4-argon'
        ai_settings.save(config, settings)
        with self.assertRaises(PredictionError):
            ai_settings.authorize_pro(ai_settings.model_config(config, 'fast'), '')

    def test_only_admin_can_set_pro_passcode_and_pro_cannot_be_downgraded(self):
        self.assertEqual(self.client.post('/api/v1/ai-admin/tools/pro-passcode', json={'passcode': 'new-passcode'}, headers=self.headers).status_code, 401)
        self.login()
        response = self.post('tools/pro-passcode', {'passcode': 'new-pro-passcode'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['data']['configured'])
        self.assertNotIn('new-pro-passcode', response.text)
        settings = ai_settings.defaults(self.app.config)
        settings['models']['smart']['model'] = 'gemini-3.6-flash'
        self.assertEqual(self.post('settings', settings).status_code, 400)
        self.assertFalse(self.post('tools/pro-passcode', {'disable': True}).json['data']['configured'])

    def test_smart_missing_cookie_errors_before_passcode_files_retrieval_or_generation(self):
        from backend.map_predict.services.prediction import PredictionError
        with patch.object(ai_settings, 'argon_availability', return_value='cookie_required'), \
                patch.object(assistant, 'load') as load, patch.object(assistant, 'call_model') as model:
            with self.assertRaises(PredictionError) as error:
                assistant.preview(Path('/unused'), b'', b'', {'mode': 'smart', 'message': 'test'}, self.app.config)
            self.assertEqual(error.exception.code, 'COOKIE_REQUIRED')
            self.assertIn('cookie', str(error.exception))
            load.assert_not_called()
            model.assert_not_called()

    def test_legacy_three_modes_migrate_to_two_without_cheap_smart_route(self):
        old = {'models': {'fast': {'label': 'Nhanh', 'provider': 'gemini', 'model': 'gemini-3.6-flash', 'api_key': '', 'url': ''},
                           'smart': {'model': 'gemini-3.5-flash-thinking'}, 'pro': {'model': 'gemini-4-argon'}}}
        Path(self.config['AI_SETTINGS_FILE']).write_text(json.dumps(old))
        settings = ai_settings.load(self.app.config)
        self.assertEqual(set(settings['models']), {'fast', 'smart'})
        self.assertEqual(settings['models']['smart']['model'], 'gemini-4-argon')
        with patch.object(ai_settings, 'argon_availability', return_value='cookie_required'):
            response = self.client.get('/api/v1/assistant/status', headers=self.headers)
        self.assertEqual([mode['id'] for mode in response.json['data']['modes']], ['fast', 'smart'])
        self.assertEqual(response.json['data']['modes'][1]['availability'], 'cookie_required')
