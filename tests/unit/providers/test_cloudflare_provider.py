import pytest

from deepsearch.infrastructure.providers.implementations.cloudflare.cloudflare import (
    ProxyDataProvider,
)


@pytest.mark.asyncio
async def test_initialize_skips_placeholder_worker_url():
    provider = ProxyDataProvider(worker_url="https://your-cloudflare-worker.example.com")

    assert provider._using_placeholder_worker is True

    # 占位地址无需真实健康检查，initialize 应立即返回 False
    result = await provider.initialize()

    assert result is False
