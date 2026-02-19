"""Dask Worker contact host 解析测试。"""

from __future__ import annotations

import pytest
from core.compute.dask_worker_manager import DaskConfig, DaskWorkerManager


@pytest.mark.asyncio
async def test_resolve_worker_contact_host_prefers_explicit_config() -> None:
    manager = DaskWorkerManager(config=DaskConfig(contact_host="10.10.10.10"))
    manager._parsed_host = "localhost"
    manager._parsed_port = 8786

    result = await manager._resolve_worker_contact_host()
    assert result == "10.10.10.10"


@pytest.mark.asyncio
async def test_resolve_worker_contact_host_prefers_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = DaskWorkerManager(config=DaskConfig())
    manager._parsed_host = "localhost"
    manager._parsed_port = 8786
    monkeypatch.setenv("DEEPSEARCH_DASK_WORKER_CONTACT_HOST", "192.168.10.20")

    result = await manager._resolve_worker_contact_host()
    assert result == "192.168.10.20"


@pytest.mark.asyncio
async def test_resolve_worker_contact_host_external_scheduler_uses_host_docker_internal() -> None:
    manager = DaskWorkerManager(config=DaskConfig())
    manager._parsed_host = "localhost"
    manager._parsed_port = 8786

    async def _fake_runtime_host() -> str:
        return "172.18.0.2"

    manager._detect_scheduler_runtime_host = _fake_runtime_host  # type: ignore[method-assign]
    result = await manager._resolve_worker_contact_host()
    assert result == "host.docker.internal"


@pytest.mark.asyncio
async def test_resolve_worker_contact_host_loopback_scheduler_uses_localhost() -> None:
    manager = DaskWorkerManager(config=DaskConfig())
    manager._parsed_host = "localhost"
    manager._parsed_port = 8786

    async def _fake_runtime_host() -> str:
        return "127.0.0.1"

    manager._detect_scheduler_runtime_host = _fake_runtime_host  # type: ignore[method-assign]
    result = await manager._resolve_worker_contact_host()
    assert result == "localhost"
