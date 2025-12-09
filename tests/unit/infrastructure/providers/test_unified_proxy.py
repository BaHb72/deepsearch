"""unified_proxy 单例工具回归测试。"""

import asyncio

import pytest

from deepsearch.infrastructure.providers import unified_proxy


@pytest.mark.asyncio
async def test_get_data_proxy_singleton(monkeypatch):
    """多次获取数据代理应复用同一个实例，避免重复初始化。"""

    init_calls = {"count": 0}

    async def fake_initialize(self):
        init_calls["count"] += 1
        self.initialized = True

    monkeypatch.setattr(unified_proxy.DataAccessProxy, "initialize", fake_initialize, raising=False)
    monkeypatch.setattr(unified_proxy, "_DATA_PROXY_INSTANCE", None, raising=False)
    monkeypatch.setattr(unified_proxy, "_DATA_PROXY_LOCK", asyncio.Lock(), raising=False)

    proxy_first = await unified_proxy.get_data_proxy()
    proxy_second = await unified_proxy.get_data_proxy()

    assert proxy_first is proxy_second
    assert init_calls["count"] == 1
