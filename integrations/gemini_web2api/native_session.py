"""Authenticated Argon WebChannel transport, bounded by the caller's deadline."""
import base64
import hashlib
import json
import random
import time
import uuid
from contextlib import contextmanager

import httpx

from .config import CONFIG
from .gemini import load_cookie
from .native_wire import Frames, at, fields, get, message as m
from .quota_guard import QuotaRejected

ENDPOINT = 'https://geminiweb-pa.clients6.google.com/v1/processSession'


def rejected(code, status=503):
    return QuotaRejected('Gemini không hoàn thành yêu cầu (' + code + ')', status=status, code=code)


def headers(cookies, key, build, effort, request_id):
    stamp = str(int(time.time()))
    timing = m((1, m((1, 1), (2, 0))), (2, m((1, int(stamp)), (2, 0))), (3, 'Asia/Saigon'))
    auth = []
    for label, name in (('SAPISIDHASH', 'SAPISID'), ('SAPISID1PHASH', '__Secure-1PAPISID'), ('SAPISID3PHASH', '__Secure-3PAPISID')):
        if cookies.get(name):
            digest = hashlib.sha1(f'{stamp} {cookies[name]} https://gemini.google.com'.encode()).hexdigest()
            auth.append(f'{label} {stamp}_{digest}')
    if not auth or not key or not build:
        raise rejected('native_session_required')
    capabilities = {}
    route_header = (CONFIG.get('model_headers') or {}).get('8', {}).get('x-goog-ext-525001261-jspb')
    if route_header:
        catalog = json.loads(route_header)
        capabilities = {index + 1: catalog[index] for index in (11, 12) if len(catalog) > index and type(catalog[index]) is int}
    if not capabilities:
        capabilities = {12: 2}
    binary = {
        '525001261': m((1, 1), (5, 'argon'), (7, 'en'), (8, 0), (9, bytes([4, 33, 22, 5, 6, 8, 16, 19, 20])),
                      *capabilities.items(), (15, 8), (16, effort), (17, str(uuid.uuid4()).upper()),
                      (18, m((1, build))), (20, timing), (25, 'argon')),
        '73010989': m((1, 0)), '73010990': m((1, 0), (2, 0), (3, 0)),
        '525005358': m((1, str(uuid.uuid4()).upper()), (2, 1)),
    }
    return {'Authorization': ' '.join(auth),
            'X-Goog-AuthUser': str(CONFIG.get('auth_user') or 0), 'X-Goog-Api-Key': key,
            'X-WebChannel-Content-Type': 'application/x-protobuf',
            **{f'x-goog-ext-{number}-bin': base64.b64encode(value).decode() for number, value in binary.items()}}


def payloads(prompt, effort, request_id, session=None):
    session = session or {}
    args = [(1, m((1, b''), (2, 0), (7, 0))), (2, m((1, 'en'))), (5, uuid.uuid4().hex),
            (7, m((1, 0))), (8, 1), (11, 1), (12, 0), (18, m((1, m((1, session.get('turns', 0)))))),
            (19, 0), (28, 1), (31, bytes([4, 16, 19])), (42, m((1, 1))), (50, 0), (54, 0),
            (60, request_id), (62, b''), (68, 0), (69, 1), (80, 8), (81, effort), (92, 1),
            (97, int(not session.get('cid') or session.get('model_mode', 8) != 8)), (99, 1)]
    if session.get('cid'):
        args.append((72, m((1, session['cid']), (8, session.get('token', '')))))
    context = m((1, 1), (2, 'argon'), (3, 'en'), (4, request_id))
    init = m((1, m((1, context), (2, 0), (8, m((5, m((1, m(*args)), (4, 1))))))))
    question = m((2, m((1, 1), (9, m((1, prompt))))))
    return {'count': '2', 'ofs': '0', 'req0___data__': base64.b64encode(init).decode(),
            'req1___data__': base64.b64encode(question).decode()}


def events(value):
    if isinstance(value, dict):
        if '__sm__' in value and isinstance(value['__sm__'], dict):
            status = value['__sm__'].get('status')
            if isinstance(status, list) and status and isinstance(status[0], list) and status[0]:
                first = status[0][0]
                if isinstance(first, list) and first and type(first[0]) is int and first[0]:
                    raise rejected('cookie_required' if first[0] == 16 else 'native_upstream_rejected')
        if 'error' in value:
            code = value['error'].get('code') if isinstance(value['error'], dict) else None
            raise rejected('quota_exhausted' if code == 429 else 'native_upstream_rejected', 429 if code == 429 else 503)
        for item in value.values():
            yield from events(item)
    elif isinstance(value, list):
        for item in value:
            yield from events(item)
    elif isinstance(value, str) and value not in ('noop', 'close', 'stop'):
        try:
            decoded = base64.b64decode(value, validate=True)
            response = at(decoded, 2, 7, 1, 4, 4)
        except ValueError:
            return
        if response:
            yield response


def generate_native(prompt, effort, metadata=None):
    from .chat_retention import ChatRetention
    raw, _ = load_cookie()
    cookies = dict(part.strip().split('=', 1) for part in raw.split(';') if '=' in part)
    deadline = CONFIG.get('generation_deadline') or time.monotonic() + 300
    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError()
        return httpx.Timeout(value, connect=min(10, value))
    request_id = str(uuid.uuid4()).upper()
    auth = headers(cookies, CONFIG.get('native_api_key'), CONFIG.get('gemini_bl'), effort, request_id)
    jar = httpx.Cookies()
    for name, value in cookies.items():
        jar.set(name, value, domain='.google.com', path='/')
    journal = ChatRetention(CONFIG['audit_config_path']) if CONFIG.get('audit_config_path') else None
    group = CONFIG.get('chat_group', request_id)
    session = CONFIG.get('chat_session') or {}
    observed = {}
    completed_text = None
    current_cid = session.get('cid')
    last_snapshot = None
    query = {'VER': '8', 'RID': str(random.randint(10000, 50000)), 'CVER': '22', 'X-HTTP-Session-Id': 'gsessionid', 't': '1'}
    def check(reply):
        if reply.status_code != 200:
            raise rejected('quota_exhausted' if reply.status_code == 429 else 'native_http_rejected', 429 if reply.status_code == 429 else 503)
    try:
        with httpx.Client(headers=auth, cookies=jar, trust_env=False) as client:
            reply = client.post(ENDPOINT, params=query, data={'count': '0'}, timeout=remaining())
            check(reply)
            sid = None
            for frame in Frames().feed(reply.content):
                for _, value in frame:
                    if isinstance(value, list) and value and value[0] == 'c':
                        sid = value[1]
            if not sid or not reply.headers.get('x-http-session-id'):
                raise rejected('native_handshake_failed')
            query = {'VER': '8', 'gsessionid': reply.headers['x-http-session-id'], 'SID': sid,
                     'RID': str(int(query['RID']) + 1), 'AID': '0', 't': '1'}
            next_rid = int(query['RID'])
            try:
                uploads = payloads(prompt, effort, request_id, session)
                def post(offset, data):
                    nonlocal next_rid
                    parameters = {k: v for k, v in query.items() if k not in ('CI', 'TYPE')}
                    parameters['RID'] = str(next_rid)
                    next_rid += 1
                    try:
                        result = client.post(ENDPOINT, params=parameters,
                                             data={'count': '1', 'ofs': str(offset), 'req0___data__': data}, timeout=remaining())
                    except httpx.TimeoutException:
                        raise TimeoutError() from None
                    check(result)
                initialized = False
                initialized_at = None
                prompt_sent = False
                @contextmanager
                def downstream():
                    timeout = remaining()
                    if not prompt_sent:
                        timeout.read = min(3, timeout.read)
                    with client.stream('GET', ENDPOINT, params=query, timeout=timeout) as response:
                        try:
                            yield response
                        except httpx.ReadTimeout:
                            remaining()  # Reattach the channel, never resend a turn.
                while True:
                    query.update(RID='rpc', CI='0', TYPE='xmlhttp')
                    decoder = Frames()
                    with downstream() as reply:
                        check(reply)
                        if not initialized:
                            post(0, uploads['req0___data__'])
                            initialized = True
                            initialized_at = time.monotonic()
                        for chunk in reply.iter_bytes():
                            remaining()
                            if not prompt_sent and time.monotonic() - initialized_at >= 3:
                                prompt_sent = True
                                time.sleep(max(0, min(0.5, deadline - time.monotonic())))
                                post(1, uploads['req1___data__'])
                            for frame in decoder.feed(chunk):
                                for sequence, value in frame:
                                    query['AID'] = str(sequence)
                                    if value == [base64.b64encode(m((4, b''))).decode()]:
                                        if completed_text is None:
                                            raise rejected('native_incomplete_response')
                                        return completed_text
                                    # The server must acknowledge initialization before
                                    # user input. Combining both messages races startup.
                                    if not prompt_sent and isinstance(value, list) and value == [base64.b64encode(m((1, b''))).decode()]:
                                        remaining()
                                        time.sleep(max(0, min(0.5, deadline - time.monotonic())))
                                        prompt_sent = True
                                        post(1, uploads['req1___data__'])
                                    for response in events(value):
                                        for field in (43, 59, 60, 61):
                                            found = get(response, field)
                                            if found is not None:
                                                observed[field] = found
                                        identity = at(response, 2, 1)
                                        if identity:
                                            cid = identity.decode()
                                            if session.get('cid') and cid != session['cid']:
                                                raise rejected('native_conversation_mismatch')
                                            current_cid = cid
                                        if journal and current_cid:
                                            first_candidate = get(response, 5, b'')
                                            token = get(response, 26, b'')
                                            snapshot = (current_cid, (at(response, 2, 2) or b'').decode(),
                                                        (get(first_candidate, 1, b'') or b'').decode(),
                                                        token.decode() if isinstance(token, bytes) else '')
                                            if snapshot != last_snapshot:
                                                journal.update_session(group, *snapshot)
                                                last_snapshot = snapshot
                                        text = ''.join(part.decode() for f, w, candidate in fields(response) if f == 5 and w == 2
                                                       for n, kind, part in fields(get(candidate, 2, b'')) if n == 1 and kind == 2)
                                        if get(response, 47) == 2 and text and completed_text is None:
                                            if observed.get(61) != b'argon' or observed.get(43) != b'4 Argon' or observed.get(59) != 8:
                                                raise rejected('native_model_mismatch')
                                            if observed.get(60) != effort:
                                                raise rejected('effort_not_applied')
                                            if metadata is not None:
                                                metadata.update(applied_level=effort, model_name='4 Argon', variant='argon', transport='processSession')
                                            post(2, base64.b64encode(m((4, m((1, 1))))).decode())
                                            completed_text = text
                                    if value in (['close'], ['stop']):
                                        raise rejected('native_incomplete_response')
                    if initialized and not prompt_sent:
                        # Some channels omit the initialization acknowledgement.
                        # Bound that wait and submit the question exactly once.
                        remaining()
                        time.sleep(max(0, min(0.5, deadline - time.monotonic())))
                        prompt_sent = True
                        post(1, uploads['req1___data__'])
            finally:
                try:
                    client.get(ENDPOINT, params={**query, 'TYPE': 'terminate', 'RID': str(next_rid)}, timeout=2)
                except httpx.HTTPError:
                    pass
    except httpx.TimeoutException:
        raise TimeoutError() from None
    except (httpx.HTTPError, ValueError, UnicodeError):
        raise rejected('native_protocol_error') from None
