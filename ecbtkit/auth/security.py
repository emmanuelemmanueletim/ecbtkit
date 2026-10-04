"""Backward-compatible re-exports. Prefer ecbtkit.security. """
from ecbtkit.security.passwords import hash_password, verify_password
from ecbtkit.security.tokens import create_access_token, decode_token

__all__ = ["hash_password", "verify_password", "create_access_token", "decode_token"]
