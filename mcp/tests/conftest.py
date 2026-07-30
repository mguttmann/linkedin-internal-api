"""conftest.py — pins the ambient environment for every test in mcp/tests.

LINKEDIN_READ_ONLY (mcp/server.py:42) is an OPERATING mode that is read from os.environ on
every tool call, and Manuel's documented default for cron/agent operation is to export it.
An exported value must never decide whether this suite is green: without this pin,
mcp/tests/test_server.py:41 (confirm-gate proof) fails under LINKEDIN_READ_ONLY=1 because the
read-only gate raises first — and every future test that calls a writing tool would inherit
the same ambient dependency.

The fixture removes the variable per test. Tests that need read-only mode set it themselves
via monkeypatch (mcp/tests/test_readonly.py), which runs after this fixture and wins.
"""
import os

import pytest


@pytest.fixture(autouse=True)
def _unset_linkedin_read_only():
    """Remove LINKEDIN_READ_ONLY for the duration of every test, restore it afterwards."""
    previous = os.environ.pop("LINKEDIN_READ_ONLY", None)
    try:
        yield
    finally:
        if previous is not None:
            os.environ["LINKEDIN_READ_ONLY"] = previous
