"""Refuse generation at the account limit or when account limits cannot be verified."""
import math
import threading


class QuotaRejected(Exception):
    def __init__(self, message, status=429, code='quota_exhausted', reset_at=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.reset_at = reset_at

    def response(self):
        return {'error': {'message': str(self), 'type': 'insufficient_quota' if self.status == 429 else 'quota_unavailable',
                          'code': self.code, 'reset_at': self.reset_at}}


class QuotaGuard:
    def __init__(self, reader):
        self.reader = reader
        # Prevent simultaneous requests from passing a nearly-exhausted limit together.
        self.generation_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.state = {'mode': 'stop_on_limit', 'state': 'not_checked'}

    def snapshot(self):
        with self.state_lock:
            return dict(self.state)

    def check(self):
        try:
            usage = self.reader.fetch()
            windows = []
            for name in ('current_5h', 'weekly'):
                window = usage.get(name)
                fraction = window.get('used_fraction') if isinstance(window, dict) else None
                if type(fraction) not in (int, float) or not math.isfinite(fraction) or fraction < 0:
                    raise ValueError('Missing account usage window')
                windows.append((name, window, fraction))
        except Exception:
            rejection = QuotaRejected(
                'Cannot verify Google account quota. Request blocked to prevent a model downgrade. Check the session cookie or retry later.',
                status=503, code='quota_unverified')
            with self.state_lock:
                self.state = {'mode': 'stop_on_limit', 'state': 'unverified', 'message': str(rejection)}
            raise rejection from None
        for name, window, fraction in windows:
            if fraction >= 1:
                label = 'current session' if name == 'current_5h' else 'weekly'
                reset = window.get('reset_at')
                message = f'Google {label} quota exhausted. Generation is blocked; no fallback model will be used.'
                if reset:
                    message += f' Resets: {reset}.'
                with self.state_lock:
                    self.state = {'mode': 'stop_on_limit', 'state': 'blocked', 'window': name,
                                  'reset_at': reset, 'message': message}
                raise QuotaRejected(message, reset_at=reset)
        with self.state_lock:
            self.state = {'mode': 'stop_on_limit', 'state': 'allowed', 'checked_at': usage.get('updated_at')}
        return usage
