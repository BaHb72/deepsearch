"""
基础接口定义
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from deepsearch.ports.data_sources import DataSourceType

from .payloads import DataPayload


@dataclass
class DataProviderConfig:
    """数据提供者配置"""

    name: Optional[str] = None  # 数据提供者名称
    source_type: DataSourceType = DataSourceType.DEFAULT
    enabled: bool = True
    priority: int = 100
    timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 1.0
    config: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """规范化来源类型和配置载荷"""
        if isinstance(self.source_type, str):
            normalized = self.source_type.strip().lower()
            for item in DataSourceType:
                if item.value == normalized or item.name.lower() == normalized:
                    self.source_type = item
                    break
            else:
                self.source_type = DataSourceType.CUSTOM
        if self.config is None:
            self.config = {}
        elif not isinstance(self.config, dict):
            self.config = dict(self.config)


@dataclass
class ProxyConfig:
    """代理配置"""

    host: str | None = None
    port: int | None = None
    username: Optional[str] = None
    password: Optional[str] = None
    proxy_list: list[str] = field(default_factory=list)
    proxy_api_url: Optional[str] = None
    proxy_api_key: Optional[str] = None
    rotation_strategy: str = "round_robin"
    timeout: float = 5.0
    blacklist_threshold: int = 3
    blacklist_duration: int = 300
    health_check_interval: int = 60
    pool_size: int = 0
    enabled: bool = True

    def as_http_url(self) -> Optional[str]:
        """返回首选 HTTP 代理地址，便于快速注入 requests/urllib3."""
        if self.host is None or self.port is None:
            return None
        auth = ""
        if self.username:
            auth = self.username
            if self.password:
                auth = f"{auth}:{self.password}"
            auth += "@"
        return f"http://{auth}{self.host}:{self.port}"


@dataclass
class DataRequest:
    """数据请求"""

    request_type: str = "generic"
    source: Optional[DataSourceType] = None
    symbol: Optional[str] = None
    symbols: Optional[List[str]] = None
    period: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    adjust: Optional[str] = None
    params: Dict[str, object] = field(default_factory=dict)
    extra_params: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """补全常用字段并构建参数映射"""
        for key in (
            "symbol",
            "symbols",
            "start_date",
            "end_date",
            "period",
            "adjust",
            "request_type",
            "source",
        ):
            if key in self.params and getattr(self, key) is None:
                setattr(self, key, self.params[key])
        if isinstance(self.symbols, str):
            self.symbols = [self.symbols]
        if isinstance(self.source, str):
            normalized = self.source.strip().lower()
            for item in DataSourceType:
                if item.value == normalized or item.name.lower() == normalized:
                    self.source = item
                    break
        normalized_params: Dict[str, object] = dict(self.params)
        if self.symbol is not None:
            normalized_params.setdefault("symbol", self.symbol)
        if self.symbols is not None:
            normalized_params.setdefault("symbols", self.symbols)
        if self.period is not None:
            normalized_params.setdefault("period", self.period)
        if self.start_date is not None:
            normalized_params.setdefault("start_date", self.start_date)
        if self.end_date is not None:
            normalized_params.setdefault("end_date", self.end_date)
        if self.adjust is not None:
            normalized_params.setdefault("adjust", self.adjust)
        normalized_params.setdefault("request_type", self.request_type)
        if self.source is not None:
            normalized_params.setdefault("source", self.source)
        if self.extra_params:
            merged = dict(normalized_params)
            merged.update(self.extra_params)
            self.extra_params = merged
        else:
            self.extra_params = normalized_params
        self.params = normalized_params


@dataclass(init=False)
class DataResponse:
    """数据响应"""

    success: bool
    data: DataPayload | None
    error: Optional[str]
    metadata: Dict[str, object]

    def __init__(
        self,
        success: bool,
        data: DataPayload | None = None,
        error: Optional[str] = None,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        self.success = success
        self.data = data
        self.error = error
        self.metadata = dict(metadata or {})


class DataProviderError(Exception):
    """数据提供者错误"""

    pass


class TGWError(DataProviderError):
    """TGW网关相关错误

    用于标识以下情况：
    - TGW连接失败
    - TGW超时
    - TGW初始化失败
    - SDK系统退出
    """

    def __init__(self, message: str, error_code: str | None = None, is_recoverable: bool = False):
        super().__init__(message)
        self.error_code = error_code
        self.is_recoverable = is_recoverable


class DataProvider(ABC):
    """数据提供者基类

    .. deprecated::
        此类已废弃，请使用新的 UnifiedDataFeed 和 Adapter 架构：

        旧方式:
            provider = get_registry().get_provider_instance("miniqmt")
            data = await provider.get_kline_data(symbol="000001.SZ", ...)

        新方式:
            from deepsearch.application.services.unified_data import get_unified_feed
            from deepsearch.ports.data.requests import KlineRequest

            feed = get_unified_feed()
            data = await feed.query(KlineRequest(asset=..., timeframe=...))
    """

    def __init__(self, config: DataProviderConfig):
        """初始化数据提供者

        Args:
            config: 数据提供者配置
        """
        self.config = config

    @abstractmethod
    async def initialize(self) -> bool:
        """初始化数据源"""
        pass

    @abstractmethod
    async def get_stock_list(
        self, limit: Optional[int] = None, **kwargs
    ) -> Optional[List[Dict[str, Any]]]:
        """获取股票列表

        .. deprecated:: 建议使用 UnifiedDataFeed.query(StockListRequest())
        """
        pass

    @abstractmethod
    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """获取K线数据

        .. deprecated:: 建议使用 UnifiedDataFeed.query(KlineRequest(...))
        """
        pass

    async def get_realtime_quotes(self, symbols: List[str]) -> Optional[List[Dict[str, Any]]]:
        """获取实时行情

        .. deprecated:: 建议使用 UnifiedDataFeed.query(RealtimeQuoteRequest(...))
        """
        pass

    async def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取股票信息"""
        pass

    async def get_order_book(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取订单簿

        .. deprecated:: 建议使用 UnifiedDataFeed.query(OrderbookRequest(...))
        """
        pass

    async def initialize_async(self) -> bool:
        """兼容异步初始化协议，默认调用 initialize。"""
        return await self.initialize()

    async def start_async(self) -> bool:
        """组件启动协议，默认为无额外启动逻辑。"""
        return True

    async def stop_async(self) -> None:
        """组件停止协议，默认为无额外处理。"""
        return None

    def get_statistics(self) -> Dict[str, object]:
        """提供基础统计结构，默认返回空字典。"""
        return {}


class IDataSource(Protocol):
    """数据源接口协议"""

    async def initialize(self) -> bool:
        """初始化数据源"""
        ...

    async def get_stock_list(
        self, limit: Optional[int] = None, **kwargs
    ) -> Optional[List[Dict[str, Any]]]:
        """获取股票列表"""
        ...

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> Optional[List[Dict[str, Any]]]:
        """获取K线数据"""
        ...

    async def get_realtime_quotes(self, symbols: List[str]) -> Optional[List[Dict[str, Any]]]:
        """获取实时行情"""
        ...

    async def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取股票信息"""
        ...

    async def get_order_book(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取订单簿"""
        ...
