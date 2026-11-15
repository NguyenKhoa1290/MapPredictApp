import copy
import unittest

from ai_service.services.assistant_prompt import RESPONSE_CONTRACT, TURN_REMINDER, with_response_contract


class AssistantPromptTests(unittest.TestCase):
    def test_every_turn_repeats_contract_without_mutating_history_or_scope(self):
        messages = [{'role': 'system', 'content': 'Only modify the selected layer'},
                    {'role': 'user', 'content': 'Previous request'},
                    {'role': 'assistant', 'content': 'Previous answer'},
                    {'role': 'user', 'content': 'Change its color'}]
        original = copy.deepcopy(messages)
        for _ in range(2):
            result = with_response_contract(messages)
            self.assertEqual(result[0], {'role': 'system', 'content': RESPONSE_CONTRACT})
            self.assertEqual(result[1], original[0])
            self.assertEqual(result[2:4], original[1:3])
            self.assertTrue(result[-1]['content'].endswith(TURN_REMINDER))
            self.assertEqual(result[-1]['content'].count(TURN_REMINDER), 1)
        self.assertEqual(messages, original)

    def test_contract_is_present_without_user_message(self):
        result = with_response_contract([])
        self.assertEqual(result, [{'role': 'system', 'content': RESPONSE_CONTRACT}])

    def test_context_budget_accounts_for_contract_and_tail_reminder(self):
        from ai_service.services.assistant_context import bound, estimate
        messages = [{'role': 'system', 'content': 'instructions'}, {'role': 'user', 'content': 'question'}]
        _, usage = bound(messages)
        self.assertEqual(usage['used'], sum(estimate(row['content']) for row in messages)
                         + estimate(RESPONSE_CONTRACT) + estimate(TURN_REMINDER))
