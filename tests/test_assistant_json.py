import json
import unittest

from backend.map_predict.services.assistant_json import model_result, json_object


class AssistantJsonTests(unittest.TestCase):
    def test_bulk_action_output_is_not_cut_at_the_old_500000_character_limit(self):
        edits = [{'operation': 'delete_row', 'row_index': i, 'reason': 'r' * 90} for i in range(5000)]
        raw = json.dumps({'answer': 'Bulk changes', 'table_edits': edits})
        self.assertGreater(len(raw), 500000)
        self.assertEqual(model_result(raw)['table_edits'][-1]['row_index'], 4999)
        self.assertEqual(len(model_result(raw)['table_edits']), 5000)
        with self.assertRaises(ValueError):
            json_object(raw)  # Filter parsing keeps its separate, smaller bound.
        with self.assertRaises(ValueError):
            model_result(raw[:-1])  # Never turn a partial response into a partial plan.

    def test_normal_fenced_prose_and_double_encoded_results_are_decoded(self):
        result = {'answer': 'Nội dung trả lời', 'table_edits': [], 'scores': [], 'edits': []}
        raw = json.dumps(result, ensure_ascii=False)
        for value in (raw, '```json\n' + raw + '\n```', 'Đề xuất như sau\n' + raw,
                      json.dumps(raw), json.dumps({'result': result}),
                      [{'type': 'text', 'text': raw}], json.dumps({'answer': raw})):
            with self.subTest(value=value):
                self.assertEqual(model_result(value), result)

    def test_invalid_ambiguous_and_truncated_output_never_becomes_a_plan(self):
        nested = json.dumps({'answer': 'Nested', 'edits': []})
        for value in ('[]', '{"answer": "truncated"', 'prefix {"answer":"one"} {"answer":"two"}',
                      '{"broken": ' + nested, json.dumps({'answer': 'ok', 'edits': {}}),
                      json.dumps({'answer': nested, 'scores': [{'value': 9}]})):
            with self.subTest(value=value), self.assertRaises(ValueError):
                model_result(value)

    def test_json_examples_in_normal_prose_remain_part_of_the_answer(self):
        answer = 'Ví dụ thuộc tính: {"tenlodat":"A1"}'
        self.assertEqual(model_result(json.dumps({'answer': answer}))['answer'], answer)

    def test_internal_reasoning_blocks_are_not_included_in_display_content(self):
        result = model_result([{'type': 'thinking', 'thinking': 'internal block'},
                               {'type': 'text', 'text': '{"answer":"Nội dung công khai"}'}])
        self.assertEqual(result['answer'], 'Nội dung công khai')
        self.assertNotIn('internal block', str(result))

    def test_internal_rag_json_is_not_rendered_as_the_answer(self):
        for internal in ({'filters': {'so_tieu_chi': 1}}, {'so_tieu_chi': 1, 'phan_nhom': 'đồng bằng'},
                         {'page_content': 'source', 'metadata': {'x': 1}}):
            with self.subTest(internal=internal), self.assertRaises(ValueError):
                model_result(json.dumps({'answer': json.dumps(internal)}))
