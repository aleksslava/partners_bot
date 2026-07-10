import secrets
import time
from collections import defaultdict

from fastapi import Request


class LoginRateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 15 * 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def is_blocked(self, key: str) -> bool:
        attempts = self._active_attempts(key)
        return len(attempts) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        attempts = self._active_attempts(key)
        attempts.append(time.monotonic())
        self._attempts[key] = attempts

    def clear(self, key: str) -> None:
        self._attempts.pop(key, None)

    def _active_attempts(self, key: str) -> list[float]:
        threshold = time.monotonic() - self.window_seconds
        attempts = [value for value in self._attempts.get(key, []) if value >= threshold]
        if attempts:
            self._attempts[key] = attempts
        else:
            self._attempts.pop(key, None)
        return attempts


def client_key(request: Request) -> str:
    forwarded_for = request.headers.get('x-forwarded-for', '')
    if forwarded_for:
        return forwarded_for.split(',', maxsplit=1)[0].strip()
    return request.client.host if request.client else 'unknown'


def is_authenticated(request: Request) -> bool:
    return request.session.get('admin_authenticated') is True


def get_csrf_token(request: Request) -> str:
    token = request.session.get('csrf_token')
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        request.session['csrf_token'] = token
    return token


def valid_csrf(request: Request, submitted_token: str) -> bool:
    expected = request.session.get('csrf_token')
    return (
        isinstance(expected, str)
        and bool(submitted_token)
        and secrets.compare_digest(expected, submitted_token)
    )
