from __future__ import annotations

from datetime import UTC, datetime

import pytest


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
