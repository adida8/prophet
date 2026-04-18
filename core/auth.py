"""
Prophet-MVP-v1 — RSA-PSS Authentication
Signs requests for the Kalshi v2 API using RSA-PSS with SHA-256.
"""

import os
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

import config


def _normalize_pem(value: str) -> bytes:
    """Turn a PEM value (possibly with escaped newlines) into bytes."""
    if "\\n" in value and "\n" not in value:
        value = value.replace("\\n", "\n")
    return value.encode("utf-8")


def _load_private_key_bytes() -> bytes:
    """
    Prefer the PEM content set via KALSHI_PRIVATE_KEY (required on PaaS
    hosts that cannot mount a file). Fall back to the file at
    config.PRIVATE_KEY_PATH for local development.

    Forgiving: if KALSHI_PRIVATE_KEY_PATH was accidentally set to the PEM
    contents instead of a path, detect that and use it as PEM.

    Never echoes the value of either env var into exceptions — those get
    captured by log aggregators.
    """
    pem = os.getenv("KALSHI_PRIVATE_KEY", "").strip()
    if pem:
        return _normalize_pem(pem)

    raw_path = os.getenv("KALSHI_PRIVATE_KEY_PATH", "").strip()
    if raw_path.startswith("-----BEGIN"):
        # User put the PEM in the *_PATH variable by mistake — accept it.
        return _normalize_pem(raw_path)

    path: Path = config.PRIVATE_KEY_PATH
    if not path.exists():
        raise FileNotFoundError(
            "No Kalshi private key found. Set KALSHI_PRIVATE_KEY to the "
            "PEM contents (recommended on Railway), or put a PEM file at "
            "the path named by KALSHI_PRIVATE_KEY_PATH."
        )
    return path.read_bytes()


# Cache the key so we only parse it once.
_private_key = None


def _get_key():
    global _private_key
    if _private_key is None:
        _private_key = serialization.load_pem_private_key(
            _load_private_key_bytes(), password=None
        )
    return _private_key


def sign_message(timestamp: str, method: str, path: str) -> bytes:
    """
    Sign the canonical string: timestamp + method + path
    using RSA-PSS / SHA-256 (Kalshi v2 standard).
    """
    message = (timestamp + method + path).encode("utf-8")
    key = _get_key()
    signature = key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    return signature


def get_headers(method: str, path: str) -> dict[str, str]:
    """
    Return the three KALSHI-ACCESS-* headers required by every
    authenticated request.

    Parameters
    ----------
    method : str  — HTTP verb, e.g. "GET", "POST"
    path   : str  — API path, e.g. "/trade-api/v2/markets"
    """
    import base64

    timestamp = str(int(time.time() * 1000))  # millisecond epoch
    signature = sign_message(timestamp, method, path)

    return {
        "KALSHI-ACCESS-KEY": config.API_KEY,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("utf-8"),
        "Content-Type": "application/json",
    }
