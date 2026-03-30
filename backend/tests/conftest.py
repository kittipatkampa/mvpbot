"""Pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from assistant_service import db
from assistant_service.config import settings
from assistant_service.main import app


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest_asyncio.fixture
async def test_settings(db_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "assistant_db_path", db_path)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    await db.init_db(db_path)
    yield


@pytest_asyncio.fixture
async def client(test_settings):  # noqa: ARG001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def patch_graph(monkeypatch: pytest.MonkeyPatch):
    def _apply(fake_graph):
        monkeypatch.setattr("assistant_service.main.get_graph", lambda: fake_graph)

    return _apply
