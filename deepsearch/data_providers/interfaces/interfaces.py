"""
数据提供者接口定义

定义统一的数据访问接口，所有具体的数据提供者都应实现这些接口。
这样服务层可以依赖接口而非具体实现。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import pandas as pd

# 导入基础类型定义
try:
    from .base import DataRequest, DataResponse
except ImportError:
    # 如果base模块不可用，定义简单的替代
    from dataclasses import dataclass, field
    from datetime import datetime
    
    @dataclass
    class DataRequest:
        symbol: Optional[str] = None
        symbols: Optional[List[str]] = None
        start_date: Optional[str] = None
        end_date: Optional[str] = None
        period: str = "1d"
        adjust: str = "qfq"
        fields: Optional[List[str]] = None
        extra_params: Dict[str, Any] = field(default_factory=dict)
    
    @dataclass
    class DataResponse:
        success: bool
        data: Optional[pd.DataFrame] = None
        error: Optional[str] = None
        timestamp: datetime = field(default_factory=datetime.now)
        source: Optional[str] = None
        request_time: float = 0
        proxy_used: Optional[str] = None


class IDataProvider(ABC):
    """数据提供者统一接口"""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        初始化数据提供者
        
        Returns:
            是否初始化成功
        """
        pass
    
    @abstractmethod
    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """
        获取实时行情
        
        Args:
            symbol: 股票代码
            
        Returns:
            包含实时行情的字典
        """
        pass
    
    @abstractmethod
    async def get_stock_hist(
        self,
        symbol: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = ""
    ) -> Dict[str, Any]:
        """
        获取历史K线数据
        
        Args:
            symbol: 股票代码
            period: 周期
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型
            
        Returns:
            历史K线数据
        """
        pass
    
    @abstractmethod
    async def fetch_stock_list(self) -> List[Dict[str, str]]:
        """
        获取股票列表
        
        Returns:
            股票列表
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        检查连接状态
        
        Returns:
            是否已连接
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """
        关闭连接，释放资源
        """
        pass
    
    async def _fetch_with_fallback(
        self,
        api_name: str,
        params: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        带故障转移的数据获取（可选实现）
        
        Args:
            api_name: API名称或路径
            params: API参数
            max_retries: 最大重试次数
            
        Returns:
            API响应数据
        """
        # 默认实现：返回未实现错误
        return {"error": "Method not implemented"}


class IAkShareProvider(IDataProvider):
    """AkShare数据提供者接口 - 扩展接口"""
    
    @abstractmethod
    async def fetch_with_api(
        self,
        api_name: str,
        params: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        调用AkShare API的统一接口
        
        Args:
            api_name: API名称
            params: 参数
            max_retries: 最大重试次数
            
        Returns:
            API返回数据
        """
        pass
    
    @abstractmethod
    async def fetch_market_overview(self) -> Dict[str, Any]:
        """获取市场概览"""
        pass
    
    @abstractmethod
    async def fetch_sector_data(self) -> List[Dict[str, Any]]:
        """获取板块数据"""
        pass


class DataProviderAdapter:
    """
    数据提供者适配器
    
    将不同的数据提供者实现适配到统一接口，确保所有提供者都能一致地被调用
    """
    
    def __init__(self, provider: Any):
        """
        初始化适配器
        
        Args:
            provider: 原始数据提供者实例
        """
        self.provider = provider
        self.name = getattr(provider, 'name', provider.__class__.__name__)
    
    async def initialize(self) -> bool:
        """初始化"""
        if hasattr(self.provider, 'initialize'):
            return await self.provider.initialize()
        elif hasattr(self.provider, '_initialize'):
            await self.provider._initialize()
            return True
        return True
    
    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """获取实时行情"""
        if hasattr(self.provider, 'get_realtime_quote'):
            return await self.provider.get_realtime_quote(symbol)
        elif hasattr(self.provider, '_fetch_realtime_quote'):
            return await self.provider._fetch_realtime_quote(symbol)
        elif hasattr(self.provider, '_fetch_realtime_quote_sync'):
            # 处理同步方法
            import asyncio
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self.provider._fetch_realtime_quote_sync,
                symbol
            )
        else:
            return {"error": f"Provider {self.name} does not support realtime quotes"}
    
    async def get_stock_hist(
        self,
        symbol: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = ""
    ) -> Dict[str, Any]:
        """获取历史K线数据"""
        # 尝试多个可能的方法名
        if hasattr(self.provider, 'get_stock_hist'):
            return await self.provider.get_stock_hist(
                symbol, period, start_date, end_date, adjust
            )
        elif hasattr(self.provider, 'get_kline_data'):
            df = await self.provider.get_kline_data(
                symbol, period, start_date, end_date, adjust
            )
            return {"success": True, "data": df.to_dict('records') if df is not None else []}
        elif hasattr(self.provider, 'get_daily_data'):
            # 兼容只支持日线的旧接口
            if period == "daily" or period == "1d":
                df = await self.provider.get_daily_data(
                    symbol, start_date, end_date
                )
                return {"success": True, "data": df.to_dict('records') if df is not None else []}
        return {"error": f"Provider {self.name} does not support historical data"}
    
    async def fetch_stock_list(self) -> List[Dict[str, str]]:
        """获取股票列表"""
        if hasattr(self.provider, 'fetch_stock_list'):
            return await self.provider.fetch_stock_list()
        elif hasattr(self.provider, 'get_stock_list'):
            return await self.provider.get_stock_list()
        elif hasattr(self.provider, '_fetch_stock_list'):
            return await self.provider._fetch_stock_list()
        else:
            return []
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        if hasattr(self.provider, 'is_connected'):
            return self.provider.is_connected()
        elif hasattr(self.provider, 'initialized'):
            return self.provider.initialized
        elif hasattr(self.provider, '_initialized'):
            return self.provider._initialized
        else:
            return True
    
    async def close(self) -> None:
        """关闭连接"""
        if hasattr(self.provider, 'close'):
            await self.provider.close()
        elif hasattr(self.provider, '_stop'):
            await self.provider._stop()
        elif hasattr(self.provider, 'shutdown'):
            await self.provider.shutdown()
    
    async def _fetch_with_fallback(
        self,
        api_name: str,
        params: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """带故障转移的数据获取"""
        if hasattr(self.provider, '_fetch_with_fallback'):
            return await self.provider._fetch_with_fallback(
                api_name, params, max_retries
            )
        elif hasattr(self.provider, 'fetch_with_api'):
            return await self.provider.fetch_with_api(
                api_name, params, max_retries
            )
        else:
            # 尝试使用通用的数据获取方法
            return {"error": f"Provider {self.name} does not support _fetch_with_fallback"}