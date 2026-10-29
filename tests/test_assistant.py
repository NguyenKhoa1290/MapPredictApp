import base64
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

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
        availability = patch('backend.map_predict.services.ai_settings.argon_availability', return_value='ready')
        availability.start()
        self.addCleanup(availability.stop)

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

    def test_effort_is_validated_and_forwarded_to_model_config(self):
        for effort in ('auto', 'low', 'medium', 'high', 'invalid'):
            RATES.clear()
            with patch.object(assistant, 'call_model', return_value={'answer': 'ok'}) as model:
                response = self.client.post('/api/v1/assistant/preview', data={
                    'scope': 'map', 'message': 'hello', 'web': 'false', 'effort': effort})
            if effort == 'invalid':
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['error']['code'], 'INVALID_EFFORT')
                model.assert_not_called()
            else:
                self.assertEqual(response.status_code, 200, response.json)
                self.assertEqual(model.call_args.args[1]['ASSISTANT_EFFORT'], effort)

    def test_smart_accepts_all_levels_and_status_reports_real_route_capabilities(self):
        from backend.map_predict.services import ai_settings
        with patch.object(ai_settings, 'argon_availability', return_value='ready'):
            modes = {row['id']: row for row in self.client.get('/api/v1/assistant/status').json['data']['modes']}
        self.assertEqual(modes['fast']['efforts'], ['auto', 'low', 'medium', 'high'])
        self.assertEqual(modes['smart']['efforts'], ['auto', 'low', 'medium', 'high'])
        for effort in ('auto', 'low', 'medium', 'high'):
            RATES.clear()
            with patch.object(ai_settings, 'require_argon_cookie'), patch.object(ai_settings, 'authorize_pro'), \
                    patch.object(assistant, 'call_model', return_value={'answer': 'ok'}) as model:
                response = self.client.post('/api/v1/assistant/preview', data={'scope': 'map', 'message': 'hello',
                                            'web': 'false', 'mode': 'smart', 'effort': effort})
            self.assertEqual(response.status_code, 200, response.json)
            self.assertEqual(model.call_args.args[1]['ASSISTANT_EFFORT'], effort)

    def test_passcode_confirmation_checks_service_hash_without_model_or_files(self):
        from backend.map_predict.services.ai_settings import set_passcode
        self.app.config['AI_SETTINGS_FILE'] = str(Path(self.folder.name) / 'settings.json')
        set_passcode(self.app.config, 'temporary-test-passcode')
        with patch.object(assistant, 'call_model') as model:
            rejected = self.client.post('/api/v1/assistant/authorize', data={'passcode': 'incorrect', 'mode': 'fast'})
            self.assertEqual(rejected.status_code, 403)
            accepted = self.client.post('/api/v1/assistant/authorize', data={'passcode': 'temporary-test-passcode'})
            self.assertEqual(accepted.status_code, 200)
            self.assertEqual(accepted.json['data'], {'authorized': True})
            self.assertNotIn('temporary-test-passcode', accepted.get_data(as_text=True))
            model.assert_not_called()
            set_passcode(self.app.config, 'updated-test-passcode')
            expired = self.client.post('/api/v1/assistant/authorize', data={'passcode': 'temporary-test-passcode'})
            self.assertEqual(expired.status_code, 403)

    def test_model_request_sends_effort_without_changing_model_or_default(self):
        remote = Mock()
        remote.__enter__ = Mock(return_value=remote)
        remote.__exit__ = Mock(return_value=False)
        remote.read.return_value = b'{"choices":[{"message":{"content":"{\\"answer\\":\\"ok\\"}"}}]}'
        opener = Mock()
        opener.open.return_value = remote
        for model in ('gemini-3.6-flash', 'gemini-4-argon'):
            for effort in ('auto', 'low', 'medium', 'high'):
                with patch.object(assistant, 'build_opener', return_value=opener):
                    assistant.call_model([], {**self.app.config, 'ASSISTANT_MODEL': model, 'ASSISTANT_EFFORT': effort})
                payload = json.loads(opener.open.call_args.args[0].data)
                self.assertEqual(opener.open.call_args.kwargs['timeout'], 150)
                self.assertEqual(payload['model'], model)
                if effort == 'auto':
                    self.assertNotIn('reasoning_effort', payload)
                else:
                    self.assertEqual(payload['reasoning_effort'], effort)

    def test_upstream_effort_mismatch_is_reported_without_claiming_success(self):
        from urllib.error import HTTPError
        from backend.map_predict.services.prediction import PredictionError
        for model in ('gemini-3.6-flash', 'gemini-4-argon'):
            error = HTTPError('http://test/chat/completions', 503, 'Unavailable', {},
                             io.BytesIO(b'{"error":{"code":"effort_not_applied"}}'))
            opener = Mock()
            opener.open.side_effect = error
            with patch.object(assistant, 'build_opener', return_value=opener):
                with self.assertRaises(PredictionError) as result:
                    assistant.call_model([], {**self.app.config, 'ASSISTANT_MODEL': model})
            self.assertEqual(result.exception.code, 'EFFORT_NOT_APPLIED')

    def test_metadata_json_is_accepted_only_by_the_internal_filter_response_path(self):
        from backend.map_predict.services.prediction import PredictionError
        remote = Mock()
        remote.__enter__ = Mock(return_value=remote)
        remote.__exit__ = Mock(return_value=False)
        remote.read.return_value = json.dumps({'choices': [{'message': {'content':
            '```json\n{"so_tieu_chi":1,"phan_nhom":"đồng bằng"}\n```'}}]}).encode()
        opener = Mock()
        opener.open.return_value = remote
        with patch.object(assistant, 'build_opener', return_value=opener):
            result = assistant.call_model([], self.app.config, response_kind='filters')
            self.assertEqual(result, {'so_tieu_chi': 1, 'phan_nhom': 'đồng bằng'})
            with self.assertRaises(PredictionError):
                assistant.call_model([], self.app.config)

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

    def table_preview(self, edits, message='Xóa dòng đầu, xóa custom và sửa x1 thành 7', csv=None, scope='prediction', **result):
        source = self.csv if csv is None else csv
        with patch.object(assistant, 'call_model', return_value={
                'answer': 'Đề xuất sửa bảng', 'table_edits': edits, **result}):
            response = self.client.post('/api/v1/assistant/preview', data={
                'csv': (io.BytesIO(source), 'table.csv'), 'message': message, 'scope': scope, 'web': 'false'})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['data']

    def table_apply(self, preview, csv=None):
        return self.client.post('/api/v1/assistant/apply', data={'scope': 'prediction',
            'csv': (io.BytesIO(self.csv if csv is None else csv), 'table.csv'), 'token': preview['token']})

    def test_table_edit_delete_row_and_column_use_original_indexes_and_stale_guard(self):
        edits = [{'operation': 'delete_row', 'row_index': 0},
                 {'operation': 'delete_column', 'column': 'custom'},
                 {'operation': 'set_cell', 'row_index': 1, 'column': 'x1', 'value': 7,
                  'quote': 'sửa x1 thành 7'}]
        preview = self.table_preview(edits)
        self.assertEqual(len(preview['table_edits']), 3)
        self.assertEqual(preview['table_edits'][0]['before']['id'], 'A1')
        self.assertEqual(preview['table_edits'][1]['affected_rows'], 2)
        response = self.table_apply(preview)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['data']['rows'], [{'id': 'A2', 'x1': 7, 'x4': '4'}])
        self.assertEqual(response.json['data']['columns'], ['id', 'x1', 'x4'])
        self.assertIn(b'also-keep', self.csv)
        self.assertEqual(self.table_apply(preview, csv=self.csv + b'A3,,,,\n').status_code, 409)

    def test_table_can_delete_all_rows_and_keep_headers_without_creating_new_csv(self):
        preview = self.table_preview([{'operation': 'delete_row', 'row_index': 0},
                                      {'operation': 'delete_row', 'row_index': 1}], message='Xóa hai dòng')
        response = self.table_apply(preview)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['data']['rows'], [])
        self.assertEqual(response.json['data']['columns'], ['id', 'x1', 'x4', 'custom'])
        blank = self.table_preview([], csv=b'id,x1,x4,custom\r\n')
        self.assertIsNone(blank['token'])
        self.assertFalse(blank['create_table'])
        from backend.map_predict.services.prediction import read_csv
        from backend.map_predict.services.prediction import PredictionError
        with self.assertRaises(PredictionError):
            read_csv(b'id,x1\r\n', 100)

    def test_scoring_a_missing_criterion_retains_its_column_in_export_schema(self):
        source = b'id,x1\nA1,3\n'
        preview = self.table_preview([], csv=source, message='Ô A1 là đất nông nghiệp xen kẹt', scores=[
            {'row_index': 0, 'column': 'x4', 'value': 9, 'rule': 'L9',
             'evidence': 'USER', 'quote': 'đất nông nghiệp xen kẹt'}])
        response = self.table_apply(preview, csv=source)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['data']['columns'], ['id', 'x1', 'x4'])
        self.assertEqual(response.json['data']['rows'][0]['x4'], 9)

    def test_table_edits_reject_unknown_cells_guessed_scores_and_model_output(self):
        invalid = [None, {'operation': 'run_code'},
            {'operation': 'delete_row', 'row_index': -1}, {'operation': 'delete_row', 'row_index': True},
            {'operation': 'delete_column', 'column': 'missing'},
            {'operation': 'set_cell', 'row_index': 0, 'column': 'missing', 'value': '7'},
            {'operation': 'set_cell', 'row_index': 0, 'column': 'Y', 'value': 2},
            {'operation': 'set_cell', 'row_index': 0, 'column': 'x1', 'value': 5, 'quote': 'sửa x1 thành 7'},
            {'operation': 'set_cell', 'row_index': 0, 'column': 'x1', 'value': 7, 'quote': 'Người dùng chưa nói'},
            {'operation': 'set_cell', 'row_index': 0, 'column': 'x1', 'value': float('nan')}]
        preview = self.table_preview(invalid)
        self.assertEqual(len(preview['rejected']), len(invalid))
        self.assertIsNone(preview['token'])
        self.assertEqual(preview['table_edits'], [])
        # A number inside a different number is not an explicitly supplied value.
        preview = self.table_preview([{'operation': 'set_cell', 'row_index': 0, 'column': 'x1',
                                      'value': 1, 'quote': 'sửa x1 thành 10'}], message='sửa x1 thành 10')
        self.assertIsNone(preview['token'])

    def test_table_edit_conflicts_are_rejected_and_last_input_column_is_retained(self):
        preview = self.table_preview([
            {'operation': 'set_cell', 'row_index': 0, 'column': 'x1', 'value': 7, 'quote': 'sửa x1 thành 7'},
            {'operation': 'delete_row', 'row_index': 0}, {'operation': 'delete_column', 'column': 'x1'},
            {'operation': 'delete_row', 'row_index': 1}, {'operation': 'delete_row', 'row_index': 1}])
        self.assertEqual(len(preview['table_edits']), 2)
        self.assertEqual(len(preview['rejected']), 3)
        last = self.table_preview([{'operation': 'delete_column', 'column': 'id'}], csv=b'id,Y\nA1,2\n')
        self.assertIsNone(last['token'])
        self.assertTrue(last['rejected'])

    def test_manual_text_edit_and_clearing_are_supported_without_automatic_scoring(self):
        message = 'Sửa custom thành mới, xóa nội dung x1'
        preview = self.table_preview([
            {'operation': 'set_cell', 'row_index': 0, 'column': 'custom', 'value': 'mới', 'quote': 'Sửa custom thành mới'},
            {'operation': 'set_cell', 'row_index': 1, 'column': 'x1', 'value': '', 'quote': 'xóa nội dung x1'}], message=message)
        response = self.table_apply(preview)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['data']['rows'][0]['custom'], 'mới')
        self.assertEqual(response.json['data']['rows'][1]['x1'], '')

    def test_map_scope_cannot_edit_csv_with_table_edits(self):
        with patch.object(assistant, 'call_model', return_value={'answer': 'Đề xuất', 'table_edits': [
                {'operation': 'delete_column', 'column': 'id'}]}):
            response = self.client.post('/api/v1/assistant/preview', data={'scope': 'map', 'message': 'Xóa cột', 'web': 'false'})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['data']['table_edits'], [])
        self.assertIsNone(response.json['data']['token'])

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
