"""HMAC-SHA256 signing for the MTA webhook — copied verbatim from Desk.

The signature covers `f"{timestamp}.{body}"` where `body` is the
canonical-JSON bytes of the payload exactly as sent on the wire. The
receiver (MTAI) re-derives the same string from the headers + raw body
and compares signatures with constant-time equality.

Identical algorithm + input shape to the live Desk, so the same shared
secret keeps verifying on MTAI's side after the cutover.
"""

from __future__ import annotations

import hmac
import hashlib


def sign(timestamp: int, body: bytes, secret: str) -> str:
    """Return the lowercase-hex HMAC-SHA256 of `{timestamp}.{body}`."""
    if not secret:
        raise ValueError("secret must be a non-empty string")
    msg = f"{timestamp}.".encode("utf-8") + body
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify(timestamp: int, body: bytes, secret: str, signature_hex: str) -> bool:
    """Constant-time signature compare. Returns True iff valid."""
    expected = sign(timestamp, body, secret)
    return hmac.compare_digest(expected, signature_hex)
