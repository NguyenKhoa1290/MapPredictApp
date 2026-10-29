import unittest
from unittest.mock import patch, Mock

from backend.map_predict.services import knowledge, assistant
from backend.map_predict.services.prediction import PredictionError


POINT = {'id': 'point-1', 'payload': {'page_content': 'sửa ngày 1509 | 4. Hiện trạng sử dụng đất\n'
         '- **source_ref:** `sửa ngày 1509!L9`\n- **record_id:** `S3-L9`\n'
         '| 9 | `L9` | Đất nông nghiệp xen kẹt |',
         'metadata': {'file_name': 'Tieuchi.md', 'source': '/private/path/not-for-the-client'}}}


class KnowledgeTests(unittest.TestCase):
    config = {'ASSISTANT_QDRANT_URL': 'http://qdrant:6333', 'ASSISTANT_QDRANT_COLLECTION': 'CSDL-Datdai',
              'ASSISTANT_EMBEDDING_URL': 'http://embedding:11434',
              'ASSISTANT_EMBEDDING_MODEL': 'qwen3-embedding:0.6b'}

    def keyword(self, query, points):
        replies = [{'result': {'config': {'params': {'vectors': {'size': 1024}}}, 'points_count': len(points)}},
                   {'result': {'points': points, 'next_page_offset': None}}]
        with patch.object(knowledge, 'json_request', side_effect=replies) as request:
            result = knowledge.retrieve(query, {**self.config, 'ASSISTANT_RETRIEVAL_MODE': 'keyword'})
        self.assertTrue(all('/api/embed' not in call.args[0] for call in request.call_args_list))
        return result

    def mixed_point(self):
        content = '### sửa ngày 1509 | Tiêu đề và nhãn thang điểm\n- **record_id:** `S3-HEADERS`\n- **source_ref:** `sửa ngày 1509!A1:T2`\n'
        for row, group, threshold in [(3, 'ĐỒNG BẰNG', '<2m'), (4, 'ĐỒI THẤP/TRUNG DU', '200-300m'),
                                      (5, 'CAO NGUYÊN', '> 1600m'), (6, 'NÚI', '>1700m')]:
            content += f'### sửa ngày 1509 | 1. Cao độ nền địa hình | {group}\n'
            content += f'- **source_ref:** `sửa ngày 1509!A{row}:T{row}`\n- **record_id:** `S3-R{row}`\n'
            content += '- **Tiêu chí:** 1. Cao độ nền địa hình\n- **Định lượng:** Dữ liệu số độ cao (DEM)\n'
            content += f'#### sửa ngày 1509 | 1. Cao độ nền địa hình | {group} | Ngưỡng và nhãn điểm\n'
            content += f'| 1 / 2 / 3 | `D{row}:F{row}` | {threshold} |\n'
        content += '### sửa ngày 1509 | 2. Độ dốc\n| 1 / 2 / 3 | `D7:F7` | >30% |\n'
        content += '### sửa ngày 1509 | 6. Sự phù hợp quy hoạch\n| 9 | `L11` | Phù hợp quy hoạch |\n'
        return {'id': '59929946-642c-45bb-a3a0-5b7a4e8394cd', 'payload': {'page_content': content,
                'metadata': {'file_name': 'Tieuchi.md', 'so_tieu_chi': 7, 'source_ref': 'sửa ngày 1509!a3:t3'}}}

    def test_column_and_ordinal_queries_return_the_complete_correct_criterion(self):
        for query in ('x1', 'Tiêu chí thứ nhất', 'cao độ nền địa hình'):
            with self.subTest(query=query):
                result = self.keyword(query, [self.mixed_point()])
                self.assertEqual(len(result['records']), 1)
                record = result['records'][0]
                self.assertEqual(record['id'], '59929946-642c-45bb-a3a0-5b7a4e8394cd')
                for group in ('ĐỒNG BẰNG', 'ĐỒI THẤP/TRUNG DU', 'CAO NGUYÊN', 'NÚI'):
                    self.assertIn(group, record['content'])
                self.assertIn('S3-HEADERS', record['content'])
                self.assertNotIn('2. Độ dốc', record['content'])
                parsed = assistant.rules(record['content'])
                self.assertEqual({row['column'] for row in parsed.values()}, {'x1'})
                self.assertEqual(parsed['D3:F3']['points'], [1, 2, 3])
                self.assertEqual(parsed['D4:F4']['threshold'], '200-300m')

    def test_actual_sections_override_inaccurate_chunk_metadata(self):
        for query in ('x6', 'tiêu chí 6', 'sự phù hợp quy hoạch'):
            result = self.keyword(query, [self.mixed_point()])
            parsed = assistant.rules(result['records'][0]['content'])
            self.assertEqual(set(parsed), {'L11'})
            self.assertEqual(parsed['L11']['column'], 'x6')

    def test_direct_lookup_reaches_criteria_after_the_first_200_points_without_embedding(self):
        pages = [{'result': {'points': [{'id': str(i), 'payload': {}} for i in range(n, n + 50)],
                             'next_page_offset': str(n + 50)}} for n in range(0, 200, 50)]
        pages.append({'result': {'points': [self.mixed_point()], 'next_page_offset': None}})
        info = {'result': {'points_count': 201}}
        with patch.object(knowledge, 'json_request', side_effect=[info, *pages]) as call:
            result = knowledge.retrieve('x1', {**self.config, 'ASSISTANT_RETRIEVAL_MODE': 'keyword'})
        self.assertEqual(result['mode'], 'keyword')
        self.assertEqual(result['scanned_points'], 201)
        self.assertEqual(result['records'][0]['id'], self.mixed_point()['id'])
        self.assertTrue(all('/api/embed' not in item.args[0] for item in call.call_args_list))
        self.assertTrue(all(item.args[1]['with_vector'] is False for item in call.call_args_list[1:]))

    def test_repeated_scroll_offset_fails_instead_of_returning_incomplete_criteria(self):
        page = {'result': {'points': [], 'next_page_offset': 'repeat'}}
        with patch.object(knowledge, 'json_request', side_effect=[{'result': {}}, page, page]):
            with self.assertRaises(PredictionError):
                knowledge.retrieve('x1', {**self.config, 'ASSISTANT_RETRIEVAL_MODE': 'keyword'})

    def test_comparison_queries_keep_requested_criteria_and_exclude_other_thresholds(self):
        result = self.keyword('So sánh x1 và x6', [self.mixed_point()])
        parsed = assistant.rules(result['records'][0]['content'])
        self.assertEqual({row['column'] for row in parsed.values()}, {'x1', 'x6'})
        self.assertNotIn('D7:F7', parsed)
        self.assertEqual(knowledge.requested_criteria('tiêu chí 1 và 2 và 6, điểm 9'), {1, 2, 6})
        self.assertEqual(knowledge.requested_criteria('Tiêu chí thứ hai'), {2})

    def test_old_document_versions_cannot_occupy_keyword_results(self):
        current = self.mixed_point()
        old = {'id': 'old', 'payload': {'page_content': current['payload']['page_content'].replace('1509', '2024')}}
        result = self.keyword('x1', [old, current])
        self.assertEqual([row['id'] for row in result['records']], [current['id']])

    def test_dense_query_uses_matching_embedding_and_existing_collection(self):
        responses = [{'result': {'config': {'params': {'vectors': {'size': 3}}}, 'points_count': 5}},
                     {'embeddings': [[.1, .2, .3]]}, {'result': {'points': [POINT]}}]
        with patch.object(knowledge, 'json_request', side_effect=responses) as request:
            result = knowledge.retrieve('Đất nông nghiệp xen kẹt', self.config)
        self.assertEqual(result['mode'], 'dense')
        self.assertEqual(result['records'][0]['id'], 'point-1')
        self.assertEqual(request.call_args.args[1]['query'], [.1, .2, .3])
        self.assertTrue(request.call_args.args[0].endswith('/points/query'))
        self.assertNotIn('/private/path', str(result))
        self.assertEqual(assistant.rules(result['records'][0]['content'])['L9']['column'], 'x4')

    def test_dimension_mismatch_uses_explicit_keyword_fallback_without_reindexing(self):
        responses = [{'result': {'config': {'params': {'vectors': {'size': 1024}}}}},
                     {'embeddings': [[.1, .2]]}, {'result': {'points': [POINT], 'next_page_offset': None}}]
        with patch.object(knowledge, 'json_request', side_effect=responses) as request:
            result = knowledge.retrieve('đất nông nghiệp', self.config)
        self.assertEqual(result['mode'], 'keyword_fallback')
        self.assertEqual(len(result['records']), 1)
        self.assertTrue(request.call_args.args[0].endswith('/points/scroll'))
        self.assertNotIn('vectors', request.call_args.args[1])

    def test_configured_qdrant_outage_does_not_silently_use_local_document(self):
        with patch.object(knowledge, 'json_request', side_effect=OSError('offline')):
            with self.assertRaises(PredictionError) as error:
                knowledge.retrieve('độ dốc', self.config)
        self.assertEqual(error.exception.code, 'KNOWLEDGE_UNAVAILABLE')

    def test_ragwire_failure_reports_keyword_fallback_without_leaking_internal_json(self):
        import sys
        from types import SimpleNamespace
        adapter = SimpleNamespace(retrieve=Mock(side_effect=ValueError('internal JSON /private/path')))
        replies = [{'result': {'config': {'params': {'vectors': {'size': 1024}}}, 'points_count': 1}},
                   {'result': {'points': [POINT], 'next_page_offset': None}}]
        with patch.dict(sys.modules, {'backend.map_predict.services.ragwire_search': adapter}), \
                patch.object(knowledge, 'json_request', side_effect=replies):
            result = knowledge.retrieve('x4', {**self.config, 'ASSISTANT_RETRIEVAL_MODE': 'ragwire'})
        self.assertEqual(result['mode'], 'keyword_fallback')
        self.assertEqual(result['records'][0]['id'], 'point-1')
        self.assertNotIn('internal JSON', str(result))

    def test_paragraph_score_rules_do_not_become_wrong_criteria_from_table_points(self):
        text = '### sửa ngày 1509 | 7 Chi phí GPMB\n#### sửa ngày 1509 | 7 Chi phí GPMB | Nhãn điểm hàng 1: 9\n'
        text += '- **source_ref:** `sửa ngày 1509!L12`\n- **Tiêu chí:** 7 Chi phí GPMB\n'
        text += '### sửa ngày 1509 | 4. Hiện trạng sử dụng đất\n| 9 | `L9` | Đất nông nghiệp xen kẹt |'
        rules = assistant.rules(text)
        self.assertEqual(rules['L12']['column'], 'x7')
        self.assertEqual(rules['L12']['points'], [9])
        self.assertEqual(rules['L9']['column'], 'x4')


if __name__ == '__main__':
    unittest.main()
