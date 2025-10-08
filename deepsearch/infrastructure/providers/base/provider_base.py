"""
数据提供者基础类
确保所有必需的属性都被正确初始化
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from loguru import logger


class BaseDataProvider(ABC):
    """
    数据提供者基础类

    确保所有子类都正确初始化必需的属性
    """

    def __init__(self):
        """初始化基础属性"""
        # 基础属性 - 所有子类都应该有这些
        self.initialized = False
        self.session = None
        self._cache = {}
        self._cache_ttl = {
            "realtime": 10,  # 实时数据缓存10秒
            "historical": 300,  # 历史数据缓存5分钟
            "info": 3600,  # 信息数据缓存1小时
        }
        self.config = {}
        self.status = "inactive"
        self.last_access_time = None
        self.error_count = 0
        self.success_count = 0

        # 性能统计
        self._performance_stats: Dict[str, float | int] = {
            "total_requests": 0,
            "failed_requests": 0,
            "total_latency": 0.0,
            "min_latency": float("inf"),
            "max_latency": 0.0,
        }

        logger.debug(f"初始化基础数据提供者: {self.__class__.__name__}")

    @abstractmethod
    async def initialize(self) -> bool:
        """
        初始化数据提供者

        子类必须实现此方法并调用基类的初始化检查

        Returns:
            bool: 初始化是否成功
        """
        pass

    @abstractmethod
    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """
        获取实时行情

        Args:
            symbol: 股票代码

        Returns:
            实时行情数据
        """
        pass

    @abstractmethod
    async def get_historical_data(
        self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取历史数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            历史数据
        """
        pass

    def _check_initialization(self) -> bool:
        """
        检查初始化状态

        Returns:
            bool: 是否已初始化
        """
        if not self.initialized:
            logger.warning(f"{self.__class__.__name__} 未初始化")
            return False
        return True

    def _update_stats(self, success: bool, latency: float):
        """
        更新性能统计

        Args:
            success: 请求是否成功
            latency: 请求延迟（秒）
        """
        self._performance_stats["total_requests"] += 1

        if not success:
            self._performance_stats["failed_requests"] += 1
            self.error_count += 1
        else:
            self.success_count += 1

        self._performance_stats["total_latency"] += latency
        self._performance_stats["min_latency"] = min(
            self._performance_stats["min_latency"], latency
        )
        self._performance_stats["max_latency"] = max(
            self._performance_stats["max_latency"], latency
        )

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计

        Returns:
            性能统计数据
        """
        stats = self._performance_stats.copy()

        # 计算平均延迟
        if stats["total_requests"] > 0:
            stats["avg_latency"] = stats["total_latency"] / stats["total_requests"]
            stats["success_rate"] = (
                (stats["total_requests"] - stats["failed_requests"]) / stats["total_requests"] * 100
            )
        else:
            stats["avg_latency"] = 0.0
            stats["success_rate"] = 0.0

        return stats

    def reset_stats(self):
        """重置性能统计"""
        self._performance_stats: Dict[str, float | int] = {
            "total_requests": 0,
            "failed_requests": 0,
            "total_latency": 0.0,
            "min_latency": float("inf"),
            "max_latency": 0.0,
        }
        self.error_count = 0
        self.success_count = 0

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态信息
        """
        return {
            "provider": self.__class__.__name__,
            "initialized": self.initialized,
            "status": self.status,
            "error_count": self.error_count,
            "success_count": self.success_count,
            "performance": self.get_performance_stats(),
        }

