import unittest
from unittest.mock import patch

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
