"""Identifier and hashing helpers.

Convention (architecture-spine → Consistency Conventions): every entity id is a
time-ordered UUIDv7 string; audio blobs are addressed by the SHA-256 hex of their
bytes, which is also the dedup key on ``recording``.
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid


def new_id() -> str:
    """A time-ordered UUIDv7 as a canonical string.

    Uses :func:`uuid.uuid7` when available (Python 3.14+), otherwise a minimal
    RFC 9562-compatible construction (48-bit ms timestamp + random).
    """
    uuid7 = getattr(uuid, "uuid7", None)
    if uuid7 is not None:  # pragma: no cover - version dependent
        return str(uuid7())

    unix_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand = os.urandom(10)
    b = bytearray(16)
    b[0:6] = unix_ms.to_bytes(6, "big")
    b[6:16] = rand
    b[6] = (b[6] & 0x0F) | 0x70  # version 7
    b[8] = (b[8] & 0x3F) | 0x80  # variant 10
    return str(uuid.UUID(bytes=bytes(b)))


def sha256_hex(data: bytes) -> str:
    """Lowercase hex SHA-256 — the content address for audio blobs (FR-2)."""
    return hashlib.sha256(data).hexdigest()


def text_hash(text: str) -> str:
    """Stable hash of normalised text — used for prompt hashes and follow-up
    intent dedup keys (AD-8, AD-12)."""
    normalised = " ".join(text.split()).lower()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
