"""Lockout state is global (per IP and per account), so tests must clear it."""

from __future__ import annotations

import pytest
from axes.utils import reset


@pytest.fixture(autouse=True)
def clear_lockouts(db):
    # ``db`` is required: reset() reads and writes the access-attempt tables.
    reset()
    yield
    reset()
