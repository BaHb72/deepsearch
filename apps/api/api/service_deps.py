"""服务依赖过渡层。

当前仍有少量旧实现位于 `providers.py`，endpoint 层通过本模块间接访问，
便于后续继续向 ProviderContainer / 统一服务门面迁移。
"""

from __future__ import annotations

from typing import Any

from apps.api.api import providers as legacy_providers


async def get_market_service() -> Any:
    """获取市场服务，当前复用旧 providers 实现。"""

    return await legacy_providers.get_market_service()


async def get_akshare_direct_fallback_provider() -> Any | None:
    """获取 AKShare 直连兜底 provider。"""

    return await legacy_providers._get_fallback_akshare_direct_provider()
