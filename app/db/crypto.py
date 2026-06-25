"""Symmetric encryption for per-tenant credentials (Cal.com keys, WhatsApp tokens).

Secrets are encrypted at rest in Postgres and only ever decrypted in memory when a
tenant's context is loaded. The Fernet key lives in ENCRYPTION_KEY (env, gitignored).
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import settings


@lru_cache
def _fernet() -> Fernet:
    if not settings.encryption_key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Generate one with:\n"
            '  python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(settings.encryption_key.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
