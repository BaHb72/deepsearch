"""
统一数据访问代理

作为所有数据访问的统一入口，提供监控、路由和容错功能。
"""

import asyncio
import inspect
import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, cast

from core.infrastructure.providers.managers.data_source_manager import (
    StockListFetchResult,
    build_stock_list_result,
)
from core.observability.monitoring.data_source_monitor import get_monitor
from core.ports.data_sources import DataAccessType, DataSourceType
from loguru import logger

# 数据源名称到枚举的映射
_SOURCE_NAME_MAP: Dict[str, DataSourceType] = {
    "miniqmt": DataSourceType.QMT,
    "qmt": DataSourceType.QMT,
    "amazingdata": DataSourceType.AMAZINGDATA,
    "akshare": DataSourceType.AKSHARE,
}


class DataAccessProxy:
    """数据访问代理"""

    def __init__(self):
        """初始化代理"""
        self.monitor = get_monitor()
        self.providers: Dict[DataSourceType, Any] = {}
        self.initialized = False

        # 熔断器配置
        self.circuit_breaker_threshold = 5  # 连续失败次数阈值
        self.circuit_breaker_timeout = 60  # 熔断恢复时间（秒）
        self.circuit_breaker_status: Dict[DataSourceType, Dict[str, Any]] = {}

        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1.0  # 重试延迟（秒）

        # 从配置加载 fallback_order
        self._fallback_order: List[DataSourceType] = self._load_fallback_order()

        # ProviderContainer 引用（用于动态获取 AmazingData）
        self._provider_container: Optional[Any] = None

    def _load_fallback_order(self) -> List[DataSourceType]:
        """从配置文件加载 fallback_order

        Returns:
            数据源优先级列表
        """
        try:
            from core.config import get_config

            app_config = get_config()
            order = app_config.data_sources.fallback_order  # type: ignore[union-attr]
            result = []
            for name in order:
                if name in _SOURCE_NAME_MAP:
                    source_type = _SOURCE_NAME_MAP[name]
                    if source_type not in result:  # 避免重复
                        result.append(source_type)
            if result:
                logger.info(f"从配置加载 fallback_order: {[s.value for s in result]}")
                return result
        except Exception as e:
            logger.debug(f"从配置加载 fallback_order 失败，使用默认值: {e}")

        # 默认优先级
        default = [DataSourceType.QMT, DataSourceType.AMAZINGDATA, DataSourceType.AKSHARE]
        logger.info(f"使用默认 fallback_order: {[s.value for s in default]}")
        return default

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
                "last_failure_time": 0,
            }

        self.initialized = True
        logger.info("统一数据访问代理初始化完成")

    async def _init_providers(self):
        """初始化数据提供者"""
        # 初始化AKShare Direct
        try:
            from core.infrastructure.providers.implementations.akshare.akshare_direct import (
                AKShareDirectProvider,
            )

            provider = AKShareDirectProvider()
            await provider.initialize()
            self.providers[DataSourceType.AKSHARE] = provider
            logger.info("AKShare数据提供者初始化成功")
        except Exception as e:
            logger.error(f"AKShare数据提供者初始化失败: {e}")

        # 初始化QMT（如果可用）
        try:
            from core.core.runtime.context import get_context

            context = get_context()
            if hasattr(context, "get_component_manager"):
                manager = context.get_component_manager()
                qmt_component = manager.get_component("qmt_gateway")
                if qmt_component:
                    self.providers[DataSourceType.QMT] = qmt_component
                    logger.info("QMT数据提供者初始化成功")
        except Exception as e:
            logger.debug(f"QMT数据提供者不可用: {e}")

        # 初始化 AmazingData（通过 ProviderContainer，如果已注册）
        await self._try_init_amazingdata()

    async def _try_init_amazingdata(self) -> bool:
        """尝试初始化 AmazingData 数据提供者

        AmazingData 通过 Dask Worker 异步初始化，可能在代理初始化时还不可用。
        此方法会尝试从 ProviderContainer 获取已注册的 AmazingData 代理。

        Returns:
            是否成功初始化
        """
        try:
            from core.infrastructure.providers.container import ProviderContainer

            # 尝试从应用上下文获取 ProviderContainer
            try:
                from core.core.runtime.context import get_context

                context = get_context()
                if context.has_service("provider_container"):
                    self._provider_container = context.get_service("provider_container")
            except Exception:
                pass

            # 如果有 ProviderContainer，尝试获取 AmazingData
            if self._provider_container and isinstance(self._provider_container, ProviderContainer):
                if self._provider_container.has("amazingdata"):
                    amazingdata_provider = await self._provider_container.get("amazingdata")
                    if amazingdata_provider:
                        self.providers[DataSourceType.AMAZINGDATA] = amazingdata_provider
                        logger.info("AmazingData 数据提供者初始化成功（通过 ProviderContainer）")
                        return True

            logger.debug("AmazingData 数据提供者暂不可用（将在请求时动态检查）")
            return False

        except Exception as e:
            logger.debug(f"AmazingData 数据提供者初始化跳过: {e}")
            return False

    async def _get_amazingdata_provider(self) -> Optional[Any]:
        """动态获取 AmazingData 数据提供者

        在每次请求时检查 AmazingData 是否可用（可能在代理初始化后才注册）。

        Returns:
            AmazingData 数据提供者实例，或 None
        """
        # 如果已经在 providers 中，直接返回
        if DataSourceType.AMAZINGDATA in self.providers:
            return self.providers[DataSourceType.AMAZINGDATA]

        # 尝试从 ProviderContainer 获取
        try:
            from core.infrastructure.providers.container import ProviderContainer

            # 如果没有缓存 ProviderContainer，尝试获取
            if self._provider_container is None:
                try:
                    from core.core.runtime.context import get_context

                    context = get_context()
                    if context.has_service("provider_container"):
                        self._provider_container = context.get_service("provider_container")
                except Exception:
                    pass

            if self._provider_container and isinstance(self._provider_container, ProviderContainer):
                if self._provider_container.has("amazingdata"):
                    amazingdata_provider = await self._provider_container.get("amazingdata")
                    if amazingdata_provider:
                        self.providers[DataSourceType.AMAZINGDATA] = amazingdata_provider
                        logger.info("AmazingData 数据提供者已动态注册")
                        return amazingdata_provider

        except Exception as e:
            logger.debug(f"动态获取 AmazingData 失败: {e}")

        return None

    def set_provider_container(self, container: Any) -> None:
        """设置 ProviderContainer 引用

        允许外部（如 FastAPI lifespan）注入 ProviderContainer。

        Args:
            container: ProviderContainer 实例
        """
        self._provider_container = container
        logger.debug("ProviderContainer 已注入到 DataAccessProxy")

    @asynccontextmanager
    async def _monitor_access(
        self,
        source: DataSourceType,
        access_type: DataAccessType,
        symbol: Optional[str] = None,
        module: Optional[str] = None,
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
            yield {"source": source, "access_type": access_type, "symbol": symbol}
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
                data_size=data_size,
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
                logger.warning(
                    f"数据源 {source.value} 触发熔断器，将在 {self.circuit_breaker_timeout} 秒后恢复"
                )

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

    def _get_source_priority(
        self,
        access_type: DataAccessType,
        prefer_source: Optional[DataSourceType] = None,
    ) -> List[DataSourceType]:
        """
        获取数据源优先级列表

        基于配置文件中的 fallback_order，并根据访问类型做微调。

        Args:
            access_type: 访问类型
            prefer_source: 优先使用的数据源

        Returns:
            数据源优先级列表
        """
        # 使用配置文件中的 fallback_order 作为基础优先级
        priority = self._fallback_order.copy()

        # 根据访问类型可以做微调（但仍然尊重配置顺序）
        # 注意：如果配置已经指定了顺序，这里只是确保相关数据源在列表中
        if access_type == DataAccessType.REALTIME_QUOTE:
            # 实时行情：确保 QMT 和 AmazingData 在列表中靠前
            # 配置的 fallback_order 已经考虑了这一点
            pass
        elif access_type == DataAccessType.HISTORICAL_KLINE:
            # 历史 K 线：如果需要特殊处理可以在这里调整
            # 但配置的 fallback_order 应该已经设置好了优先级
            pass
        elif access_type == DataAccessType.STOCK_LIST:
            # 股票列表：使用配置的优先级
            pass

        # 如果指定了优先数据源，将其移到最前面
        if prefer_source and prefer_source in priority:
            priority.remove(prefer_source)
            priority.insert(0, prefer_source)

        return priority

    def reset_circuit_breaker(
        self,
        source: Optional[DataSourceType] = None,
    ) -> None:
        """
        重置熔断器状态

        Args:
            source: 指定数据源，None表示重置所有
        """
        if source:
            if source in self.circuit_breaker_status:
                self.circuit_breaker_status[source] = {
                    "is_open": False,
                    "failure_count": 0,
                    "last_failure_time": 0,
                }
                logger.info(f"数据源 {source.value} 熔断器已重置")
        else:
            for src in DataSourceType:
                self.circuit_breaker_status[src] = {
                    "is_open": False,
                    "failure_count": 0,
                    "last_failure_time": 0,
                }
            logger.info("所有数据源熔断器已重置")

    async def get_realtime_quote(
        self,
        symbol: str,
        prefer_source: Optional[DataSourceType] = None,
        module: Optional[str] = None,
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
                    module=module,
                ):
                    # 调用实际的数据提供者
                    if source == DataSourceType.AKSHARE:
                        result = await provider.get_realtime_quote(symbol)
                    elif source == DataSourceType.QMT:
                        result = provider.get_latest_tick(symbol)
                        if result is not None and not result.empty:
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
                                "source": "qmt",
                            }
                    else:
                        continue

                    if result is not None and not result.get("error"):
                        result["source"] = source.value
                        return cast(Dict[str, Any], result)

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
        module: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取历史K线数据（带监控和容错）

        Args:
            symbol: 股票代码
            period: 周期（daily, 1d, 5m 等）
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型（none, qfq, hfq）
            prefer_source: 优先数据源
            module: 调用模块

        Returns:
            历史K线数据
        """
        sources = self._get_source_priority(DataAccessType.HISTORICAL_KLINE, prefer_source)

        last_error = None
        for source in sources:
            if self._is_circuit_open(source):
                logger.debug(f"数据源 {source.value} 处于熔断状态，跳过")
                continue

            # 动态获取 provider（支持 AmazingData 延迟注册）
            provider = await self._get_provider_for_source(source)
            if not provider:
                logger.debug(f"数据源 {source.value} 不可用，跳过")
                continue

            try:
                async with self._monitor_access(
                    source=source,
                    access_type=DataAccessType.HISTORICAL_KLINE,
                    symbol=symbol,
                    module=module,
                ):
                    result = await self._fetch_kline_from_source(
                        source=source,
                        provider=provider,
                        symbol=symbol,
                        period=period,
                        start_date=start_date,
                        end_date=end_date,
                        adjust=adjust,
                    )

                    if result is not None and not result.get("error"):
                        result["source"] = source.value
                        logger.debug(f"从 {source.value} 成功获取 {symbol} K线数据")
                        return cast(Dict[str, Any], result)

            except Exception as e:
                last_error = e
                logger.warning(f"从 {source.value} 获取历史数据失败: {e}")
                continue

        error_msg = f"所有数据源获取失败: {last_error}" if last_error else "没有可用的数据源"
        raise Exception(error_msg)

    async def _get_provider_for_source(self, source: DataSourceType) -> Optional[Any]:
        """获取指定数据源的 Provider

        支持动态获取 AmazingData（可能在代理初始化后才注册）。

        Args:
            source: 数据源类型

        Returns:
            Provider 实例，或 None
        """
        # 先从已注册的 providers 中获取
        provider = self.providers.get(source)
        if provider:
            return provider

        # 如果是 AmazingData，尝试动态获取
        if source == DataSourceType.AMAZINGDATA:
            return await self._get_amazingdata_provider()

        return None

    async def _fetch_kline_from_source(
        self,
        source: DataSourceType,
        provider: Any,
        symbol: str,
        period: str,
        start_date: Optional[str],
        end_date: Optional[str],
        adjust: str,
    ) -> Optional[Dict[str, Any]]:
        """从指定数据源获取 K 线数据

        Args:
            source: 数据源类型
            provider: 数据提供者实例
            symbol: 股票代码
            period: 周期
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型

        Returns:
            K 线数据字典，或 None
        """
        if source == DataSourceType.AKSHARE:
            return await provider.get_stock_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )

        elif source == DataSourceType.AMAZINGDATA:
            # 调用 AmazingData 的 K 线接口
            kline_data = await self._fetch_kline_from_amazingdata(
                provider=provider,
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            if kline_data:
                return {"data": kline_data, "source": "amazingdata"}
            return None

        elif source == DataSourceType.QMT:
            # 调用 QMT 的 K 线接口
            kline_data = await self._fetch_kline_from_qmt(
                provider=provider,
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            if kline_data:
                return {"data": kline_data, "source": "qmt"}
            return None

        else:
            logger.debug(f"数据源 {source.value} 不支持 K 线查询")
            return None

    async def _fetch_kline_from_amazingdata(
        self,
        provider: Any,
        symbol: str,
        period: str,
        start_date: Optional[str],
        end_date: Optional[str],
        adjust: str,
    ) -> Optional[list]:
        """从 AmazingData 获取 K 线数据

        Args:
            provider: AmazingData Provider 实例
            symbol: 股票代码
            period: 周期
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型

        Returns:
            K 线数据列表，或 None
        """
        try:
            # 转换周期格式（统一到 AmazingData 格式）
            period_map = {
                "daily": "1d",
                "day": "1d",
                "1d": "1d",
                "5m": "5m",
                "15m": "15m",
                "30m": "30m",
                "60m": "60m",
                "1h": "60m",
            }
            ad_period = period_map.get(period, period)

            # 尝试调用 get_kline_data 方法
            get_kline_data = getattr(provider, "get_kline_data", None)
            if callable(get_kline_data):
                result = await get_kline_data(
                    symbol=symbol,
                    period=ad_period,
                    start_date=start_date,
                    end_date=end_date,
                )
                return result

            # 备用：尝试 get_kline 方法
            get_kline = getattr(provider, "get_kline", None)
            if callable(get_kline):
                df = await get_kline(
                    symbol=symbol,
                    period=ad_period,
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust,
                )
                if df is not None and not df.empty:
                    return df.reset_index().to_dict("records")

        except Exception as e:
            logger.debug(f"从 AmazingData 获取 K 线失败: {e}")

        return None

    async def _fetch_kline_from_qmt(
        self,
        provider: Any,
        symbol: str,
        period: str,
        start_date: Optional[str],
        end_date: Optional[str],
        adjust: str,
    ) -> Optional[list]:
        """从 QMT 获取 K 线数据

        Args:
            provider: QMT Provider 实例
            symbol: 股票代码
            period: 周期
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型

        Returns:
            K 线数据列表，或 None
        """
        try:
            # 转换周期格式
            period_map = {
                "daily": "1d",
                "day": "1d",
                "1d": "1d",
                "5m": "5m",
                "15m": "15m",
                "30m": "30m",
                "60m": "1h",
                "1h": "1h",
            }
            qmt_period = period_map.get(period, period)

            # 尝试调用 get_kline 方法
            get_kline = getattr(provider, "get_kline", None)
            if callable(get_kline):
                result = get_kline(
                    symbol=symbol,
                    period=qmt_period,
                    start_date=start_date,
                    end_date=end_date,
                )
                if inspect.isawaitable(result):
                    result = await result
                if result is not None:
                    # 如果返回 DataFrame，转换为 records
                    if hasattr(result, "to_dict"):
                        return result.reset_index().to_dict("records")
                    return result

        except Exception as e:
            logger.debug(f"从 QMT 获取 K 线失败: {e}")

        return None

    async def get_stock_list(
        self,
        prefer_source: Optional[DataSourceType] = None,
        module: Optional[str] = None,
    ) -> StockListFetchResult:
        """
        获取股票列表，并返回领域对象与旧结构。
        """
        sources = self._get_source_priority(DataAccessType.STOCK_LIST, prefer_source)

        for source in sources:
            if self._is_circuit_open(source):
                logger.debug(f"数据源 {source.value} 处于熔断状态，跳过")
                continue

            # 动态获取 provider（支持 AmazingData 延迟注册）
            provider = await self._get_provider_for_source(source)
            if not provider:
                logger.debug(f"数据源 {source.value} 不可用，跳过")
                continue

            try:
                async with self._monitor_access(
                    source=source, access_type=DataAccessType.STOCK_LIST, module=module
                ):
                    payload: Optional[Any] = None
                    fetch_records = getattr(provider, "get_stock_list_records", None)
                    if callable(fetch_records):
                        maybe_records = fetch_records()
                        payload = (
                            await maybe_records
                            if inspect.isawaitable(maybe_records)
                            else maybe_records
                        )

                    if payload is None:
                        fetch_stock_list = getattr(provider, "fetch_stock_list", None)
                        if callable(fetch_stock_list):
                            maybe_payload = fetch_stock_list()
                            payload = (
                                await maybe_payload
                                if inspect.isawaitable(maybe_payload)
                                else maybe_payload
                            )

                    if payload is None:
                        get_stock_list = getattr(provider, "get_stock_list", None)
                        if callable(get_stock_list):
                            maybe_payload = get_stock_list()
                            payload = (
                                await maybe_payload
                                if inspect.isawaitable(maybe_payload)
                                else maybe_payload
                            )

                    result = build_stock_list_result(payload, source.value)
                    if result and (result.records or result.legacy):
                        if result.mismatch:
                            logger.warning(
                                "股票列表双写存在差异 source=%s mismatch=%d",
                                source.value,
                                result.mismatch,
                            )
                        return result
            except Exception as error:
                logger.warning(f"从 {source.value} 获取股票列表失败: {error}")
                continue

        # 所有数据源都失败，抛出异常（而非返回不完整的硬编码数据）
        # 这样调用者能明确知道获取失败，而不是误以为系统只有几只股票
        error_msg = "所有数据源获取股票列表失败（已尝试: miniqmt, amazingdata, akshare）"
        logger.error(error_msg)
        raise Exception(error_msg)


def monitor_access(
    source: DataSourceType, access_type: DataAccessType, module: Optional[str] = None
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
            symbol = kwargs.get("symbol") or (args[0] if args else None)

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
                    error_message=error_message,
                )

        return wrapper

    return decorator


_DATA_PROXY_INSTANCE: Optional[DataAccessProxy] = None
_DATA_PROXY_LOCK: asyncio.Lock | None = None


async def get_data_proxy() -> DataAccessProxy:
    """
    获取 DataAccessProxy 单例实例，确保只初始化一次。
    """

    global _DATA_PROXY_INSTANCE, _DATA_PROXY_LOCK

    if _DATA_PROXY_INSTANCE is not None and _DATA_PROXY_INSTANCE.initialized:
        return _DATA_PROXY_INSTANCE

    if _DATA_PROXY_LOCK is None:
        _DATA_PROXY_LOCK = asyncio.Lock()

    async with _DATA_PROXY_LOCK:
        if _DATA_PROXY_INSTANCE is None:
            _DATA_PROXY_INSTANCE = DataAccessProxy()
        if not _DATA_PROXY_INSTANCE.initialized:
            await _DATA_PROXY_INSTANCE.initialize()
        return _DATA_PROXY_INSTANCE


def async_monitor_access(
    source: DataSourceType, access_type: DataAccessType, module: Optional[str] = None
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
            symbol = kwargs.get("symbol") or (args[0] if args else None)

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
                    error_message=error_message,
                )

        return wrapper

    return decorator
