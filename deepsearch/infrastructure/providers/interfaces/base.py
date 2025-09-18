"""
基础接口定义
"""
from enum import Enum
from typing import Protocol, Dict, Any, Optional, List
from abc import ABC, abstractmethod
from dataclasses import dataclass


class DataSourceType(Enum):
    """数据源类型枚举"""
    AMAZINGDATA = "amazingdata"
    CLOUDFLARE = "cloudflare"
    CLOUDFLARE_PROXY = "cloudflare_proxy"  # CloudFlare Workers代理
    AKSHARE = "akshare"
    QMT = "qmt"
    DEFAULT = "default"
    CUSTOM = "custom"


@dataclass
class DataProviderConfig:
    """数据提供者配置"""
    name: Optional[str] = None  # 数据提供者名称
    enabled: bool = True
    priority: int = 100
    timeout: float = 30.0
    retry_count: int = 3
    config: Optional[Dict[str, Any]] = None


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
    symbol: str
    request_type: str
    params: Optional[Dict[str, Any]] = None


@dataclass
class DataResponse:
    """数据响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


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
    async def get_stock_list(self, limit: Optional[int] = None, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """获取股票列表"""
        pass

    @abstractmethod
    async def get_kline_data(
        self,
        symbol: str,
        period: str = '1d',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs
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


class IDataSource(Protocol):
    """数据源接口协议"""

    async def initialize(self) -> bool:
        """初始化数据源"""
        ...

    async def get_stock_list(self, limit: Optional[int] = None, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """获取股票列表"""
        ...

    async def get_kline_data(
        self,
        symbol: str,
        period: str = '1d',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs
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