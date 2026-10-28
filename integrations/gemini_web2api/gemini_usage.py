"""Read Gemini Web usage windows; never log cookies or raw RPC responses."""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
from .google_session import GoogleSession, UsageAuthError

SAIGON = timezone(timedelta(hours=7))


def nested(value, indexes):
    try:
        for index in indexes:
            value = value[index]
        return value
    except (IndexError, KeyError, TypeError):
        return None


def parse_usage(text):
    bodies = []
    def walk(value):
        if not isinstance(value, list):
            return
        if len(value) > 2 and value[:2] == ['wrb.fr', 'jSf9Qc']:
            if nested(value, [5, 0]) == 7:
                raise UsageAuthError('Google session not accepted')
            if isinstance(value[2], str):
                bodies.append(json.loads(value[2]))
        else:
            for child in value:
                walk(child)
    for line in text.splitlines():
        try:
            walk(json.loads(line))
        except UsageAuthError:
            raise
        except (ValueError, TypeError):
            continue
    result = {'current_5h': None, 'weekly': None}
    for body in bodies:
        for item in nested(body, [1]) or []:
            window = {1: 'current_5h', 2: 'weekly'}.get(nested(item, [2]))
            if window is None:
                continue
            fraction = nested(item, [1])
            timestamp = nested(item, [3, 0, 0])
            percent = None
            if type(fraction) in (int, float) and math.isfinite(fraction) and fraction >= 0:
                percent = math.floor(fraction * 100 + 0.5)
            reset = None
            if type(timestamp) in (int, float) and timestamp > 0:
                try:
                    reset = datetime.fromtimestamp(timestamp, SAIGON).strftime('%d/%m %H:%M GMT+7')
                except (ValueError, OverflowError, OSError):
                    pass
            result[window] = {'used_percent': percent, 'used_fraction': fraction if percent is not None else None,
                              'reset_at': reset, 'reset_unix': timestamp if reset else None}
    if not any(result.values()):
        raise ValueError('Usage windows unavailable')
    result['updated_at'] = datetime.now(SAIGON).strftime('%H:%M:%S')
    return result


class UsageReader:
    def __init__(self, root, config_path=None):
        self.root = Path(root)
        self.config_path = Path(config_path) if config_path else None
        self.sessions = {}

    def fetch(self):
        path = self.config_path or self.root / 'secrets/config.json'
        if self.config_path is None:
            config = json.loads(path.read_text(encoding='utf-8'))
            account_id = config.get('active_account_id')
            if account_id:
                if not re.fullmatch(r'[0-9a-f]{32}', account_id):
                    raise ValueError('Invalid account identifier')
                path = self.root / 'secrets/accounts' / account_id / 'config.json'
        session = self.sessions.setdefault(str(path), GoogleSession(path))
        return parse_usage(session.request_rpc('jSf9Qc', source='/usage'))


if __name__ == '__main__':
    try:
        print(json.dumps(UsageReader(Path(__file__).resolve().parent).fetch(), ensure_ascii=False))
    except Exception as exc:
        # Exception messages may contain request URLs; expose only the type.
        print(json.dumps({'unavailable': type(exc).__name__}))
        raise SystemExit(1)
