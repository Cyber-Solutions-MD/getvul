"""Symmetric encryption for connector credentials using Fernet."""

from __future__ import annotations

from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    """Get Fernet instance from the configured encryption key."""
    key = settings.encryption_key.encode()
    return Fernet(key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string. Returns plaintext."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def generate_key() -> str:
    """Generate a new Fernet encryption key. Run once, store in .env."""
    return Fernet.generate_key().decode()


def _fernet_for(key: str) -> Fernet:
    """Return a Fernet instance for an explicit key string.

    Raises ValueError if key is not a valid 32-byte url-safe base64 Fernet key.
    """
    return Fernet(key.encode())
