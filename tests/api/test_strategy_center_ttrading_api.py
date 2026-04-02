"""策略中心 T-Trading 数据源状态接口测试。"""

import pytest

from apps.api.api.endpoints.strategy_center import ttrading


@pytest.mark.asyncio
async def test_datasource_status_returns_none_when_miniqmt_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    """MiniQMT 不可用时应返回 none 状态。"""

    async def _probe_should_not_run() -> bool:
        raise AssertionError("MINIQMT_AVAILABLE=False 时不应探活")

    monkeypatch.setattr(ttrading, "MINIQMT_AVAILABLE", False)
    monkeypatch.setattr(ttrading, "_probe_miniqmt_actor_connection", _probe_should_not_run)

    result = await ttrading.get_datasource_status()

    assert result["miniqmt_available"] is False
    assert result["miniqmt_connected"] is False
    assert result["active_provider"] == "none"


@pytest.mark.asyncio
async def test_datasource_status_fallbacks_when_probe_failed(monkeypatch: pytest.MonkeyPatch):
    """MiniQMT 探活失败时应继续探测回退数据源。"""

    async def _probe_false() -> bool:
        return False

    async def _soft_provider(name: str):
        if name == "akshare":
            return object()
        return None

    monkeypatch.setattr(ttrading, "MINIQMT_AVAILABLE", True)
    monkeypatch.setattr(ttrading, "_probe_miniqmt_tcp_connection", lambda: True)
    monkeypatch.setattr(ttrading, "_probe_miniqmt_actor_connection", _probe_false)
    monkeypatch.setattr(ttrading, "_get_provider_with_soft_fail", _soft_provider)

    result = await ttrading.get_datasource_status()

    assert result["miniqmt_available"] is True
    assert result["miniqmt_connected"] is False
    assert result["amazingdata_available"] is False
    assert result["akshare_available"] is True
    assert result["active_provider"] == "akshare"


@pytest.mark.asyncio
async def test_datasource_status_returns_none_when_all_providers_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    """MiniQMT 与回退源均不可用时返回 none。"""

    async def _probe_false() -> bool:
        return False

    async def _soft_provider(_name: str):
        return None

    monkeypatch.setattr(ttrading, "MINIQMT_AVAILABLE", True)
    monkeypatch.setattr(ttrading, "_probe_miniqmt_tcp_connection", lambda: True)
    monkeypatch.setattr(ttrading, "_probe_miniqmt_actor_connection", _probe_false)
    monkeypatch.setattr(ttrading, "_get_provider_with_soft_fail", _soft_provider)

    result = await ttrading.get_datasource_status()

    assert result["miniqmt_available"] is True
    assert result["miniqmt_connected"] is False
    assert result["amazingdata_available"] is False
    assert result["akshare_available"] is False
    assert result["active_provider"] == "none"


@pytest.mark.asyncio
async def test_datasource_status_returns_miniqmt_when_probe_success(
    monkeypatch: pytest.MonkeyPatch,
):
    """探活成功时应标记为已连接。"""

    async def _probe_true() -> bool:
        return True

    monkeypatch.setattr(ttrading, "MINIQMT_AVAILABLE", True)
    monkeypatch.setattr(ttrading, "_probe_miniqmt_tcp_connection", lambda: True)
    monkeypatch.setattr(ttrading, "_probe_miniqmt_actor_connection", _probe_true)

    result = await ttrading.get_datasource_status()

    assert result["miniqmt_available"] is True
    assert result["miniqmt_connected"] is True
    assert result["active_provider"] == "miniqmt"


@pytest.mark.asyncio
async def test_datasource_status_returns_none_when_tcp_unreachable(monkeypatch: pytest.MonkeyPatch):
    """端口不可达时应直接判定未连接并保持 none。"""

    async def _probe_should_not_run() -> bool:
        raise AssertionError("TCP 不可达时不应执行 Actor 探活")

    monkeypatch.setattr(ttrading, "MINIQMT_AVAILABLE", True)
    monkeypatch.setattr(ttrading, "_probe_miniqmt_tcp_connection", lambda: False)
    monkeypatch.setattr(ttrading, "_probe_miniqmt_actor_connection", _probe_should_not_run)

    result = await ttrading.get_datasource_status()

    assert result["miniqmt_available"] is True
    assert result["miniqmt_connected"] is False
    assert result["active_provider"] == "none"
