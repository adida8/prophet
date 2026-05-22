"""
Prophet-MVP-v1 — RSA-PSS Authentication
Signs requests for the Kalshi v2 API using RSA-PSS with SHA-256.
"""

import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

import config


def _load_private_key(path: Path):
    """Load an RSA private key from a PEM file."""
    # Guard against KALSHI_PRIVATE_KEY_PATH being configured with the PEM
    # contents instead of a filesystem path. Without this, read_bytes()
    # raises FileNotFoundError whose str() contains the whole "filename"
    # (i.e. the key) verbatim, which then gets logged.
    if "-----BEGIN" in str(path):
        raise RuntimeError(
            "KALSHI_PRIVATE_KEY_PATH appears to contain inline PEM content "
            "rather than a path to a file. Set it to a filesystem path."
        )
    pem_data = path.read_bytes()
    return serialization.load_pem_private_key(pem_data, password=None)


# Cache the key so we only read disk once.
_private_key = None


def _get_key():
    global _private_key
    if _private_key is None:
        _private_key = _load_private_key(config.PRIVATE_KEY_PATH)
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
