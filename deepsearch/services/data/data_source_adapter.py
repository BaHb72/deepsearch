"""
股票数据源适配器

实现智能路由、故障转移和熔断器功能
"""
import time
from collections import defaultdict
from typing import Dict, Any, List, Optional

from loguru import logger

from .interfaces import IStockDataSource, ICircuitBreaker


class CircuitBreaker(ICircuitBreaker):
    """
    熔断器实现
    
    当某个数据源失败次数过多时，自动熔断一段时间
    """

    def __init__(
            self,
            failure_threshold: int = 5,
            recovery_timeout: int = 60,
            half_open_attempts: int = 3
    ):
        """
        初始化熔断器
        
        Args:
            failure_threshold: 失败阈值，超过此值触发熔断
            recovery_timeout: 熔断恢复时间（秒）
            half_open_attempts: 半开状态尝试次数
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_attempts = half_open_attempts

        # 状态记录
        self._failure_counts = defaultdict(int)
        self._success_counts = defaultdict(int)
        self._last_failure_time = {}
        self._circuit_open = {}
        self._half_open_count = defaultdict(int)

    def is_open(self, source_id: str) -> bool:
        """检查熔断器是否打开"""
        if source_id not in self._circuit_open:
            return False

        if not self._circuit_open[source_id]:
            return False

        # 检查是否可以进入半开状态
        if source_id in self._last_failure_time:
            elapsed = time.time() - self._last_failure_time[source_id]
            if elapsed > self.recovery_timeout:
                # 进入半开状态，允许有限次尝试
                if self._half_open_count[source_id] < self.half_open_attempts:
                    self._half_open_count[source_id] += 1
                    logger.info(
                        f"熔断器半开：{source_id} (尝试 {self._half_open_count[source_id]}/{self.half_open_attempts})")
                    return False
                else:
                    # 半开尝试用完，继续熔断
                    self._last_failure_time[source_id] = time.time()
                    self._half_open_count[source_id] = 0

        return True

    def record_success(self, source_id: str) -> None:
        """记录成功调用"""
        self._success_counts[source_id] += 1

        # 如果在半开状态成功，则关闭熔断器
        if self._circuit_open.get(source_id, False):
            self._circuit_open[source_id] = False
            self._failure_counts[source_id] = 0
            self._half_open_count[source_id] = 0
            logger.info(f"熔断器关闭：{source_id}")

    def record_failure(self, source_id: str) -> None:
        """记录失败调用"""
        self._failure_counts[source_id] += 1
        self._last_failure_time[source_id] = time.time()

        # 检查是否需要触发熔断
        if self._failure_counts[source_id] >= self.failure_threshold:
            if not self._circuit_open.get(source_id, False):
                self._circuit_open[source_id] = True
                logger.warning(f"熔断器打开：{source_id} (失败次数: {self._failure_counts[source_id]})")

    def reset(self, source_id: str) -> None:
        """重置熔断器"""
        self._failure_counts[source_id] = 0
        self._success_counts[source_id] = 0
        self._circuit_open[source_id] = False
        self._half_open_count[source_id] = 0
        if source_id in self._last_failure_time:
            del self._last_failure_time[source_id]

    def get_stats(self, source_id: str) -> Dict[str, Any]:
        """获取熔断器统计信息"""
        return {
            "failure_count": self._failure_counts[source_id],
            "success_count": self._success_counts[source_id],
            "is_open": self._circuit_open.get(source_id, False),
            "half_open_attempts": self._half_open_count[source_id]
        }


class StockDataSourceAdapter(IStockDataSource):
    """
    股票数据源适配器
    
    实现智能路由、故障转移和负载均衡
    """

    def __init__(self, circuit_breaker: Optional[ICircuitBreaker] = None):
        """
        初始化适配器
        
        Args:
            circuit_breaker: 熔断器实例
        """
        self._sources: List[IStockDataSource] = []
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._current_index = 0  # 用于轮询

        # 统计信息
        self._stats = defaultdict(lambda: {"requests": 0, "successes": 0, "failures": 0})

    def register_source(self, source: IStockDataSource) -> None:
        """
        注册数据源
        
        Args:
            source: 数据源实例
        """
        self._sources.append(source)
        # 按优先级排序
        self._sources.sort(key=lambda x: x.get_priority())
        logger.info(f"注册数据源: {source.get_name()} (优先级: {source.get_priority()})")

    def unregister_source(self, source_name: str) -> None:
        """
        注销数据源
        
        Args:
            source_name: 数据源名称
        """
        self._sources = [s for s in self._sources if s.get_name() != source_name]
        logger.info(f"注销数据源: {source_name}")

    async def fetch_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取股票信息，自动故障转移
        
        Args:
            symbol: 股票代码
            
        Returns:
            股票信息字典
        """
        for source in self._sources:
            source_name = source.get_name()

            # 若不可用，尝试初始化一次
            try:
                if not source.is_available() and hasattr(source, 'initialize'):
                    logger.debug(f"尝试初始化数据源: {source_name}")
                    await getattr(source, 'initialize')()
            except Exception as e:
                logger.warning(f"初始化数据源失败 {source_name}: {e}")

            # 检查数据源是否可用
            if not source.is_available():
                logger.debug(f"数据源不可用: {source_name}")
                continue

            # 检查熔断器
            if self._circuit_breaker.is_open(source_name):
                logger.debug(f"数据源被熔断: {source_name}")
                continue

            # 尝试获取数据
            self._stats[source_name]["requests"] += 1

            try:
                logger.debug(f"尝试从 {source_name} 获取股票信息: {symbol}")
                result = await source.fetch_stock_info(symbol)

                if result:
                    self._circuit_breaker.record_success(source_name)
                    self._stats[source_name]["successes"] += 1
                    logger.debug(f"成功从 {source_name} 获取股票信息: {symbol}")
                    return result

            except Exception as e:
                self._circuit_breaker.record_failure(source_name)
                self._stats[source_name]["failures"] += 1
                logger.warning(f"从 {source_name} 获取股票信息失败: {e}")

        logger.error(f"所有数据源都无法获取股票信息: {symbol}")
        return None

    async def fetch_stock_list(self) -> List[Dict[str, Any]]:
        """
        获取股票列表，自动故障转移
        
        Returns:
            股票列表
        """
        for source in self._sources:
            source_name = source.get_name()

            if not source.is_available():
                continue

            if self._circuit_breaker.is_open(source_name):
                continue

            try:
                logger.debug(f"尝试从 {source_name} 获取股票列表")
                result = await source.fetch_stock_list()

                if result:
                    self._circuit_breaker.record_success(source_name)
                    logger.debug(f"成功从 {source_name} 获取股票列表")
                    return result

            except Exception as e:
                self._circuit_breaker.record_failure(source_name)
                logger.warning(f"从 {source_name} 获取股票列表失败: {e}")

        logger.error("所有数据源都无法获取股票列表")
        return []

    async def batch_fetch_stock_info(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        批量获取股票信息
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            股票信息字典
        """
        for source in self._sources:
            source_name = source.get_name()

            if not source.is_available():
                continue

            if self._circuit_breaker.is_open(source_name):
                continue

            try:
                logger.debug(f"尝试从 {source_name} 批量获取股票信息")
                result = await source.batch_fetch_stock_info(symbols)

                if result:
                    self._circuit_breaker.record_success(source_name)
                    logger.debug(f"成功从 {source_name} 批量获取股票信息")
                    return result

            except Exception as e:
                self._circuit_breaker.record_failure(source_name)
                logger.warning(f"从 {source_name} 批量获取股票信息失败: {e}")

        # 如果批量获取失败，逐个获取
        logger.warning("批量获取失败，尝试逐个获取")
        result = {}
        for symbol in symbols:
            info = await self.fetch_stock_info(symbol)
            if info:
                result[symbol] = info

        return result

    def is_available(self) -> bool:
        """检查是否有可用数据源"""
        for source in self._sources:
            if source.is_available() and not self._circuit_breaker.is_open(source.get_name()):
                return True
        return False

    def get_priority(self) -> int:
        """获取优先级（返回最高优先级）"""
        if self._sources:
            return self._sources[0].get_priority()
        return 999

    def get_name(self) -> str:
        """获取适配器名称"""
        return "StockDataSourceAdapter"

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "sources": [],
            "total_sources": len(self._sources),
            "available_sources": sum(1 for s in self._sources if s.is_available())
        }

        for source in self._sources:
            source_name = source.get_name()
            source_stats = {
                "name": source_name,
                "priority": source.get_priority(),
                "available": source.is_available(),
                "circuit_breaker": self._circuit_breaker.get_stats(source_name) if hasattr(self._circuit_breaker,
                                                                                           'get_stats') else {},
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

    def switch_source(self, source_name: str) -> bool:
        """
        手动切换到指定数据源（将其优先级临时调至最高）
        
        Args:
            source_name: 数据源名称
            
        Returns:
            切换是否成功
        """
        for i, source in enumerate(self._sources):
            if source.get_name() == source_name:
                # 将该数据源移到最前面
                self._sources.insert(0, self._sources.pop(i))
                logger.info(f"手动切换到数据源: {source_name}")
                return True

        logger.warning(f"未找到数据源: {source_name}")
        return False
