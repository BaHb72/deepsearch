"""验证数据提供者能力声明。"""

import importlib
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Optional

import pytest

from deepsearch.infrastructure.providers.interfaces.capabilities import DataCapability
from deepsearch.infrastructure.providers.implementations.akshare.akshare_refactored import (
    AkShareProxyProvider,
)
from deepsearch.infrastructure.providers.implementations.qmt.unified_qmt_provider import (
    UnifiedQMTProvider,
)


@pytest.fixture()
def dummy_config():
    """构造最小化配置对象，避免读取真实配置。"""

    return SimpleNamespace(cloudflare_workers=None)


def test_akshare_proxy_capabilities(monkeypatch: pytest.MonkeyPatch, dummy_config: SimpleNamespace) -> None:
    monkeypatch.setattr(
        "deepsearch.infrastructure.providers.implementations.akshare.akshare_refactored.get_config",
        lambda: dummy_config,
    )

    provider = AkShareProxyProvider()

    expected = {
        DataCapability.REALTIME_QUOTE,
        DataCapability.REALTIME_QUOTES,
        DataCapability.KLINE_DATA,
        DataCapability.MINUTE_DATA,
        DataCapability.TICK_DATA,
        DataCapability.ORDER_BOOK,
        DataCapability.SECTOR_DATA,
        DataCapability.ANOMALY_DETECTION,
        DataCapability.CAPITAL_FLOW,
        DataCapability.NORTH_FLOW,
    }

    assert provider.get_capabilities() == expected


def test_amazingdata_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    # AmazingData 包的 __init__ 依赖实时模块，缺失 SDK 时会抛异常，这里注入占位模块避免导入失败。
    stub_module: Any = ModuleType("amazingdata_realtime_stub")
    stub_module.AmazingDataRealtime = object()
    monkeypatch.setitem(
        sys.modules,
        "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_realtime",
        stub_module,
    )
    monkeypatch.delitem(
        sys.modules,
        "deepsearch.infrastructure.providers.implementations.amazingdata",
        raising=False,
    )
    monkeypatch.delitem(
        sys.modules,
        "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata",
        raising=False,
    )

    module = importlib.import_module(
        "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata"
    )
    AmazingDataConfig = module.AmazingDataConfig
    AmazingDataProvider = module.AmazingDataProvider

    config = AmazingDataConfig(
        username="demo",
        password="demo",
        host="127.0.0.1",
        port=9100,
        enabled=True,
        cache_enabled=False,
    )

    provider = AmazingDataProvider(config)

    expected = {
        DataCapability.REALTIME_QUOTE,
        DataCapability.REALTIME_QUOTES,
        DataCapability.KLINE_DATA,
        DataCapability.MINUTE_DATA,
        DataCapability.TICK_DATA,
        DataCapability.STOCK_LIST,
        DataCapability.FINANCIAL_DATA,
        DataCapability.KEY_INDICATORS,
        DataCapability.SHAREHOLDER_INFO,
        DataCapability.DRAGON_TIGER,
        DataCapability.MARGIN_TRADING,
        DataCapability.NORTH_FLOW,
        DataCapability.TRADING_CALENDAR,
        DataCapability.ADJUSTMENT_FACTOR,
        DataCapability.STOCK_INFO,
    }

    assert provider.get_capabilities() == expected


def test_miniqmt_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_base: Any = ModuleType("qmt_base_stub")

    class _DataProvider:
        def __init__(self, config):
            self.config = config

    class _DataProviderConfig:
        def __init__(
            self,
            name: str,
            source_type,
            enabled: bool = True,
            timeout: float = 0.0,
            config: Optional[dict[str, object]] = None,
        ) -> None:
            self.name = name
            self.source_type = source_type
            self.enabled = enabled
            self.timeout = timeout
            self.config = config or {}

    class _DataProviderError(Exception):
        pass

    class _DataRequest:
        def __init__(self, **kwargs) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    stub_base.DataProvider = _DataProvider
    stub_base.DataProviderConfig = _DataProviderConfig
    stub_base.DataProviderError = _DataProviderError
    stub_base.DataRequest = _DataRequest

    module_name = "deepsearch.infrastructure.providers.implementations.qmt"
    base_name = f"{module_name}.base"
    miniqmt_name = f"{module_name}.miniqmt"

    monkeypatch.setitem(sys.modules, base_name, stub_base)
    monkeypatch.delitem(sys.modules, miniqmt_name, raising=False)

    miniqmt_module: Any = importlib.import_module(miniqmt_name)

    class _TestMiniQMT(miniqmt_module.MiniQMTProvider):
        async def initialize(self) -> bool:
            return True

        async def get_stock_list(self, limit=None, **kwargs):
            return []

        async def get_kline_data(
            self, symbol: str, period: str = "1d", start_date=None, end_date=None, limit: int = 100, **kwargs
        ):
            return []

    provider = _TestMiniQMT()

    expected = {
        DataCapability.REALTIME_QUOTE,
        DataCapability.REALTIME_QUOTES,
        DataCapability.TICK_DATA,
        DataCapability.MINUTE_DATA,
        DataCapability.KLINE_DATA,
    }

    assert provider.get_capabilities() == expected


def test_unified_qmt_capabilities() -> None:
    class _UnifiedQMTStub(UnifiedQMTProvider):
        async def initialize(self) -> bool:  # type: ignore[override]
            return True

        async def get_stock_list(  # type: ignore[override]
            self,
            limit: Optional[int] = None,
            **kwargs,
        ) -> Optional[list]:
            return []

        async def get_kline_data(  # type: ignore[override]
            self,
            symbol: str,
            period: str = "1d",
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            limit: int = 100,
            **kwargs,
        ) -> Optional[list]:
            return []

    provider = _UnifiedQMTStub()

    expected = {
        DataCapability.REALTIME_QUOTE,
        DataCapability.REALTIME_QUOTES,
        DataCapability.TICK_DATA,
        DataCapability.MINUTE_DATA,
        DataCapability.KLINE_DATA,
    }

    assert provider.get_capabilities() == expected
