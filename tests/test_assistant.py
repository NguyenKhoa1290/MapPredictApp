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

    def test_prediction_creates_csv_without_dxf_and_scores_only_via_verified_rules(self):
        result = {'answer': 'Đề xuất bảng mới', 'create_table': True, 'table_rows': [{'id': 'A1', 'x4': 100, 'Y': 2}],
                  'edits': [], 'sources': [], 'scores': [{'row_index': 0, 'column': 'x4', 'value': 9,
                    'rule': 'L9', 'evidence': 'USER', 'quote': 'đất nông nghiệp xen kẹt'}]}
        with patch.object(assistant, 'call_model', return_value=result):
            response = self.client.post('/api/v1/assistant/preview', data={'scope': 'prediction',
                'message': 'Tạo CSV cho A1 là đất nông nghiệp xen kẹt', 'web': 'false'})
        self.assertEqual(response.status_code, 200, response.json)
        preview = response.json['data']
        self.assertTrue(preview['create_table'])
        self.assertEqual(preview['row_count'], 1)
        response = self.client.post('/api/v1/assistant/apply', data={'scope': 'prediction', 'token': preview['token']})
        self.assertEqual(response.status_code, 200, response.json)
        rows = response.json['data']['rows']
        self.assertEqual(rows[0]['id'], 'A1')
        self.assertEqual(rows[0]['x4'], 9)
        self.assertEqual(rows[0]['x1'], '')
        self.assertNotIn('Y', rows[0])
        self.assertIsNone(response.json['data']['dxf'])

    def test_scope_rejects_wrong_files_and_map_cannot_create_a_new_dxf(self):
        with patch.object(assistant, 'call_model') as model:
            response = self.client.post('/api/v1/assistant/apply', data={'scope': 'map', 'token': 'no-file'})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json['error']['code'], 'MAP_RESOURCE_REQUIRED')
            response = self.post('preview', scope='prediction', message='Sửa DXF')
            self.assertEqual(response.status_code, 400)
            response = self.post('preview', scope='map', resource_ids='["file-a"]', message='Sửa điểm')
            self.assertEqual(response.status_code, 400)
            model.assert_not_called()

    def test_empty_map_can_chat_but_cannot_propose_any_file_mutation(self):
        result = {'answer': 'Bạn có thể nạp DXF để chỉnh bản vẽ', 'sources': [], 'scores': [],
                  'create_table': True, 'table_rows': [{'id': 'A1'}],
                  'edits': [{'handle': 'NEW', 'operation': 'add_line', 'value': {'points': [[1, 2], [3, 4]]}}]}
        with patch.object(assistant, 'call_model', return_value=result) as model:
            response = self.client.post('/api/v1/assistant/preview', data={'scope': 'map', 'message': 'Xin chào', 'web': 'false'})
        self.assertEqual(response.status_code, 200, response.json)
        model.assert_called_once()
        self.assertEqual(response.json['data']['answer'], result['answer'])
        self.assertIsNone(response.json['data']['token'])
        self.assertFalse(response.json['data']['edits'])
        self.assertFalse(response.json['data']['scores'])
        self.assertFalse(response.json['data']['create_table'])

    def map_request(self, action, **options):
        return self.client.post('/api/v1/assistant/' + action, data={
            'scope': 'map', 'resource_ids': '["file-a","file-b"]',
            'dxf': [(io.BytesIO(self.dxf), 'a.dxf'), (io.BytesIO(self.dxf), 'b.dxf')], **options})

    def test_multiple_dxf_handles_are_scoped_drawings_and_attributes_survive_export(self):
        result = {'answer': 'Đề xuất sửa hai file', 'sources': [], 'scores': [], 'edits': [
            {'handle': '0~' + self.handle, 'operation': 'color', 'value': 1},
            {'handle': '1~' + self.handle, 'operation': 'color', 'value': 3},
            {'handle': '0~' + self.handle, 'operation': 'attribute', 'value': {'name': 'tenlodat', 'value': 'Lô A1'}},
            {'handle': 'NEW', 'source_id': 'file-b', 'operation': 'add_line',
             'value': {'points': [[10, 20], [30, 40]], 'layer': 'DuongMoi', 'color': 2}},
            {'handle': 'NEW', 'source_id': 'not-loaded', 'operation': 'add_circle',
             'value': {'position': [1, 2], 'radius': 3}}]}
        with patch.object(assistant, 'call_model', return_value=result) as model:
            response = self.map_request('preview', message='Sửa màu, thêm thuộc tính và vẽ đường', web='false')
            context = json.loads(model.call_args.args[0][-1]['content'].split('DỮ LIỆU NGƯỜI DÙNG\n')[1].split('\nYÊU CẦU\n')[0])
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(len(context['dxf']['files']), 2)
        preview = response.json['data']
        self.assertEqual(len(preview['edits']), 4)
        self.assertEqual(len(preview['rejected']), 1)
        response = self.map_request('apply', token=preview['token'])
        self.assertEqual(response.status_code, 200, response.json)
        output = {item['source_id']: ezdxf.read(io.StringIO(base64.b64decode(item['dxf']).decode()))
                  for item in response.json['data']['dxfs']}
        self.assertEqual(output['file-a'].entitydb[self.handle].dxf.color, 1)
        self.assertEqual(output['file-b'].entitydb[self.handle].dxf.color, 3)
        self.assertEqual(len(output['file-a'].modelspace().query('LINE')), 0)
        self.assertEqual(len(output['file-b'].modelspace().query('LINE')), 1)
        from cad_to_geojson import read_assistant_attributes
        self.assertEqual(read_assistant_attributes(output['file-a'].entitydb[self.handle])['tenlodat'], 'Lô A1')
        response = self.client.post('/api/v1/assistant/apply', data={'scope': 'map', 'resource_ids': '["file-a"]',
            'dxf': (io.BytesIO(self.dxf), 'a.dxf'), 'token': preview['token']})
        self.assertEqual(response.status_code, 409)

    def test_new_table_and_drawing_validators_reject_unbounded_or_ambiguous_data(self):
        for value in ([], [{'id': 'A1'}, {'id': 'A1'}], [{'x1': 3}]):
            with self.assertRaises(ValueError):
                assistant.new_table(value)
        for value in ({'position': [float('nan'), 1], 'radius': 1}, {'position': [1, 2], 'radius': -1}):
            with self.assertRaises(ValueError):
                assistant.valid_drawing({'operation': 'add_circle', 'value': value})

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

    def test_exact_numeric_serializations_are_supported_without_interpreting_ranges(self):
        preview = self.plan(edits=[{'handle': self.handle, 'operation': 'color', 'value': '1'}],
            scores=[{'row_index': '0', 'column': 'x4', 'value': '9', 'rule': 'L9',
                     'evidence': 'USER', 'quote': 'đất nông nghiệp xen kẹt'}])
        self.assertEqual(preview['edits'][0]['value'], 1)
        self.assertEqual(preview['scores'][0]['value'], 9)
        for value in ('1-3', True, float('nan')):
            with self.assertRaises(ValueError):
                assistant.exact_integer(value)

    def test_merged_point_groups_are_not_filled(self):
        preview = self.plan(scores=[{'row_index': 0, 'column': 'x1', 'value': 1,
                                    'rule': 'D3:F3', 'evidence': 'USER', 'quote': 'đất nông nghiệp xen kẹt'}])
        self.assertFalse(preview['scores'])
        self.assertIsNone(preview['token'])
        self.assertTrue(preview['rejected'])

    def test_qdrant_rule_itself_is_not_an_observation_of_the_land_parcel(self):
        record = {'id': 'point-1', 'file': 'Tieuchi.md', 'source_refs': ['sửa ngày 1509!L9'],
                  'content': '### sửa ngày 1509 | 4. Hiện trạng sử dụng đất\n| 9 | `L9` | Đất nông nghiệp xen kẹt |'}
        with patch.object(assistant, 'retrieve', return_value={'mode': 'dense', 'records': [record]}):
            preview = self.plan(scores=[{'row_index': 0, 'column': 'x4', 'value': 9, 'rule': 'L9',
                'evidence': 'QDRANT:point-1', 'quote': 'Đất nông nghiệp xen kẹt'}])
        self.assertIsNone(preview['token'])
        self.assertFalse(preview['scores'])

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

    def test_export_returns_downloadable_dxf_without_applying_to_original(self):
        preview = self.plan(edits=[{'handle': self.handle, 'operation': 'color', 'value': 2}])
        response = self.post('export', token=preview['token'])
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertIn('original_edited.dxf', response.headers['Content-Disposition'])
        changed = ezdxf.read(io.StringIO(response.data.decode()))
        self.assertEqual(changed.entitydb[self.handle].dxf.color, 2)
        unchanged = ezdxf.read(io.StringIO(self.dxf.decode()))
        self.assertEqual(unchanged.entitydb[self.handle].dxf.color, 7)

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
