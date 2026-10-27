import base64
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import ezdxf

from backend.map_predict import create_app
from backend.map_predict.api.v1.assistant import RATES
from backend.map_predict.services import assistant, assistant_sources


class AssistantTests(unittest.TestCase):
    def setUp(self):
        RATES.clear()
        doc = ezdxf.new('R2010')
        entity = doc.modelspace().add_text('A1', dxfattribs={'insert': (1, 2), 'color': 7})
        self.handle = entity.dxf.handle
        stream = io.StringIO()
        doc.write(stream)
        self.dxf = stream.getvalue().encode()
        self.csv = b'id,x1,x4,Y,custom\nA1,,,2,keep\nA2,3,4,1,also-keep\n'
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        secret = Path(self.folder.name) / 'key'
        secret.write_text('test-key-for-assistant')
        self.app = create_app({'TESTING': True, 'ASSISTANT_ENABLED': True,
                               'ASSISTANT_SECRET_FILE': str(secret)})
        self.client = self.app.test_client()

    def post(self, action, **kwargs):
        csv = kwargs.pop('csv', self.csv)
        return self.client.post('/api/v1/assistant/' + action, data={
            'dxf': (io.BytesIO(self.dxf), 'original.dxf'),
            'csv': (io.BytesIO(csv), 'criteria.csv'), **kwargs})

    def plan(self, **changes):
        result = {'answer': 'Đề xuất cho ô đất', 'edits': [], 'scores': [], 'sources': [], **changes}
        with patch.object(assistant, 'call_model', return_value=result):
            response = self.post('preview', message='Ô A1 là đất nông nghiệp xen kẹt', web='false')
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['data']

    def test_edit_requires_preview_and_apply_only_returns_a_copy(self):
        original = self.dxf
        preview = self.plan(edits=[{'handle': self.handle, 'operation': 'color', 'value': 1}])
        self.assertEqual(preview['edits'][0]['before'], 7)
        self.assertEqual(self.dxf, original)
        response = self.post('apply', token=preview['token'])
        self.assertEqual(response.status_code, 200)
        edited = ezdxf.read(io.StringIO(base64.b64decode(response.json['data']['dxf']).decode()))
        self.assertEqual(edited.entitydb[self.handle].dxf.color, 1)
        self.assertEqual(self.dxf, original)

    def test_scores_keep_other_columns_and_invalidate_old_predictions(self):
        preview = self.plan(scores=[{'row_index': 0, 'column': 'x4', 'value': 9,
                                    'rule': 'L9', 'evidence': 'USER', 'quote': 'đất nông nghiệp xen kẹt'}])
        self.assertEqual(len(preview['scores']), 1)
        response = self.post('apply', token=preview['token'])
        rows = response.json['data']['rows']
        self.assertEqual(rows[0]['x4'], 9)
        self.assertEqual(rows[0]['custom'], 'keep')
        self.assertEqual(rows[1]['x4'], '4')
        self.assertTrue(all('Y' not in row for row in rows))

    def test_merged_point_groups_are_not_filled(self):
        preview = self.plan(scores=[{'row_index': 0, 'column': 'x1', 'value': 1,
                                    'rule': 'D3:F3', 'evidence': 'USER', 'quote': 'đất nông nghiệp xen kẹt'}])
        self.assertFalse(preview['scores'])
        self.assertIsNone(preview['token'])
        self.assertTrue(preview['rejected'])

    def test_fabricated_evidence_and_unknown_rows_are_rejected(self):
        for index, quote in ((-1, 'đất nông nghiệp xen kẹt'), (0, 'thông tin tự bịa trong câu trả lời')):
            result = self.plan(scores=[{'row_index': index, 'column': 'x4', 'value': 9,
                                       'rule': 'L9', 'evidence': 'USER', 'quote': quote}])
            self.assertIsNone(result['token'])

    def test_only_known_handles_and_whitelisted_edits_are_allowed(self):
        for edit in ({'handle': self.handle, 'operation': 'delete', 'value': True},
                     {'handle': 'NOT_REAL', 'operation': 'color', 'value': 1},
                     {'handle': self.handle, 'operation': 'color', 'value': 999},
                     {'handle': self.handle, 'operation': 'translate', 'value': [float('inf'), 0]}):
            self.assertIsNone(self.plan(edits=[edit])['token'])

    def test_stale_csv_and_forged_tokens_cannot_apply(self):
        preview = self.plan(edits=[{'handle': self.handle, 'operation': 'text', 'value': 'A2'}])
        self.assertEqual(self.post('apply', token=preview['token'], csv=self.csv + b'A3,,,,\n').status_code, 409)
        self.assertEqual(self.post('apply', token=preview['token'] + 'tampered').status_code, 409)

    def test_cross_origin_is_rejected_without_contacting_model(self):
        with patch.object(assistant, 'call_model') as model:
            response = self.client.post('/api/v1/assistant/preview', headers={'Origin': 'https://another.example'},
                                        data={'message': 'Đọc DXF'})
        self.assertEqual(response.status_code, 403)
        model.assert_not_called()

    def test_upload_is_not_shared_across_clients(self):
        self.plan(edits=[{'handle': self.handle, 'operation': 'color', 'value': 1}])
        second = self.app.test_client()
        with patch.object(assistant, 'call_model', return_value={'answer': 'Không có file', 'edits': []}) as model:
            response = second.post('/api/v1/assistant/preview', data={'message': 'Tôi có file nào'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('"entity_count": 0', model.call_args.args[0][-1]['content'])
        self.assertNotIn(self.handle + '", "type"', model.call_args.args[0][-1]['content'])

    def test_rate_limit_preserves_health_capacity(self):
        RATES['127.0.0.1'].extend([time.monotonic()] * 6)
        response = self.client.post('/api/v1/assistant/preview', data={'message': 'test'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.client.get('/api/v1/health').status_code, 200)

    def test_polyline_context_has_geometry_and_explicit_limits(self):
        doc = ezdxf.new()
        doc.modelspace().add_lwpolyline([(i, i * 2) for i in range(20)], close=True)
        doc.modelspace().add_polyline3d([(0, 0, 2), (1, 0, 3), (1, 1, 4)], close=True)
        context = assistant.describe(doc)
        self.assertEqual(context['entities'][0]['vertex_count'], 20)
        self.assertEqual(len(context['entities'][0]['vertices_xy_bulge']), 16)
        self.assertTrue(context['entities'][0]['closed'])
        self.assertEqual(context['entities'][1]['vertices_xyz'][0], [0, 0, 2])

    def test_source_verification_rejects_private_and_local_hosts(self):
        for address in ('127.0.0.1', '169.254.169.254', '10.1.2.3', '::1'):
            with patch.object(assistant_sources.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', (address, 443))]):
                with self.assertRaises(ValueError):
                    assistant_sources.public_address('example.com')
        with patch.object(assistant_sources, 'public_address') as resolver:
            source = assistant_sources.verify_source({'url': 'file:///etc/passwd', 'quote': 'a' * 40})
        resolver.assert_not_called()
        self.assertFalse(source['verified'])


if __name__ == '__main__':
    unittest.main()
