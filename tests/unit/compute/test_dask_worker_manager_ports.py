from __future__ import annotations

import asyncio
from typing import ClassVar, List
from unittest.mock import AsyncMock

import pytest
from core.compute.dask_worker_manager import DaskConfig, DaskWorkerManager, PluginState


class _FakePortReservation:
    instances: ClassVar[List["_FakePortReservation"]] = []

    def __init__(self) -> None:
        self.released = False
        _FakePortReservation.instances.append(self)

    def reserve_ports(
        self,
        count: int,
        start_port: int = 58200,
        max_range: int = 100,
        host: str = "0.0.0.0",
    ) -> list[int]:
        del max_range, host
        return [start_port + i for i in range(count)]

    def release_all(self) -> None:
        self.released = True


@pytest.mark.parametrize(("platform", "expect_none"), [("nt", True), ("posix", False)])
def test_reserve_ports_platform_behavior(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    expect_none: bool,
) -> None:
    _FakePortReservation.instances.clear()
    monkeypatch.setattr("core.compute.dask_worker_manager.os.name", platform)
    monkeypatch.setattr(
        "core.utils.system.port_reservation.PortReservation",
        _FakePortReservation,
    )

    manager = DaskWorkerManager(config=DaskConfig(num_workers=1))
    ports, reservation = manager._reserve_ports(count=1, start_port=58200, max_range=8)

    assert ports == [58200]
    assert (reservation is None) is expect_none

    fake_reservation = _FakePortReservation.instances[0]
    assert fake_reservation.released is expect_none


def test_build_worker_name_includes_session_suffix() -> None:
    manager = DaskWorkerManager(config=DaskConfig(name_prefix="windows-worker"))
    manager._worker_session_id = "abcd1234"

    name = manager._build_worker_name(0)

    assert name == "windows-worker-abcd1234-0"


@pytest.mark.asyncio
async def test_wait_amazingdata_plugin_ready_returns_false_when_event_is_timeout_result() -> None:
    manager = DaskWorkerManager(config=DaskConfig(num_workers=1))
    manager._amazingdata_plugin_ready_ok = False
    manager._amazingdata_plugin_ready.set()

    ready = await manager.wait_amazingdata_plugin_ready(timeout=0.1)

    assert ready is False


@pytest.mark.asyncio
async def test_wait_amazingdata_plugin_ready_returns_true_when_ready_flag_set() -> None:
    manager = DaskWorkerManager(config=DaskConfig(num_workers=1))
    manager._amazingdata_plugin_ready_ok = True
    manager._amazingdata_plugin_ready.set()

    ready = await manager.wait_amazingdata_plugin_ready(timeout=0.1)

    assert ready is True


@pytest.mark.asyncio
async def test_register_plugin_safe_timeout_keeps_amazingdata_in_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = DaskWorkerManager(config=DaskConfig(num_workers=1))

    async def _slow_register(name: str, scheduler_address: str) -> bool:
        del name, scheduler_address
        await asyncio.sleep(0.05)
        return True

    monkeypatch.setattr(manager, "_plugin_register_timeout_seconds", lambda name=None: 0.01)
    monkeypatch.setattr(manager, "_register_plugin", _slow_register)

    await manager._register_plugin_safe("amazingdata", "tcp://127.0.0.1:8786")

    plugin = manager._plugins["amazingdata"]
    assert plugin.state != PluginState.FAILED
    assert plugin.state == PluginState.REGISTERING
    await asyncio.sleep(0.06)


@pytest.mark.asyncio
async def test_register_plugin_safe_timeout_cancels_non_amazingdata_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = DaskWorkerManager(config=DaskConfig(num_workers=1))
    cancelled = asyncio.Event()

    async def _slow_register(name: str, scheduler_address: str) -> bool:
        del name, scheduler_address
        try:
            await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return True

    monkeypatch.setattr(manager, "_plugin_register_timeout_seconds", lambda name=None: 0.01)
    monkeypatch.setattr(manager, "_register_plugin", _slow_register)

    await manager._register_plugin_safe("miniqmt", "tcp://127.0.0.1:8786")

    plugin = manager._plugins["miniqmt"]
    assert plugin.state == PluginState.FAILED
    assert plugin.error is not None
    assert "超时" in plugin.error
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_register_all_plugins_probe_setup_even_if_timeout_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = DaskWorkerManager(config=DaskConfig(num_workers=1))

    async def _mock_register_safe(name: str, scheduler_address: str) -> None:
        del scheduler_address
        plugin = manager._plugins[name]
        if name == "amazingdata":
            plugin.state = PluginState.FAILED
            plugin.error = "注册超时(30.0s)"
        else:
            plugin.state = PluginState.FAILED
            plugin.error = "init failed"

    wait_setup_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(manager, "_register_plugin_safe", _mock_register_safe)
    monkeypatch.setattr(manager, "_wait_for_plugin_setup", wait_setup_mock)

    await manager._register_all_plugins()

    wait_setup_mock.assert_awaited_once()
    assert manager._amazingdata_plugin_ready_ok is True
    assert manager._plugins["amazingdata"].state == PluginState.REGISTERED
