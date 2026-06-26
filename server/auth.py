"""Session management — signed cookie, no database needed."""

from __future__ import annotations

import os

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_SECRET = os.environ.get("SESSION_SECRET", "otel-rm-dev-secret-change-in-prod")
_s = URLSafeTimedSerializer(_SECRET)
_MAX_AGE = 86400  # 24 h


def create_session(username: str) -> str:
    return _s.dumps({"u": username})


def verify_session(token: str | None) -> str | None:
    if not token:
        return None
    try:
        data = _s.loads(token, max_age=_MAX_AGE)
        return data.get("u")
    except (BadSignature, SignatureExpired):
        return None
