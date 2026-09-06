from __future__ import annotations

import uuid

from quizme.domain.ids import new_id, sha256_hex, text_hash


def test_new_id_is_uuid_v7_and_unique() -> None:
    ids = [new_id() for _ in range(200)]
    for i in ids:
        assert uuid.UUID(i).version == 7
    assert len(set(ids)) == len(ids)


def test_new_id_is_broadly_time_ordered() -> None:
    import time

    a = new_id()
    time.sleep(0.005)
    b = new_id()
    assert a < b  # ms-precision timestamp prefix orders across a 5ms gap


def test_sha256_hex_stable() -> None:
    assert sha256_hex(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_text_hash_normalises() -> None:
    assert text_hash("  Hello   World ") == text_hash("hello world")
