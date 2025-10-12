"""
数据提供者管理器运行态与统计快照的单元测试
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProvider,
    DataProviderConfig,
    DataRequest,
    DataResponse,
    DataSourceType,
)
from deepsearch.infrastructure.providers.interfaces.capabilities import DataCapability
from deepsearch.infrastructure.providers.managers.manager import (
    DataProviderManager,
    ManagerStatisticsDict,
)


class DummyProvider(DataProvider):
    """用于测试的数据提供者实现，支持健康状态与统计信息控制。"""

    def __init__(
        self,
        name: str,
        *,
        source_type: DataSourceType,
        enabled: bool = True,
        priority: int = 100,
        extras: dict[str, object] | None = None,
        stats: dict[str, object] | str | None = None,
        healthy: bool = True,
        status: str = "running",
        capabilities: set[DataCapability] | None = None,
    ) -> None:
        config = DataProviderConfig(
            name=name,
            source_type=source_type,
            enabled=enabled,
            priority=priority,
            config=extras or {},
        )
        super().__init__(config)
        self._raw_stats = stats
        self._healthy = healthy
        self.status = status
        self._capabilities = capabilities or set()
        self.last_request: DataRequest | None = None

    async def initialize(self) -> bool:
        return True

    async def get_stock_list(
        self, limit: Optional[int] = None, **kwargs: Any
    ) -> Optional[List[Dict[str, Any]]]:
        return None

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs: Any,
    ) -> Optional[List[Dict[str, Any]]]:
        return None

    async def get_realtime_quotes(
        self, symbols: List[str]
    ) -> Optional[List[Dict[str, Any]]]:
        return None

    async def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        return None

    async def get_order_book(self, symbol: str) -> Optional[Dict[str, Any]]:
        return None

    async def get_data(self, request: DataRequest) -> DataResponse:
        self.last_request = request
        return DataResponse(success=True, data=[{"echo": request.request_type}], metadata={})

    def get_statistics(self) -> Dict[str, object]:
        if isinstance(self._raw_stats, dict):
            return dict(self._raw_stats)
        if self._raw_stats is None:
            return {}
        return {"value": self._raw_stats}

    def get_capabilities(self) -> set[DataCapability]:
        return set(self._capabilities)

    def is_healthy(self) -> bool:
        return self._healthy


@pytest.fixture()
def manager_with_providers() -> tuple[DataProviderManager, DummyProvider, DummyProvider]:
    """创建包含两个测试提供者的管理器。"""

    manager = DataProviderManager()
    manager._provider_priority["alpha"] = 2  # 调整以验证有效优先级来源

    provider_alpha = DummyProvider(
        "alpha",
        source_type=DataSourceType.AMAZINGDATA,
        priority=5,
        extras={"endpoint": "alpha://service"},
        stats={"requests": 2},
        healthy=True,
        capabilities={DataCapability.KLINE_DATA, DataCapability.REALTIME_QUOTES},
    )

    provider_beta = DummyProvider(
        "beta",
        source_type=DataSourceType.AKSHARE,
        enabled=False,
        priority=50,
        stats="offline",
        healthy=False,
        status="stopped",
        capabilities={DataCapability.STOCK_LIST},
    )

    manager.register_provider(provider_alpha)
    manager.register_provider(provider_beta)

    return manager, provider_alpha, provider_beta


@pytest.mark.asyncio
async def test_get_data_supports_datasource_selector(manager_with_providers):
    manager, provider_alpha, _ = manager_with_providers
    manager._initialized = True

    request = DataRequest(request_type="custom", symbol="000001")

    response = await manager._get_data(request, DataSourceType.AMAZINGDATA)

    assert response.success is True
    assert response.metadata["source"] == provider_alpha.config.name
    assert provider_alpha.last_request is not None

    disabled_response = await manager._get_data(request, DataSourceType.AKSHARE)
    assert disabled_response.success is False
    assert "已被禁用" in (disabled_response.error or "")


def test_statistics_snapshot_contains_runtime_metadata(manager_with_providers):
    manager, _, _ = manager_with_providers

    snapshot = manager.get_statistics_snapshot()

    assert snapshot.total_providers == 2
    assert snapshot.available_provider_names == ("alpha",)

    payload = snapshot.as_dict()
    assert payload["available_providers"] == 1
    alpha_runtime = payload["providers"]["alpha"]
    assert alpha_runtime["config"]["source_type"] == DataSourceType.AMAZINGDATA.value
    assert sorted(alpha_runtime["metadata"]["capabilities"]) == [
        DataCapability.KLINE_DATA.value,
        DataCapability.REALTIME_QUOTES.value,
    ]
    assert alpha_runtime["effective_priority"] == 2
    assert alpha_runtime["statistics"] == {"requests": 2}

    beta_runtime = payload["providers"]["beta"]
    assert beta_runtime["running"] is False
    assert beta_runtime["statistics"] == {"value": "offline"}


def test_get_statistics_returns_serializable_payload(manager_with_providers):
    manager, _, _ = manager_with_providers

    stats = manager.get_statistics()
    assert isinstance(stats, dict)
    assert stats["total_providers"] == 2
    assert stats["providers"]["alpha"]["config"]["name"] == "alpha"
