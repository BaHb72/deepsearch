"""providers 模块中 fallback AKShareDirectProvider 的单例行为测试。"""

import asyncio

import pytest

from apps.api.api import providers


@pytest.mark.asyncio
async def test_fallback_akshare_direct_provider_singleton(monkeypatch):
    """并发获取 fallback provider 时只初始化一次。"""

    from core.infrastructure.providers.implementations.akshare import akshare_direct

    class DummyProvider:
        init_calls = 0

        async def initialize(self):
            DummyProvider.init_calls += 1
            await asyncio.sleep(0.01)
            return True

    providers._fallback_akshare_direct_provider = None
    providers._fallback_akshare_direct_provider_lock = None
    monkeypatch.setattr(akshare_direct, "AKShareDirectProvider", DummyProvider)

    provider_a, provider_b = await asyncio.gather(
        providers._get_fallback_akshare_direct_provider(),
        providers._get_fallback_akshare_direct_provider(),
    )

    assert provider_a is provider_b
    assert DummyProvider.init_calls == 1

    providers._fallback_akshare_direct_provider = None
    providers._fallback_akshare_direct_provider_lock = None
