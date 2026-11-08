"""Demo login: one username/password per synthetic customer, server-side sessions."""

import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import Cookie, HTTPException

from . import db

COOKIE_NAME = "apex_session"

# username -> (customer_id, env var holding the password override, default password)
_DEMO_USERS = {
    "aarav": ("CUST-IN-101", "DEMO_AARAV_PASSWORD", "Apex@101"),
    "rajesh": ("CUST-IN-102", "DEMO_RAJESH_PASSWORD", "Apex@102"),
    "priya": ("CUST-IN-103", "DEMO_PRIYA_PASSWORD", "Apex@103"),
}

# Simple brute-force guard: username -> list of recent failed attempt timestamps
_failures: Dict[str, list] = {}
_MAX_FAILS, _WINDOW_SECONDS = 5, 300


def session_ttl_hours() -> int:
    try:
        return int(os.getenv("SESSION_TTL_HOURS", "12"))
    except ValueError:
        return 12


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _is_locked(username: str) -> bool:
    now = time.time()
    recent = [t for t in _failures.get(username, []) if now - t < _WINDOW_SECONDS]
    _failures[username] = recent
    return len(recent) >= _MAX_FAILS


def authenticate(username: str, password: str) -> Optional[str]:
    """Returns the customer_id on success, None on failure. Constant-time compare."""
    username = (username or "").strip().lower()
    if _is_locked(username):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a few minutes.")
    entry = _DEMO_USERS.get(username)
    expected = os.getenv(entry[1], entry[2]) if entry else ""
    ok = bool(entry) and hmac.compare_digest(password.encode(), expected.encode())
    if not ok:
        _failures.setdefault(username, []).append(time.time())
        return None
    _failures.pop(username, None)
    return entry[0]


def create_session(customer_id: str, username: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=session_ttl_hours())
    db.save_session(_hash_token(token), customer_id, username.lower(), expires.isoformat())
    return token


def end_session(token: Optional[str]) -> None:
    if token:
        db.delete_session(_hash_token(token))


def current_session(apex_session: Optional[str] = Cookie(default=None)) -> Dict[str, str]:
    """FastAPI dependency: the logged-in customer, or 401."""
    if not apex_session:
        raise HTTPException(status_code=401, detail="Not signed in")
    sess = db.load_session(_hash_token(apex_session))
    if not sess:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    return sess
