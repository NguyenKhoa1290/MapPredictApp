import json
import unittest
from unittest.mock import patch

from ai_service.services.assistant_context import bound, preview, validate_patch
from shared.tabular import PredictionError


class ContextTests(unittest.TestCase):
    def test_budget_removes_old_turns_but_never_truncates_current_data(self):
        messages = [{'role': 'system', 'content': 'rules'},
                    {'role': 'user', 'content': 'a' * 78000},
                    {'role': 'user', 'content': 'current layer'}]
        result, usage = bound(messages)
        self.assertEqual(result, [messages[0], messages[-1]])
        self.assertEqual(usage['limit'], 30000)
        self.assertTrue(usage['estimated'])
        with self.assertRaises(PredictionError):
            bound([messages[0], {'role': 'user', 'content': 'a' * 80000}])

    def test_patch_rejects_geometry_unknown_fields_and_out_of_range(self):
        for patch_value in ({'geometry': {}}, {'style': {'weight': 9}},
                            {'style': {'color': 'red'}}, {'adjustments': {'invert': -1}},
                            {'opacity': float('nan')}, {'style': {'weight': True}}):
            with self.subTest(patch=patch_value), self.assertRaises(ValueError):
                validate_patch(patch_value)
        self.assertEqual(validate_patch({'style': {'color': '#00ff00', 'dashArray': '8 5'},
                                         'adjustments': {'hue': 60}, 'opacity': 0.5})['opacity'], 0.5)
        self.assertEqual(validate_patch({'style': {'east': 20, 'north': -10}}), {'style': {'east': 20, 'north': -10}})
        with self.assertRaises(ValueError):
            validate_patch({'style': {'east': 100001}})

    def test_inspector_returns_only_validated_patch_without_opening_dxf(self):
        options = {'message': 'Change the selected layer', 'layer_context': json.dumps({
            'id': 'base-1', 'component': 'net', 'style': {'color': '#00ff00'}}), 'history': []}
        with patch('ai_service.services.assistant.call_model', return_value={
                'answer': 'Preview', 'layer_patch': {'style': {'weight': 3}},
                'edits': [{'operation': 'delete'}]}) as model, patch('ezdxf.readfile') as read:
            result = preview(options, {})
        read.assert_not_called()
        self.assertEqual(result['layer_patch'], {'style': {'weight': 3}})
        self.assertEqual(result['edits'], [])
        self.assertIn('net', model.call_args.args[0][-1]['content'])
        self.assertIsNone(result['token'])

    def test_compact_cannot_create_mutations(self):
        with patch('ai_service.services.assistant.call_model', return_value={
                'answer': 'summary', 'layer_patch': {'opacity': 0}}):
            result = preview({'compact': 'true', 'message': 'Summarize', 'history': [
                {'role': 'user', 'content': 'Remember the green layer'}]}, {})
        self.assertIsNone(result['layer_patch'])
        self.assertTrue(result['compact'])
