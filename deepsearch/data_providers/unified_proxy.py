"""
统一数据访问代理

作为所有数据访问的统一入口，提供监控、路由和容错功能。
"""
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List, Callable
from functools import wraps

from loguru import logger

from deepsearch.observability.monitoring.data_source_monitor import (
    DataSourceMonitor,
    DataSourceType,
    DataAccessType,
    get_monitor
)


class DataAccessProxy:
    """数据访问代理"""
    
    def __init__(self):
        """初始化代理"""
        self.monitor = get_monitor()
        self.providers = {}
        self.initialized = False
        
        # 熔断器配置
        self.circuit_breaker_threshold = 5  # 连续失败次数阈值
        self.circuit_breaker_timeout = 60  # 熔断恢复时间（秒）
        self.circuit_breaker_status = {}  # 数据源熔断状态
        
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1.0  # 重试延迟（秒）
        
    async def initialize(self):
        """初始化代理"""
        if self.initialized:
            return
        
        logger.info("初始化统一数据访问代理...")
        
        # 初始化各数据提供者
        await self._init_providers()
        
        # 初始化熔断器状态
        for source in DataSourceType:
            self.circuit_breaker_status[source] = {
                "is_open": False,
                "failure_count": 0,
                "last_failure_time": 0
            }
        
        self.initialized = True
        logger.info("统一数据访问代理初始化完成")
    
    async def _init_providers(self):
        """初始化数据提供者"""
        # 初始化AKShare Direct
        try:
            from deepsearch.data_providers.implementations.akshare.akshare_direct import AKShareDirectProvider
            provider = AKShareDirectProvider()
            await provider.initialize()
            self.providers[DataSourceType.AKSHARE] = provider
            logger.info("AKShare数据提供者初始化成功")
        except Exception as e:
            logger.error(f"AKShare数据提供者初始化失败: {e}")
        
        # 初始化QMT（如果可用）
        try:
            from deepsearch.core.runtime.context import get_context
            context = get_context()
            if hasattr(context, 'get_component_manager'):
                manager = context.get_component_manager()
                qmt_component = manager.get_component('qmt_gateway')
                if qmt_component:
                    self.providers[DataSourceType.QMT] = qmt_component
                    logger.info("QMT数据提供者初始化成功")
        except Exception as e:
            logger.debug(f"QMT数据提供者不可用: {e}")
    
    @asynccontextmanager
    async def _monitor_access(
        self,
        source: DataSourceType,
        access_type: DataAccessType,
        symbol: Optional[str] = None,
        module: Optional[str] = None
    ):
        """
        监控数据访问的上下文管理器
        
        Args:
            source: 数据源类型
            access_type: 访问类型
            symbol: 股票代码
            module: 调用模块
        """
        start_time = time.time()
        success = False
        error_message = None
        data_size = 0
        
        try:
            yield {
                "source": source,
                "access_type": access_type,
                "symbol": symbol
            }
            success = True
        except Exception as e:
            error_message = str(e)
            raise
        finally:
            # 计算延迟
            latency_ms = (time.time() - start_time) * 1000
            
            # 记录访问
            self.monitor.record_access(
                source=source,
                access_type=access_type,
                success=success,
                latency_ms=latency_ms,
                symbol=symbol,
                module=module,
                error_message=error_message,
                data_size=data_size
            )
            
            # 更新熔断器状态
            self._update_circuit_breaker(source, success)
    
    def _update_circuit_breaker(self, source: DataSourceType, success: bool):
        """更新熔断器状态"""
        breaker = self.circuit_breaker_status[source]
        
        if success:
            # 成功，重置失败计数
            breaker["failure_count"] = 0
            breaker["is_open"] = False
        else:
            # 失败，增加计数
            breaker["failure_count"] += 1
            breaker["last_failure_time"] = time.time()
            
            # 检查是否需要熔断
            if breaker["failure_count"] >= self.circuit_breaker_threshold:
                breaker["is_open"] = True
                logger.warning(f"数据源 {source.value} 触发熔断器，将在 {self.circuit_breaker_timeout} 秒后恢复")
    
    def _is_circuit_open(self, source: DataSourceType) -> bool:
        """检查熔断器是否打开"""
        breaker = self.circuit_breaker_status[source]
        
        if not breaker["is_open"]:
            return False
        
        # 检查是否到了恢复时间
        if time.time() - breaker["last_failure_time"] > self.circuit_breaker_timeout:
            breaker["is_open"] = False
            breaker["failure_count"] = 0
            logger.info(f"数据源 {source.value} 熔断器已恢复")
            return False
        
        return True
    
    async def get_realtime_quote(
        self,
        symbol: str,
        prefer_source: Optional[DataSourceType] = None,
        module: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取实时行情（带监控和容错）
        
        Args:
            symbol: 股票代码
            prefer_source: 优先使用的数据源
            module: 调用模块
            
        Returns:
            实时行情数据
        """
        # 确定数据源优先级
        sources = self._get_source_priority(DataAccessType.REALTIME_QUOTE, prefer_source)
        
        last_error = None
        for source in sources:
            # 检查熔断器
            if self._is_circuit_open(source):
                logger.debug(f"数据源 {source.value} 处于熔断状态，跳过")
                continue
            
            # 检查提供者是否存在
            provider = self.providers.get(source)
            if not provider:
                continue
            
            try:
                async with self._monitor_access(
                    source=source,
                    access_type=DataAccessType.REALTIME_QUOTE,
                    symbol=symbol,
                    module=module
                ):
                    # 调用实际的数据提供者
                    if source == DataSourceType.AKSHARE:
                        result = await provider.get_realtime_quote(symbol)
                    elif source == DataSourceType.QMT:
                        result = provider.get_latest_tick(symbol)
                        if result:
                            # 转换QMT格式到统一格式
                            result = {
                                "symbol": symbol,
                                "current": result.get("last_price", 0),
                                "prev_close": result.get("pre_close", 0),
                                "open": result.get("open", 0),
                                "high": result.get("high", 0),
                                "low": result.get("low", 0),
                                "volume": result.get("volume", 0),
                                "amount": result.get("amount", 0),
                                "source": "qmt"
                            }
                    else:
                        continue
                    
                    if result and not result.get("error"):
                        result["source"] = source.value
                        return result
                        
            except Exception as e:
                last_error = e
                logger.warning(f"从 {source.value} 获取数据失败: {e}")
                continue
        
        # 所有数据源都失败
        error_msg = f"所有数据源获取失败: {last_error}" if last_error else "没有可用的数据源"
        raise Exception(error_msg)
    
    async def get_historical_kline(
        self,
        symbol: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "",
        prefer_source: Optional[DataSourceType] = None,
        module: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取历史K线数据（带监控和容错）
        
        Args:
            symbol: 股票代码
            period: 周期
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型
            prefer_source: 优先数据源
            module: 调用模块
            
        Returns:
            历史K线数据
        """
        sources = self._get_source_priority(DataAccessType.HISTORICAL_KLINE, prefer_source)
        
        last_error = None
        for source in sources:
            if self._is_circuit_open(source):
                continue
            
            provider = self.providers.get(source)
            if not provider:
                continue
            
            try:
                async with self._monitor_access(
                    source=source,
                    access_type=DataAccessType.HISTORICAL_KLINE,
                    symbol=symbol,
                    module=module
                ):
                    if source == DataSourceType.AKSHARE:
                        result = await provider.get_stock_hist(
                            symbol=symbol,
                            period=period,
                            start_date=start_date,
                            end_date=end_date,
                            adjust=adjust
                        )
                    else:
                        continue
                    
                    if result and not result.get("error"):
                        result["source"] = source.value
                        return result
                        
            except Exception as e:
                last_error = e
                logger.warning(f"从 {source.value} 获取历史数据失败: {e}")
                continue
        
        error_msg = f"所有数据源获取失败: {last_error}" if last_error else "没有可用的数据源"
        raise Exception(error_msg)
    
    async def get_stock_list(
        self,
        prefer_source: Optional[DataSourceType] = None,
        module: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        获取股票列表（带监控和容错）
        
        Args:
            prefer_source: 优先数据源
            module: 调用模块
            
        Returns:
            股票列表
        """
        sources = self._get_source_priority(DataAccessType.STOCK_LIST, prefer_source)
        
        last_error = None
        for source in sources:
            if self._is_circuit_open(source):
                continue
            
            provider = self.providers.get(source)
            if not provider:
                continue
            
            try:
                async with self._monitor_access(
                    source=source,
                    access_type=DataAccessType.STOCK_LIST,
                    module=module
                ):
                    if source == DataSourceType.AKSHARE:
                        result = await provider.fetch_stock_list()
                    else:
                        continue
                    
                    if result:
                        return result
                        
            except Exception as e:
                last_error = e
                logger.warning(f"从 {source.value} 获取股票列表失败: {e}")
                continue
        
        # 返回默认列表
        logger.warning("所有数据源失败，返回默认股票列表")
        return [
            {'代码': '000001', '名称': '平安银行'},
            {'代码': '000002', '名称': '万科A'},
            {'代码': '600000', '名称': '浦发银行'},
            {'代码': '600036', '名称': '招商银行'},
        ]
    
    def _get_source_priority(
        self,
        access_type: DataAccessType,
        prefer_source: Optional[DataSourceType] = None
    ) -> List[DataSourceType]:
        """
        获取数据源优先级列表
        
        Args:
            access_type: 访问类型
            prefer_source: 优先数据源
            
        Returns:
            排序后的数据源列表
        """
        # 基础优先级
        priority_map = {
            DataAccessType.REALTIME_QUOTE: [
                DataSourceType.QMT,
                DataSourceType.AKSHARE,
                DataSourceType.CLOUDFLARE,
            ],
            DataAccessType.HISTORICAL_KLINE: [
                DataSourceType.AKSHARE,
                DataSourceType.QMT,
                DataSourceType.DATABASE,
            ],
            DataAccessType.STOCK_LIST: [
                DataSourceType.AKSHARE,
                DataSourceType.DATABASE,
            ],
            DataAccessType.ORDERBOOK: [
                DataSourceType.QMT,
            ],
            DataAccessType.TICK_DATA: [
                DataSourceType.QMT,
            ],
        }
        
        sources = priority_map.get(access_type, list(DataSourceType))
        
        # 如果指定了优先数据源，调整顺序
        if prefer_source and prefer_source in sources:
            sources.remove(prefer_source)
            sources.insert(0, prefer_source)
        
        # 根据监控数据动态调整（获取推荐）
        recommended = self.monitor.get_recommendation(
            access_type=access_type,
            require_realtime=(access_type == DataAccessType.REALTIME_QUOTE)
        )
        if recommended and recommended in sources and recommended != sources[0]:
            sources.remove(recommended)
            sources.insert(0, recommended)
            logger.debug(f"根据监控数据，推荐使用 {recommended.value} 作为首选数据源")
        
        return sources
    
    def get_monitor_stats(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        return self.monitor.export_metrics()
    
    def reset_circuit_breaker(self, source: Optional[DataSourceType] = None):
        """
        重置熔断器
        
        Args:
            source: 数据源，如果为None则重置所有
        """
        if source:
            self.circuit_breaker_status[source] = {
                "is_open": False,
                "failure_count": 0,
                "last_failure_time": 0
            }
            logger.info(f"重置数据源 {source.value} 的熔断器")
        else:
            for s in DataSourceType:
                self.circuit_breaker_status[s] = {
                    "is_open": False,
                    "failure_count": 0,
                    "last_failure_time": 0
                }
            logger.info("重置所有数据源的熔断器")


# 全局代理实例
_proxy_instance = None


async def get_data_proxy() -> DataAccessProxy:
    """获取全局数据访问代理实例"""
    global _proxy_instance
    if _proxy_instance is None:
        _proxy_instance = DataAccessProxy()
        await _proxy_instance.initialize()
    return _proxy_instance


def monitor_access(
    source: DataSourceType,
    access_type: DataAccessType,
    module: Optional[str] = None
):
    """
    监控装饰器，用于监控同步函数的数据访问
    
    Args:
        source: 数据源类型
        access_type: 访问类型
        module: 调用模块
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            error_message = None
            symbol = kwargs.get('symbol') or (args[0] if args else None)
            
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                error_message = str(e)
                raise
            finally:
                latency_ms = (time.time() - start_time) * 1000
                monitor = get_monitor()
                monitor.record_access(
                    source=source,
                    access_type=access_type,
                    success=success,
                    latency_ms=latency_ms,
                    symbol=symbol if isinstance(symbol, str) else None,
                    module=module or func.__module__,
                    error_message=error_message
                )
        return wrapper
    return decorator


def async_monitor_access(
    source: DataSourceType,
    access_type: DataAccessType,
    module: Optional[str] = None
):
    """
    监控装饰器，用于监控异步函数的数据访问
    
    Args:
        source: 数据源类型
        access_type: 访问类型
        module: 调用模块
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            error_message = None
            symbol = kwargs.get('symbol') or (args[0] if args else None)
            
            try:
                result = await func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                error_message = str(e)
                raise
            finally:
                latency_ms = (time.time() - start_time) * 1000
                monitor = get_monitor()
                monitor.record_access(
                    source=source,
                    access_type=access_type,
                    success=success,
                    latency_ms=latency_ms,
                    symbol=symbol if isinstance(symbol, str) else None,
                    module=module or func.__module__,
                    error_message=error_message
                )
        return wrapper
    return decorator