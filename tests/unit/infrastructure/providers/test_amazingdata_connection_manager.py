from types import SimpleNamespace
from typing import Any

import pytest

from deepsearch.infrastructure.providers.implementations.amazingdata import connection_manager as cm
from deepsearch.infrastructure.providers.implementations.amazingdata.connection_manager import (
    AmazingDataConnectionManager,
)


class _DummyPool:
    def __init__(self, *_, **__) -> None:
        self.initialized = False
        self.closed = False

    async def initialize(self) -> None:
        self.initialized = True

    async def close(self) -> None:
        self.closed = True


class _StubSessionManager:
    def __init__(self) -> None:
        self.acquire_calls = 0
        self.release_calls = 0

    async def acquire_login_file_lock(self) -> object:
        self.acquire_calls += 1
        return object()

    async def release_login_file_lock(self) -> None:
        self.release_calls += 1


class _DummyOwner:
    def __init__(self) -> None:
        self._connected = False
        self._degraded_mode = False
        self._stats: dict[str, Any] = {}
        self._subscriptions: list[str] = []
        self._restore_calls = 0
        self.login_calls = 0
        self.logout_calls = 0
        self.config = SimpleNamespace(
            heartbeat_interval=0,
            auto_reconnect=False,
            reconnect_interval=1,
        )

    async def _perform_login(self) -> bool:
        self.login_calls += 1
        self._connected = True
        return True

    async def _perform_logout(self) -> None:
        self.logout_calls += 1
        self._connected = False

    async def _perform_heartbeat(self) -> None:
        return None

    def _create_connection(self) -> dict[str, Any]:
        return {}

    async def _validate_connection(self, conn: dict[str, Any]) -> bool:
        return True

    async def _close_connection(self, conn: dict[str, Any]) -> None:
        conn.clear()

    def _increment_stat(self, key: str, delta: int = 1) -> int:
        current = int(self._stats.get(key, 0)) + delta
        self._stats[key] = current
        return current

    async def _restore_subscriptions(self) -> None:
        self._restore_calls += 1


@pytest.fixture(autouse=True)
def _patch_connection_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cm, "ConnectionPool", _DummyPool)


def _make_manager(monkeypatch: pytest.MonkeyPatch, owner: _DummyOwner) -> AmazingDataConnectionManager:
    manager = AmazingDataConnectionManager(owner)
    stub_session = _StubSessionManager()
    manager._session_manager = stub_session  # type: ignore[attr-defined]
    monkeypatch.setattr(manager, "_session_manager", stub_session, raising=False)
    return manager


@pytest.mark.asyncio
async def test_initialize_in_degraded_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _DummyOwner()
    owner._degraded_mode = True
    manager = _make_manager(monkeypatch, owner)

    await manager.initialize()

    assert manager._pool is None  # type: ignore[attr-defined]
    assert owner._connected is False


@pytest.mark.asyncio
async def test_login_retries_and_connects(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _DummyOwner()
    attempt_state = {"count": 0}

    async def failing_then_success() -> bool:
        attempt_state["count"] += 1
        if attempt_state["count"] < 2:
            raise RuntimeError("transient failure")
        owner._connected = True
        return True

    owner._perform_login = failing_then_success  # type: ignore[assignment]
    manager = _make_manager(monkeypatch, owner)

    async def noop_sleep(_: float) -> None:  # pragma: no cover - patched behaviour
        return None

    monkeypatch.setattr(cm.asyncio, "sleep", noop_sleep)

    await manager.login()

    assert attempt_state["count"] == 2
    assert owner._connected is True
    assert manager._session_manager.release_calls == attempt_state["count"]  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_ensure_session_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _DummyOwner()
    manager = _make_manager(monkeypatch, owner)

    connected = await manager.ensure_session()

    assert connected is True
    assert owner._connected is True
    assert isinstance(manager._pool, _DummyPool)  # type: ignore[attr-defined]
    assert owner.login_calls == 1


@pytest.mark.asyncio
async def test_shutdown_closes_pool_and_logs_out(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _DummyOwner()
    manager = _make_manager(monkeypatch, owner)

    await manager.initialize()
    assert owner.login_calls == 1

    await manager.shutdown()

    assert owner.logout_calls == 1
    pool = manager._pool  # type: ignore[attr-defined]
    assert pool is None or pool.closed
