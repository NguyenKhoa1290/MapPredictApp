import base64
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


class NativeSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import httpx
        except ImportError:
            raise unittest.SkipTest('Requires Gemini image dependencies')
        cls.previous = list(sys.path)
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'integrations'))

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'previous'):
            sys.path[:] = cls.previous

    def test_fragmented_utf8_frame_and_multiple_frames(self):
        from gemini_web2api.native_wire import Frames
        payload = json.dumps([[1, ['đất']]], ensure_ascii=False).encode()
        encoded = str(len(payload)).encode() + b'\n' + payload
        decoder = Frames()
        output = []
        for byte in encoded * 2:
            output.extend(decoder.feed(bytes([byte])))
        self.assertEqual(output, [[[1, ['đất']]], [[1, ['đất']]]])

    def test_malformed_and_oversized_wire_rejected(self):
        from gemini_web2api.native_wire import Frames, fields
        for raw in (b'\x08\x80', b'\x0a\x05x', b'\x00', b'\x08' + b'\xff' * 10):
            with self.assertRaises(ValueError):
                list(fields(raw))
        with self.assertRaises(ValueError):
            Frames().feed(b'999999999\n')

    def test_header_contains_variant_and_nested_timing_not_uuid(self):
        from gemini_web2api.native_session import headers
        from gemini_web2api.native_wire import at, get
        with patch('gemini_web2api.native_session.time.time', return_value=1000):
            result = headers({'SAPISID': 'test'}, 'api', 'build', 4, 'request')
        model = base64.b64decode(result['x-goog-ext-525001261-bin'])
        self.assertEqual(get(model, 5), b'argon')
        self.assertEqual(get(model, 16), 4)
        self.assertEqual(at(model, 20, 2, 1), 1000)
        self.assertEqual(at(model, 20, 3), b'Asia/Saigon')

    def test_continuation_and_effort_are_encoded(self):
        from gemini_web2api.native_session import payloads
        from gemini_web2api.native_wire import at, get
        data = payloads('question', 2, 'request', {'cid': 'c_test', 'turns': 2, 'token': 't'})
        args = at(base64.b64decode(data['req0___data__']), 1, 8, 5, 1)
        self.assertEqual(get(args, 81), 2)
        self.assertEqual(at(args, 72, 1), b'c_test')
        self.assertEqual(at(args, 18, 1, 1), 2)

    def test_embedded_error_is_not_ignored(self):
        from gemini_web2api.native_session import events
        from gemini_web2api.quota_guard import QuotaRejected
        with self.assertRaises(QuotaRejected) as error:
            list(events({'__sm__': {'status': [[{'error': {'code': 429}}]]}}))
        self.assertEqual(error.exception.code, 'quota_exhausted')
        with self.assertRaises(QuotaRejected) as error:
            list(events({'__sm__': {'status': [[[16, 'missing credentials']]]}}))
        self.assertEqual(error.exception.code, 'cookie_required')

    def native_call(self, response_effort=1, variant='argon', category=8, missing_ack=False):
        import httpx
        from gemini_web2api.config import CONFIG
        from gemini_web2api.native_session import generate_native
        from gemini_web2api.native_wire import message as m
        def frame(value):
            body = json.dumps(value).encode()
            return str(len(body)).encode() + b'\n' + body
        def event(response):
            for field in reversed((2, 7, 1, 4, 4)):
                response = m((field, response))
            return base64.b64encode(response).decode()
        output = m((2, m((1, 'c_unit'))), (5, m((1, 'rc_unit'), (2, m((1, 'answer'))))),
                   (43, '4 Argon'), (47, 2), (59, category), (60, response_effort), (61, variant))
        phases = [event(m((47, 2))), event(output)]
        posts = []
        polls = 0
        class IdleStream(httpx.SyncByteStream):
            def __iter__(self):
                yield frame([[0, ['noop']]])
                raise httpx.ReadTimeout('idle channel')
        def handle(request):
            nonlocal polls
            if request.method == 'POST' and request.content == b'count=0':
                return httpx.Response(200, headers={'x-http-session-id': 'gs'}, content=frame([[0, ['c', 'sid']]]))
            if request.method == 'POST':
                from urllib.parse import parse_qs
                posts.append(parse_qs(request.content.decode())['ofs'][0])
                return httpx.Response(200, content=b'ack')
            if request.url.params.get('TYPE') == 'terminate':
                return httpx.Response(200)
            polls += 1
            if missing_ack and polls == 1:
                return httpx.Response(200, stream=IdleStream())
            payload = frame([[1, [base64.b64encode(m((1, b''))).decode()]]])
            payload += b''.join(frame([[i+2, [value]]]) for i, value in enumerate(phases))
            payload += frame([[4, [base64.b64encode(m((4, b''))).decode()]]])
            return httpx.Response(200, content=payload)
        client = httpx.Client(transport=httpx.MockTransport(handle))
        metadata = {}
        with CONFIG.isolated(), patch('gemini_web2api.native_session.httpx.Client', return_value=client), \
                patch('gemini_web2api.native_session.load_cookie', return_value=('SAPISID=test', 'test')), \
                patch('gemini_web2api.native_session.time.sleep'):
            CONFIG.update(native_api_key='key', gemini_bl='build', audit_config_path=None, chat_session=None, generation_deadline=None)
            result = generate_native('question', 1, metadata)
        return result, metadata, posts

    def test_waits_for_ack_and_finishes_turn_before_returning(self):
        result, metadata, posts = self.native_call()
        self.assertEqual(result, 'answer')
        self.assertEqual(posts, ['0', '1', '2'])
        self.assertEqual(metadata['variant'], 'argon')

    def test_rejects_model_downgrade(self):
        from gemini_web2api.quota_guard import QuotaRejected
        with self.assertRaises(QuotaRejected) as error:
            self.native_call(variant='carbon')
        self.assertEqual(error.exception.code, 'native_model_mismatch')

    def test_rejects_unapplied_effort(self):
        from gemini_web2api.quota_guard import QuotaRejected
        with self.assertRaises(QuotaRejected) as error:
            self.native_call(response_effort=4)
        self.assertEqual(error.exception.code, 'effort_not_applied')

    def test_missing_initialization_ack_does_not_stall_or_duplicate_prompt(self):
        result, metadata, posts = self.native_call(missing_ack=True)
        self.assertEqual(result, 'answer')
        self.assertEqual(posts, ['0', '1', '2'])
