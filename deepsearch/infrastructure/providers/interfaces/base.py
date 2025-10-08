"""
基础接口定义
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from .payloads import DataPayload


class DataSourceType(Enum):
    """数据源类型枚举"""

    AMAZINGDATA = "amazingdata"
    CLOUDFLARE = "cloudflare"
    AKSHARE = "akshare"
    QMT = "qmt"
    DEFAULT = "default"
    CUSTOM = "custom"


@dataclass
class DataProviderConfig:
    """数据提供者配置"""

    name: Optional[str] = None  # 数据提供者名称
    source_type: DataSourceType = DataSourceType.DEFAULT
    enabled: bool = True
    priority: int = 100
    timeout: float = 30.0
    retry_count: int = 3
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

    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None



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
        for key in ("symbol", "symbols", "start_date", "end_date", "period", "adjust", "request_type", "source"):
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


class DataProvider(ABC):
    """数据提供者基类"""

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
        """获取股票列表"""
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
        """获取K线数据"""
        pass

    async def get_realtime_quotes(self, symbols: List[str]) -> Optional[List[Dict[str, Any]]]:
        """获取实时行情"""
        pass

    async def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取股票信息"""
        pass

    async def get_order_book(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取订单簿"""
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
