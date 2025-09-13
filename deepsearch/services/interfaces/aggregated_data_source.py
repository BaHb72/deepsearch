"""
聚合数据源

实现智能路由、故障转移和负载均衡
"""
import asyncio
from collections import defaultdict
from typing import Dict, Any, List, Optional

import pandas as pd
from loguru import logger

from deepsearch.core.async_component import AsyncComponent
from deepsearch.core.interfaces.component import ComponentType
from .data_source_adapter import CircuitBreaker
from .data_source_interface import IDataSource


class AggregatedDataSource(AsyncComponent, IDataSource):
    """
    聚合数据源
    
    管理多个数据源，提供智能路由和故障转移
    """

    def __init__(self, name: str = "aggregated_data_source"):
        """初始化聚合数据源"""
        super().__init__(
            name=name,
            component_type=ComponentType.BUSINESS,
            display_name="聚合数据源"
        )

        self._sources: List[IDataSource] = []
        self._circuit_breaker = CircuitBreaker()
        self._stats = defaultdict(lambda: {"requests": 0, "successes": 0, "failures": 0})

    def add_source(self, source: IDataSource) -> None:
        """
        添加数据源
        
        Args:
            source: 数据源实例
        """
        self._sources.append(source)
        # 按优先级排序
        self._sources.sort(key=lambda x: x.get_priority())
        logger.info(f"添加数据源: {source.name} (优先级: {source.get_priority()})")

    def remove_source(self, source_name: str) -> None:
        """
        移除数据源
        
        Args:
            source_name: 数据源名称
        """
        self._sources = [s for s in self._sources if s.name != source_name]
        logger.info(f"移除数据源: {source_name}")

    async def _initialize(self) -> None:
        """初始化所有数据源"""
        init_tasks = []
        for source in self._sources:
            init_tasks.append(source.initialize_async())

        results = await asyncio.gather(*init_tasks, return_exceptions=True)

        for source, result in zip(self._sources, results):
            if isinstance(result, Exception):
                logger.error(f"数据源 {source.name} 初始化失败: {result}")
            else:
                logger.info(f"数据源 {source.name} 初始化成功")

        self._instance = self

    async def _start(self) -> None:
        """启动所有数据源"""
        start_tasks = []
        for source in self._sources:
            start_tasks.append(source.start_async())

        await asyncio.gather(*start_tasks, return_exceptions=True)
        logger.info("聚合数据源启动完成")

    async def _stop(self) -> None:
        """停止所有数据源"""
        stop_tasks = []
        for source in self._sources:
            stop_tasks.append(source.stop_async())

        await asyncio.gather(*stop_tasks, return_exceptions=True)
        logger.info("聚合数据源停止完成")

    async def fetch_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取股票信息，自动故障转移
        """
        for source in self._sources:
            source_name = source.name

            # 检查数据源是否可用
            if not source.is_available():
                logger.debug(f"数据源不可用: {source_name}")
                continue

            # 检查熔断器
            if self._circuit_breaker.is_open(source_name):
                logger.debug(f"数据源被熔断: {source_name}")
                continue

            # 记录请求
            self._stats[source_name]["requests"] += 1

            try:
                logger.debug(f"尝试从 {source_name} 获取股票信息: {symbol}")
                result = await source.fetch_stock_info(symbol)

                if result:
                    self._circuit_breaker.record_success(source_name)
                    self._stats[source_name]["successes"] += 1
                    logger.debug(f"成功从 {source_name} 获取股票信息")
                    return result

            except Exception as e:
                self._circuit_breaker.record_failure(source_name)
                self._stats[source_name]["failures"] += 1
                logger.warning(f"从 {source_name} 获取股票信息失败: {e}")

        logger.error(f"所有数据源都无法获取股票信息: {symbol}")
        return None

    async def fetch_stock_list(self) -> List[Dict[str, Any]]:
        """获取股票列表"""
        for source in self._sources:
            if not source.is_available():
                continue

            if self._circuit_breaker.is_open(source.name):
                continue

            try:
                result = await source.fetch_stock_list()
                if result:
                    self._circuit_breaker.record_success(source.name)
                    return result
            except Exception as e:
                self._circuit_breaker.record_failure(source.name)
                logger.warning(f"从 {source.name} 获取股票列表失败: {e}")

        return []

    async def fetch_realtime_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取实时行情"""
        for source in self._sources:
            if not source.is_available():
                continue

            if self._circuit_breaker.is_open(source.name):
                continue

            try:
                result = await source.fetch_realtime_quote(symbol)
                if result:
                    self._circuit_breaker.record_success(source.name)
                    return result
            except Exception as e:
                self._circuit_breaker.record_failure(source.name)
                logger.warning(f"从 {source.name} 获取实时行情失败: {e}")

        return None

    async def fetch_kline_data(
            self,
            symbol: str,
            period: str = "1d",
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """获取K线数据"""
        for source in self._sources:
            if not source.is_available():
                continue

            if self._circuit_breaker.is_open(source.name):
                continue

            try:
                result = await source.fetch_kline_data(symbol, period, start_date, end_date)
                if result is not None and not result.empty:
                    self._circuit_breaker.record_success(source.name)
                    return result
            except Exception as e:
                self._circuit_breaker.record_failure(source.name)
                logger.warning(f"从 {source.name} 获取K线数据失败: {e}")

        return None

    def get_priority(self) -> int:
        """获取优先级"""
        if self._sources:
            return self._sources[0].get_priority()
        return 999

    def is_available(self) -> bool:
        """检查是否有可用数据源"""
        for source in self._sources:
            if source.is_available() and not self._circuit_breaker.is_open(source.name):
                return True
        return False

    def switch_source(self, source_name: str) -> bool:
        """
        手动切换到指定数据源
        
        Args:
            source_name: 数据源名称
            
        Returns:
            切换是否成功
        """
        for i, source in enumerate(self._sources):
            if source.name == source_name:
                # 将该数据源移到最前面
                self._sources.insert(0, self._sources.pop(i))
                # 重置该数据源的熔断器
                self._circuit_breaker.reset(source_name)
                logger.info(f"手动切换到数据源: {source_name}")
                return True

        logger.warning(f"未找到数据源: {source_name}")
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "sources": [],
            "total_sources": len(self._sources),
            "available_sources": sum(1 for s in self._sources if s.is_available())
        }

        for source in self._sources:
            source_name = source.name
            source_stats = {
                "name": source_name,
                "priority": source.get_priority(),
                "available": source.is_available(),
                "circuit_breaker_open": self._circuit_breaker.is_open(source_name),
                "requests": self._stats[source_name]["requests"],
                "successes": self._stats[source_name]["successes"],
                "failures": self._stats[source_name]["failures"],
                "success_rate": (
                    self._stats[source_name]["successes"] / self._stats[source_name]["requests"] * 100
                    if self._stats[source_name]["requests"] > 0 else 0
                )
            }
            stats["sources"].append(source_stats)

        return stats
