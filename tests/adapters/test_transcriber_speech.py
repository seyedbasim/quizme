"""_faststart: MP4 moov relocation for iOS Voice Memos (fixes 422 InvalidAudioFormat)."""

from __future__ import annotations

import struct

from quizme.adapters.transcriber_speech import _faststart


def _atom(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload) + 8) + kind + payload


def test_non_mp4_bytes_pass_through_unchanged() -> None:
    raw = b"RIFF\x24\x00\x00\x00WAVEfmt "
    assert _faststart(raw) is raw


def test_short_bytes_pass_through_unchanged() -> None:
    assert _faststart(b"abc") == b"abc"


def test_moov_before_mdat_is_left_alone() -> None:
    # already "fast start" (moov ahead of mdat) -> qtfaststart raises, we return input
    mp4 = _atom(b"ftyp", b"isom") + _atom(b"moov", b"\x00" * 8) + _atom(b"mdat", b"\x00" * 16)
    assert _faststart(mp4) == mp4


def test_unparseable_mp4_returns_input() -> None:
    # ftyp signature but garbage body -> best-effort fallback, never raises
    junk = b"\x00\x00\x00\x10ftypxxxx" + b"\xff" * 64
    assert _faststart(junk) == junk
