import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

class ChatRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import httpx
        except ImportError:
            raise unittest.SkipTest('Gemini dependencies are installed in the Gemini service image')
        global ChatRetention, group_key, read_response
        cls.previous_path = list(sys.path)
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'integrations'))
        from gemini_web2api.chat_retention import ChatRetention, group_key
        from gemini_web2api.gemini import read_response

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'previous_path'):
            sys.path[:] = cls.previous_path

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = ChatRetention(Path(self.temp.name) / 'config.json')

    def test_idle_expiry_survives_restart_and_only_deletes_owned_ids(self):
        self.journal.touch('old', 'c_owned', now=100)
        self.journal.touch('active', 'c_active', now=3699)
        replies = lambda rpc, *args, **kwargs: json.dumps([['wrb.fr', rpc, 'null']])
        with patch('gemini_web2api.chat_retention.GoogleSession.request_rpc', side_effect=replies) as rpc:
            restored = ChatRetention(self.journal.config_path)
            self.assertEqual(restored.cleanup(now=3700), 1)
            self.assertEqual([call.args[0] for call in rpc.call_args_list], ['GzXR5e', 'qWymEb'])
            self.assertTrue(all('c_owned' in call.args[1] for call in rpc.call_args_list))
        self.assertEqual(list(restored.load()), [group_key('active')])

    def test_new_activity_extends_entire_group_and_failed_delete_is_retried(self):
        self.journal.touch('group', 'c_first', now=0)
        self.journal.touch('group', 'c_second', now=3500)
        with patch('gemini_web2api.chat_retention.GoogleSession.request_rpc', side_effect=TimeoutError):
            self.assertEqual(self.journal.cleanup(now=3600), 0)
            self.assertEqual(self.journal.cleanup(now=7100), 0)
        self.assertEqual(self.journal.load()[group_key('group')]['chats'], ['c_first', 'c_second'])

    def test_stream_captures_id_before_timeout_without_storing_content(self):
        frame = json.dumps([['wrb.fr', None, json.dumps([None, ['c_created', 'r_reply'], 'secret prompt'])]]) + '\n'
        class Interrupted(io.BytesIO):
            def read1(self, size):
                if self.tell() == len(self.getvalue()):
                    raise TimeoutError()
                return super().read1(7)
        with self.assertRaises(TimeoutError):
            read_response(Interrupted(frame.encode()), observer=self.journal.observer('session'))
        self.assertEqual(self.journal.load()[group_key('session')]['chats'], ['c_created'])
        self.assertNotIn('secret', self.journal.path.read_text())

    def test_missing_acknowledgement_keeps_pending_record(self):
        self.journal.touch('old', 'c_owned', now=0)
        with patch('gemini_web2api.chat_retention.GoogleSession.request_rpc', return_value='[]'):
            self.assertEqual(self.journal.cleanup(now=3600), 0)
        self.assertTrue(self.journal.load())
