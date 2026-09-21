import hashlib
import hmac
import secrets
from datetime import datetime, timezone

TOKEN_BYTES = 32


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    if not isinstance(token, str):
        raise TypeError("token must be a string")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, expected_hash: str) -> bool:
    if not isinstance(token, str) or not isinstance(expected_hash, str):
        return False
    return hmac.compare_digest(hash_token(token), expected_hash)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
