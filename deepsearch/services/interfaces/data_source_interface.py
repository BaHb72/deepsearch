"""
统一的数据源接口定义

基于现有Component体系，定义标准的数据源接口
"""
from abc import abstractmethod
from typing import Dict, Any, List, Optional, Protocol

import pandas as pd

from deepsearch.core.interfaces.component import Component


class IDataSource(Component, Protocol):
    """
    统一的数据源接口
    
    继承Component接口，与现有组件体系保持一致
    所有数据源必须实现此接口
    """

    @abstractmethod
    async def fetch_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取股票基础信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            股票信息字典，包含name, industry, sector等
        """
        pass

    @abstractmethod
    async def fetch_stock_list(self) -> List[Dict[str, Any]]:
        """
        获取股票列表
        
        Returns:
            股票列表
        """
        pass

    @abstractmethod
    async def fetch_realtime_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情
        
        Args:
            symbol: 股票代码
            
        Returns:
            实时行情数据
        """
        pass

    @abstractmethod
    async def fetch_kline_data(
            self,
            symbol: str,
            period: str = "1d",
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        获取K线数据
        
        Args:
            symbol: 股票代码
            period: 周期 (1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M)
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            K线数据DataFrame
        """
        pass

    @abstractmethod
    def get_priority(self) -> int:
        """
        获取数据源优先级
        
        Returns:
            优先级数值，越小优先级越高
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        检查数据源是否可用
        
        Returns:
            是否可用
        """
        pass
