"""HMAC-SHA256 sign/verify tests.

Includes a known-vector check so the algorithm is locked — MTA's
verifier feeds the same vector through its TS implementation and we
compare hex strings. Don't change the vector without coordinating.
"""

from __future__ import annotations

import pytest

from desk.distribute.signing import sign, verify


# Known vector — keep this in sync with MTA's signing test. If you
# change any of these four constants, rotate them on both sides at the
# same time.
KNOWN_SECRET = "test-shared-secret-001"
KNOWN_TS     = 1735689600
KNOWN_BODY   = b'{"match_id":"fb-wc26-fra-mex-20260612","verdict":"pick"}'
KNOWN_SIG    = "4c18d43ec230c3555e627f4e20fe29c09afc7abadefc6c540e7212f98c420d5e"


def test_sign_round_trip() -> None:
    secret = "s3cret"
    body = b'{"hello":"world"}'
    sig = sign(1234567890, body, secret)
    assert verify(1234567890, body, secret, sig) is True


def test_sign_tamper_body_fails() -> None:
    secret = "s3cret"
    sig = sign(1, b'{"a":1}', secret)
    assert verify(1, b'{"a":2}', secret, sig) is False


def test_sign_tamper_timestamp_fails() -> None:
    secret = "s3cret"
    sig = sign(1, b'{"a":1}', secret)
    assert verify(2, b'{"a":1}', secret, sig) is False


def test_sign_tamper_secret_fails() -> None:
    sig = sign(1, b'x', "a")
    assert verify(1, b'x', "b", sig) is False


def test_sign_known_vector() -> None:
    """Cross-implementation lock — MTA's verifier feeds the same vector
    and asserts the same hex digest. Don't change the vector without
    rotating it on both sides simultaneously."""
    actual = sign(KNOWN_TS, KNOWN_BODY, KNOWN_SECRET)
    assert actual == KNOWN_SIG, (
        "HMAC vector drifted — algorithm or input shape changed. "
        "Talk to the MTA operator before updating KNOWN_SIG."
    )
    assert verify(KNOWN_TS, KNOWN_BODY, KNOWN_SECRET, actual) is True
    # Sanity: hex output, 64 chars (SHA-256), lowercase
    assert len(actual) == 64
    assert actual == actual.lower()
    int(actual, 16)  # must parse as hex


def test_sign_rejects_empty_secret() -> None:
    with pytest.raises(ValueError):
        sign(1, b'x', "")


def test_sign_handles_binary_body() -> None:
    """Body is bytes, not str — non-UTF-8 sequences must work."""
    body = bytes(range(256))
    sig = sign(1, body, "s")
    assert verify(1, body, "s", sig)


def test_constant_time_compare_used() -> None:
    """hmac.compare_digest under the hood — a wrong-but-correct-length
    signature returns False (not raises). Smoke check."""
    bogus = "a" * 64
    assert verify(1, b'x', "s", bogus) is False
