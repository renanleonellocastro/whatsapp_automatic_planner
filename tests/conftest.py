"""Shared test fixtures.

``clean_env`` removes any ``WAPP_``-prefixed environment variables so that
configuration tests are hermetic and never pick up the host's real settings.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in list(os.environ):
        if key.startswith("WAPP_"):
            monkeypatch.delenv(key, raising=False)
    yield
