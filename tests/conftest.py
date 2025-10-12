"""
Project-wide pytest fixtures for webui tests

Provides a generic `client` fixture so tests that depend on it
(e.g. TestPerformance::test_response_time) work in isolation.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from deepsearch.webui.server import app


@pytest.fixture(scope="function")
def client() -> TestClient:
    """Generic FastAPI TestClient for webui tests.

    Uses default app instance. Keep it lightweight to satisfy
    response time tests.
    """
    with TestClient(app) as c:
        yield c
