"""
统一数据源管理器

负责管理多个数据源，自动切换和容错
"""
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional

from loguru import logger


class DataSourceType(Enum):
    """数据源类型"""
    QMT = "qmt"  # QMT本地数据
    CLOUDFLARE = "cloudflare"  # Cloudflare Worker代理
    DIRECT_API = "direct_api"  # 直连API（东方财富/新浪）
    AKSHARE = "akshare"  # AkShare库


@dataclass
class DataSourceStatus:
    """数据源状态"""
    source_type: DataSourceType
    available: bool
    last_check: float
    error_count: int
    avg_latency: float  # 平均延迟（毫秒）
    success_rate: float  # 成功率
    last_error: Optional[str] = None


class UnifiedDataManager:
    """统一数据源管理器"""

    def __init__(self):
        """初始化管理器"""
        # 数据源状态
        self.sources: Dict[DataSourceType, DataSourceStatus] = {}

        # 数据提供者实例
        self.providers: Dict[DataSourceType, Any] = {}

        # 配置
        self.health_check_interval = 30  # 健康检查间隔（秒）
        self.max_retries = 3  # 最大重试次数
        self.timeout = 10  # 请求超时时间（秒）

        # 统计信息
        self.stats = {
            "total_requests": 0,
            "success_count": 0,
            "error_count": 0,
            "source_usage": {}  # 各数据源使用次数
        }

        # 健康检查任务
        self._health_check_task = None

    async def initialize(self):
        """初始化数据源"""
        logger.info("初始化统一数据源管理器...")

        # 初始化数据源状态
        for source_type in DataSourceType:
            self.sources[source_type] = DataSourceStatus(
                source_type=source_type,
                available=True,
                last_check=0,
                error_count=0,
                avg_latency=0,
                success_rate=1.0
            )

        # 初始化数据提供者
        await self._init_providers()

        # 启动健康检查
        self._health_check_task = asyncio.create_task(self._health_check_loop())

        logger.info("统一数据源管理器初始化完成")

    async def _init_providers(self):
        """初始化数据提供者"""
        try:
            # 初始化Cloudflare Worker提供者
            from deepsearch.data_providers.cloudflare import ProxyDataProvider
            self.providers[DataSourceType.CLOUDFLARE] = ProxyDataProvider()
            await self.providers[DataSourceType.CLOUDFLARE].initialize()

        except Exception as e:
            logger.error(f"初始化Cloudflare提供者失败: {e}")
            self.sources[DataSourceType.CLOUDFLARE].available = False

        try:
            # 初始化QMT提供者（如果存在）
            from deepsearch.datafeed.qmt.provider import QMTDataProvider
            self.providers[DataSourceType.QMT] = QMTDataProvider()
            await self.providers[DataSourceType.QMT].initialize()

        except ImportError:
            logger.warning("QMT数据提供者未实现")
            self.sources[DataSourceType.QMT].available = False
        except Exception as e:
            logger.error(f"初始化QMT提供者失败: {e}")
            self.sources[DataSourceType.QMT].available = False

    async def get_stock_hist(
            self,
            symbol: str,
            period: str = "daily",
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            adjust: str = "",
            preferred_source: Optional[DataSourceType] = None
    ) -> Dict[str, Any]:
        """
        获取股票历史数据
        
        Args:
            symbol: 股票代码
            period: 周期
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型
            preferred_source: 首选数据源
            
        Returns:
            历史数据字典，包含source字段标识数据来源
        """
        # 获取可用数据源列表
        sources = self._get_available_sources(preferred_source)

        for source_type in sources:
            try:
                provider = self.providers.get(source_type)
                if not provider:
                    continue

                # 记录开始时间
                start_time = time.time()

                # 调用对应的数据提供者
                result = await asyncio.wait_for(
                    provider.get_stock_hist(
                        symbol, period, start_date, end_date, adjust
                    ),
                    timeout=self.timeout
                )

                # 计算延迟
                latency = (time.time() - start_time) * 1000

                # 更新统计
                self._update_stats(source_type, True, latency)

                # 添加数据源标识
                result["source"] = source_type.value
                result["latency"] = latency

                return result

            except asyncio.TimeoutError:
                logger.warning(f"{source_type.value} 获取历史数据超时")
                self._update_stats(source_type, False, self.timeout * 1000)

            except Exception as e:
                logger.error(f"{source_type.value} 获取历史数据失败: {e}")
                self._update_stats(source_type, False, 0)

        # 所有数据源都失败
        return {
            "data": [],
            "error": "所有数据源都不可用",
            "source": "none"
        }

    async def get_realtime_quote(
            self,
            symbol: str,
            preferred_source: Optional[DataSourceType] = None
    ) -> Dict[str, Any]:
        """
        获取实时行情
        
        Args:
            symbol: 股票代码
            preferred_source: 首选数据源
            
        Returns:
            实时行情数据
        """
        sources = self._get_available_sources(preferred_source)

        for source_type in sources:
            try:
                provider = self.providers.get(source_type)
                if not provider:
                    continue

                start_time = time.time()

                result = await asyncio.wait_for(
                    provider.get_realtime_quote(symbol),
                    timeout=self.timeout / 2  # 实时数据超时时间更短
                )

                latency = (time.time() - start_time) * 1000
                self._update_stats(source_type, True, latency)

                result["source"] = source_type.value
                result["latency"] = latency

                return result

            except Exception as e:
                logger.debug(f"{source_type.value} 获取实时行情失败: {e}")
                self._update_stats(source_type, False, 0)

        return {
            "error": "无法获取实时行情",
            "source": "none"
        }

    async def get_realtime_snapshot(
            self,
            symbol: str,
            preferred_source: Optional[DataSourceType] = None
    ) -> Dict[str, Any]:
        """
        获取实时快照（兼容性方法，内部调用 get_realtime_quote）
        
        Args:
            symbol: 股票代码
            preferred_source: 首选数据源
            
        Returns:
            实时行情数据
        """
        return await self.get_realtime_quote(symbol, preferred_source)

    async def fetch_stock_info(
            self,
            symbol: str,
            preferred_source: Optional[DataSourceType] = None
    ) -> Dict[str, Any]:
        """
        获取股票信息
        
        Args:
            symbol: 股票代码
            preferred_source: 首选数据源
            
        Returns:
            股票信息
        """
        sources = self._get_available_sources(preferred_source)

        for source_type in sources:
            try:
                provider = self.providers.get(source_type)
                if not provider or not hasattr(provider, 'fetch_stock_info'):
                    continue

                start_time = time.time()

                result = await asyncio.wait_for(
                    provider.fetch_stock_info(symbol),
                    timeout=self.timeout
                )

                latency = (time.time() - start_time) * 1000
                self._update_stats(source_type, True, latency)

                result["source"] = source_type.value
                result["latency"] = latency

                # 如果获取到有效的股票名称，返回
                if result.get("name") and not result["name"].startswith("股票"):
                    return result

            except Exception as e:
                logger.debug(f"{source_type.value} 获取股票信息失败: {e}")
                self._update_stats(source_type, False, 0)

        return {
            "symbol": symbol,
            "name": f"股票{symbol}",
            "error": "无法获取股票信息",
            "source": "none"
        }

    def _get_available_sources(
            self,
            preferred: Optional[DataSourceType] = None
    ) -> List[DataSourceType]:
        """
        获取可用数据源列表（按优先级排序）
        
        Args:
            preferred: 首选数据源
            
        Returns:
            数据源列表
        """
        sources = []

        # 如果指定了首选源且可用，优先使用
        if preferred and self.sources[preferred].available:
            sources.append(preferred)

        # QMT 总是优先（如果可用且不是首选源）
        if DataSourceType.QMT != preferred and self.sources[DataSourceType.QMT].available:
            sources.insert(0 if not preferred else 1, DataSourceType.QMT)

        # 定义数据源优先级
        priority_order = {
            DataSourceType.QMT: 1,
            DataSourceType.CLOUDFLARE: 2,
            DataSourceType.AKSHARE: 3,
            DataSourceType.DIRECT_API: 4
        }

        # 按优先级排序其他可用源
        available_sources = [
            s.source_type
            for s in self.sources.values()
            if s.available and s.source_type not in sources
        ]
        available_sources.sort(key=lambda x: (priority_order.get(x, 999), self.sources[x].avg_latency))

        sources.extend(available_sources)

        return sources

    def _update_stats(self, source_type: DataSourceType, success: bool, latency: float):
        """
        更新统计信息
        
        Args:
            source_type: 数据源类型
            success: 是否成功
            latency: 延迟（毫秒）
        """
        self.stats["total_requests"] += 1

        if success:
            self.stats["success_count"] += 1

            # 更新数据源统计
            status = self.sources[source_type]
            status.error_count = 0

            # 更新平均延迟（指数移动平均）
            if status.avg_latency == 0:
                status.avg_latency = latency
            else:
                status.avg_latency = status.avg_latency * 0.9 + latency * 0.1

            # 更新成功率
            if source_type not in self.stats["source_usage"]:
                self.stats["source_usage"][source_type] = {"success": 0, "total": 0}

            self.stats["source_usage"][source_type]["success"] += 1
            self.stats["source_usage"][source_type]["total"] += 1

            usage = self.stats["source_usage"][source_type]
            status.success_rate = usage["success"] / usage["total"]

        else:
            self.stats["error_count"] += 1

            # 更新错误计数
            status = self.sources[source_type]
            status.error_count += 1

            # 如果连续失败超过阈值，标记为不可用
            if status.error_count >= 3:
                status.available = False
                logger.warning(f"{source_type.value} 数据源已标记为不可用")

    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._check_all_sources()
            except Exception as e:
                logger.error(f"健康检查失败: {e}")

    async def _check_all_sources(self):
        """检查所有数据源健康状态"""
        for source_type, status in self.sources.items():
            try:
                provider = self.providers.get(source_type)
                if not provider:
                    continue

                # 简单的健康检查：尝试获取一个常见股票的信息
                start_time = time.time()

                if hasattr(provider, 'get_realtime_quote'):
                    await asyncio.wait_for(
                        provider.get_realtime_quote("000001"),
                        timeout=5
                    )

                    latency = (time.time() - start_time) * 1000

                    # 恢复可用状态
                    if not status.available:
                        logger.info(f"{source_type.value} 数据源已恢复")

                    status.available = True
                    status.error_count = 0
                    status.last_check = time.time()

                    # 更新延迟
                    if status.avg_latency == 0:
                        status.avg_latency = latency
                    else:
                        status.avg_latency = status.avg_latency * 0.9 + latency * 0.1

            except Exception as e:
                logger.debug(f"{source_type.value} 健康检查失败: {e}")
                status.last_error = str(e)
                status.last_check = time.time()

    def get_status_report(self) -> Dict[str, Any]:
        """
        获取状态报告
        
        Returns:
            状态报告字典
        """
        return {
            "sources": {
                s.source_type.value: {
                    "available": s.available,
                    "avg_latency": round(s.avg_latency, 2),
                    "success_rate": round(s.success_rate * 100, 2),
                    "error_count": s.error_count,
                    "last_check": s.last_check,
                    "last_error": s.last_error
                }
                for s in self.sources.values()
            },
            "stats": {
                "total_requests": self.stats["total_requests"],
                "success_count": self.stats["success_count"],
                "error_count": self.stats["error_count"],
                "success_rate": round(
                    self.stats["success_count"] / self.stats["total_requests"] * 100
                    if self.stats["total_requests"] > 0 else 0,
                    2
                )
            }
        }

    async def close(self):
        """关闭管理器"""
        if self._health_check_task:
            self._health_check_task.cancel()

        # 关闭所有提供者
        for provider in self.providers.values():
            if hasattr(provider, 'close'):
                await provider.close()


# 全局实例
_manager_instance: Optional[UnifiedDataManager] = None


async def get_unified_data_manager() -> UnifiedDataManager:
    """获取全局统一数据管理器实例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = UnifiedDataManager()
        await _manager_instance.initialize()
    return _manager_instance
