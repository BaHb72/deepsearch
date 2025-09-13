"""
数据源桥接器

将现有的DataProvider体系适配为IDataSource接口
"""
from typing import Dict, Any, List, Optional

import pandas as pd

from deepsearch.core.interfaces.component import ComponentStatus, ComponentType
from deepsearch.data_providers.interfaces.base import DataProvider, DataRequest
from .data_source_interface import IDataSource


class DataProviderBridge(IDataSource):
    """
    数据提供者桥接器
    
    将现有的DataProvider适配为IDataSource接口
    保持向后兼容性
    """

    def __init__(self, provider: DataProvider):
        """
        初始化桥接器
        
        Args:
            provider: 现有的DataProvider实例
        """
        self._provider = provider
        self._priority = 10  # 默认优先级

    @property
    def name(self) -> str:
        """组件名称"""
        return f"bridge_{self._provider.config.name}"

    @property
    def component_type(self) -> ComponentType:
        """组件类型"""
        return self._provider.component_type

    @property
    def status(self) -> ComponentStatus:
        """组件状态"""
        return self._provider.status

    async def initialize_async(self) -> None:
        """异步初始化"""
        await self._provider.initialize_async()

    async def start_async(self) -> None:
        """异步启动"""
        await self._provider.start_async()

    async def stop_async(self) -> None:
        """异步停止"""
        await self._provider.stop_async()

    def health_check(self) -> bool:
        """健康检查"""
        return self._provider.health_check()

    async def fetch_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取股票信息
        
        通过DataProvider的通用接口获取
        """
        request = DataRequest(
            symbol=symbol,
            fields=["name", "industry", "sector", "market", "listed_date"]
        )

        response = await self._provider.get_data(request)

        if response.success and response.data is not None:
            # 将DataFrame转换为字典
            if isinstance(response.data, pd.DataFrame) and not response.data.empty:
                return response.data.iloc[0].to_dict()

        return None

    async def fetch_stock_list(self) -> List[Dict[str, Any]]:
        """获取股票列表"""
        request = DataRequest()
        response = await self._provider.get_data(request)

        if response.success and response.data is not None:
            if isinstance(response.data, pd.DataFrame):
                return response.data.to_dict('records')

        return []

    async def fetch_realtime_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取实时行情"""
        request = DataRequest(
            symbol=symbol,
            period="realtime"
        )

        response = await self._provider.get_data(request)

        if response.success and response.data is not None:
            if isinstance(response.data, pd.DataFrame) and not response.data.empty:
                return response.data.iloc[0].to_dict()

        return None

    async def fetch_kline_data(
            self,
            symbol: str,
            period: str = "1d",
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """获取K线数据"""
        request = DataRequest(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date
        )

        response = await self._provider.get_data(request)

        if response.success:
            return response.data

        return None

    def get_priority(self) -> int:
        """获取优先级"""
        # 从配置中获取优先级
        if hasattr(self._provider.config, 'priority'):
            return self._provider.config.priority
        return self._priority

    def is_available(self) -> bool:
        """检查是否可用"""
        return self._provider.status == ComponentStatus.RUNNING
