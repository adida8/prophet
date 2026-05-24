"""HMAC-SHA256 signing for the MTA webhook.

The signature covers `f"{timestamp}.{body}"` where `body` is the
canonical-JSON bytes of the payload exactly as sent on the wire.
The receiver re-derives the same string from the headers + raw body
and compares signatures with constant-time equality.

This is symmetric with MTA's verifier — same algorithm, same input
shape — so a test on either side proves the wire end-to-end.
"""

from __future__ import annotations

import hmac
import hashlib


def sign(timestamp: int, body: bytes, secret: str) -> str:
    """Return the lowercase-hex HMAC-SHA256 of `{timestamp}.{body}`.

    `timestamp` is epoch seconds. `body` is the exact bytes of the
    request body (not a string — encoding has to match what the
    receiver reads from the socket). `secret` is the shared key string.
    """
    if not secret:
        raise ValueError("secret must be a non-empty string")
    msg = f"{timestamp}.".encode("utf-8") + body
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify(timestamp: int, body: bytes, secret: str, signature_hex: str) -> bool:
    """Constant-time signature compare. Returns True iff valid."""
    expected = sign(timestamp, body, secret)
    return hmac.compare_digest(expected, signature_hex)
