import base64
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import ezdxf
from backend.map_predict import create_app
from backend.map_predict.api.v1.assistant import RATES
from backend.map_predict.services import assistant, assistant_files, assistant_dxf
from backend.map_predict.services.prediction import PredictionError


class AssistantFileTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        key = self.root / 'key'
        key.write_text('test-resource-signing-key')
        self.config = {'TESTING': True, 'ASSISTANT_ENABLED': True,
                       'ASSISTANT_SECRET_FILE': str(key), 'ASSISTANT_DXF_CACHE_DIR': self.root / 'cache'}
        assistant_dxf.CACHE.clear()
        RATES.clear()

    def resource(self, data=b'drawing', identifier='file-a'):
        return {'id': identifier, 'name': 'drawing.dxf', 'data': data}

    def code(self, code, callback):
        with self.assertRaises(PredictionError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_reference_is_bound_to_content_source_and_secret(self):
        ref = assistant_files.store(self.resource(), self.config)
        self.assertEqual(assistant_files.resolve(ref['token'], 'file-a', self.config)['data'], b'drawing')
        self.code('INVALID_RESOURCE_REFERENCE', lambda: assistant_files.resolve(ref['token'], 'other', self.config))
        self.code('INVALID_RESOURCE_REFERENCE', lambda: assistant_files.resolve(ref['token'] + 'x', 'file-a', self.config))
        forged = assistant_files.signer(self.config).dumps({'id': '../outside', 'source_id': 'file-a', 'name': 'drawing.dxf', 'hash': '0' * 64})
        self.code('INVALID_RESOURCE_REFERENCE', lambda: assistant_files.resolve(forged, 'file-a', self.config))
        path = next((self.root / 'cache').glob('*.dxf'))
        if os.name != 'nt':
            self.assertEqual(path.stat().st_mode & 0o077, 0)
        path.write_bytes(b'corrupted')
        self.code('ASSISTANT_RESOURCE_EXPIRED', lambda: assistant_files.resolve(ref['token'], 'file-a', self.config))

    def test_expiration_cleanup_and_budget_only_remove_managed_cache_files(self):
        with patch.object(assistant_files, 'MAX_BYTES', 12), patch.object(assistant_files, 'MAX_FILES', 1):
            first = assistant_files.store(self.resource(b'first'), self.config)
            assistant_files.store(self.resource(b'next'), self.config)
            self.code('ASSISTANT_RESOURCE_EXPIRED', lambda: assistant_files.resolve(first['token'], 'file-a', self.config))
            self.assertEqual(len(list((self.root / 'cache').glob('*.dxf'))), 1)
            self.assertIsNone(assistant_files.store(self.resource(b'x' * 13), self.config))
        protected = self.root / 'cache' / 'keep.dxf'
        protected.write_bytes(b'not owned by cache')
        for path in (self.root / 'cache').glob('*.dxf'):
            os.utime(path, (time.time() - 1000,) * 2)
        assistant_files.prune(self.config)
        self.assertEqual(list((self.root / 'cache').glob('*.dxf')), [protected])

    def test_signed_expired_reference_is_a_retryable_miss(self):
        ref = assistant_files.store(self.resource(), self.config)
        with patch.object(assistant_files, 'TTL', -1):
            self.code('ASSISTANT_RESOURCE_EXPIRED', lambda: assistant_files.resolve(ref['token'], 'file-a', self.config))

    def test_worker_health_expires_private_files_and_summary_cache(self):
        from ai_app import create_ai_app
        assistant_files.store(self.resource(), self.config)
        path = next((self.root / 'cache').glob('*.dxf'))
        os.utime(path, (time.time() - 1000,) * 2)
        assistant_dxf.CACHE['expired'] = (time.monotonic() - 1000, b'{}')
        response = create_ai_app(self.config).test_client().get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(path.exists())
        self.assertNotIn('expired', assistant_dxf.CACHE)

    def test_resource_metadata_is_bounded_before_resolving_any_file(self):
        client = create_app(self.config).test_client()
        with patch.object(assistant_files, 'resolve') as resolve, patch.object(assistant, 'call_model') as model:
            response = client.post('/api/v1/assistant/preview', data={'scope': 'map',
                'resource_ids': json.dumps(['a'] * 10000), 'message': 'Describe drawing'})
        self.assertEqual(response.status_code, 400)
        resolve.assert_not_called()
        model.assert_not_called()

    def drawing(self):
        document = ezdxf.new()
        entity = document.modelspace().add_text('A1', dxfattribs={'color': 7})
        stream = io.StringIO()
        document.write(stream)
        return stream.getvalue().encode(), entity.dxf.handle

    def test_cached_followup_and_apply_preserve_signed_source_validation(self):
        raw, handle = self.drawing()
        client = create_app(self.config).test_client()
        def proposal(*args, **kwargs):
            return {'answer': 'Propose color', 'edits': [{'handle': '0~' + handle, 'operation': 'color', 'value': 3}]}
        with patch.object(assistant, 'call_model', side_effect=proposal):
            first = client.post('/api/v1/assistant/preview', data={'scope': 'map', 'resource_ids': '["file-a"]',
                'dxf': (io.BytesIO(raw), 'drawing.dxf'), 'message': 'Change color', 'web': 'false'})
        self.assertEqual(first.status_code, 200, first.json)
        ref = first.json['data']['resource_cache'][0]['token']
        form = {'scope': 'map', 'resource_ids': '["file-a"]', 'resource_tokens': json.dumps([ref]),
                'token': first.json['data']['token']}
        result = client.post('/api/v1/assistant/apply', data=form)
        self.assertEqual(result.status_code, 200, result.json)
        output = ezdxf.read(io.StringIO(base64.b64decode(result.json['data']['dxfs'][0]['dxf']).decode()))
        self.assertEqual(output.entitydb[handle].dxf.color, 3)
        self.assertEqual(assistant_files.resolve(ref, 'file-a', self.config)['data'], raw)
        RATES.clear()
        with patch.object(assistant.ezdxf, 'readfile', side_effect=AssertionError('A read-only cache hit must not reload the drawing')), \
                patch.object(assistant, 'call_model', return_value={'answer': 'Read summary'}) as model:
            followup = client.post('/api/v1/assistant/preview', data={**form, 'message': 'Describe drawing', 'web': 'false'})
        self.assertEqual(followup.status_code, 200, followup.json)
        self.assertEqual(followup.json['data']['timings']['summary_cache_hits'], 1)
        context = json.loads(model.call_args.args[0][-1]['content'].split('\n', 1)[1].split('\nYÊU CẦU\n')[0])
        self.assertIn('handle_prefix', model.call_args.args[0][0]['content'])
        self.assertEqual(context['dxf']['files'][0]['handle_prefix'], '0~')
        self.assertEqual(context['dxf']['entities'][0]['handle'], '0~' + handle)
        self.assertEqual(context['dxf']['entities'][0]['color'], 7)
        for path in (self.root / 'cache').glob('*.dxf'):
            path.unlink()
        with patch.object(assistant, 'call_model') as model:
            expired = client.post('/api/v1/assistant/preview', data={**form, 'message': 'Describe drawing'})
        self.assertEqual(expired.status_code, 410, expired.json)
        self.assertEqual(expired.json['error']['code'], 'ASSISTANT_RESOURCE_EXPIRED')
        model.assert_not_called()

    def test_bulge_geometry_is_preserved_without_materializing_all_vertices(self):
        doc = ezdxf.new()
        entity = doc.modelspace().add_lwpolyline([(i, i * 2, 0, 0, 0.5) for i in range(20)])
        with patch.object(entity, 'get_points', side_effect=AssertionError('Full vertex list is unnecessary')):
            result = assistant.describe(doc)
        self.assertEqual(result['entities'][0]['vertices_xy_bulge'][15], [15, 30, 0.5])

    def test_mixed_cached_and_uploaded_files_cannot_swap_edit_targets(self):
        first, handle = self.drawing()
        document = ezdxf.new()
        second_entity = document.modelspace().add_text('B2', dxfattribs={'color': 7})
        stream = io.StringIO()
        document.write(stream)
        second = stream.getvalue().encode()
        ref = assistant_files.store(self.resource(first), self.config)
        client = create_app(self.config).test_client()
        with patch.object(assistant, 'call_model', return_value={'answer': 'Change second file',
                'edits': [{'handle': '1~' + second_entity.dxf.handle, 'operation': 'color', 'value': 4}]}):
            response = client.post('/api/v1/assistant/preview', data={'scope': 'map',
                'resource_ids': '["file-a","file-b"]', 'resource_tokens': json.dumps([ref['token'], None]),
                'dxf': (io.BytesIO(second), 'second.dxf'), 'message': 'Change second file', 'web': 'false'})
        self.assertEqual(response.status_code, 200, response.json)
        proposal = response.json['data']
        self.assertEqual(proposal['edits'][0]['source_id'], 'file-b')
        references = {item['source_id']: item['token'] for item in proposal['resource_cache']}
        result = client.post('/api/v1/assistant/apply', data={'scope': 'map',
            'resource_ids': '["file-a","file-b"]',
            'resource_tokens': json.dumps([references['file-a'], references['file-b']]), 'token': proposal['token']})
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual([item['source_id'] for item in result.json['data']['dxfs']], ['file-b'])
        output = ezdxf.read(io.StringIO(base64.b64decode(result.json['data']['dxfs'][0]['dxf']).decode()))
        self.assertEqual(output.entitydb[second_entity.dxf.handle].dxf.color, 4)
        self.assertEqual(assistant_files.resolve(ref['token'], 'file-a', self.config)['data'], first)
