"""
数据提供者管理器

统一管理多个数据源，提供智能路由和容错机制。
"""

from __future__ import annotations

import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import (
    Awaitable,
    Callable,
    Dict,
    Final,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
    Literal,
    TypedDict,
    NotRequired,
    Required,
)

import pandas as pd
from loguru import logger

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProvider,
    DataProviderConfig,
    DataProviderError,
    DataRequest,
    DataResponse,
    DataSourceType,
)
from deepsearch.infrastructure.providers.interfaces.capabilities import (
    DataCapability,
    check_provider_capability,
    get_capable_providers,
)

AutoSource = Literal["auto"]
ProviderName = str
StatisticsMapping = Mapping[str, object]
SourceSelector = Union[AutoSource, DataSourceType, ProviderName]

FetchCallable = Callable[[DataRequest], Awaitable[object]]


class ProviderConfigPayload(TypedDict):
    name: Optional[str]
    source_type: Required[str]
    enabled: Required[bool]
    priority: Required[int]
    timeout: Required[float]
    retry_count: Required[int]
    config: NotRequired[Dict[str, object]]


class ProviderStatisticsPayload(TypedDict, total=False):
    resolved_name: Required[str]
    running: Required[bool]
    effective_priority: Required[int]
    config: Required[ProviderConfigPayload]
    status: NotRequired[str]
    metadata: NotRequired[Dict[str, object]]
    statistics: Dict[str, object]


class ManagerStatisticsDict(TypedDict):
    total_providers: int
    available_providers: int
    available_provider_names: List[str]
    providers: Dict[str, ProviderStatisticsPayload]


@dataclass(frozen=True)
class ProviderConfigSnapshot:
    name: Optional[str]
    source_type: DataSourceType
    enabled: bool
    priority: int
    timeout: float
    retry_count: int
    extras: Mapping[str, object] = field(default_factory=dict)

    def as_dict(self) -> ProviderConfigPayload:
        payload: ProviderConfigPayload = {
            "name": self.name,
            "source_type": self.source_type.value,
            "enabled": self.enabled,
            "priority": self.priority,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
        }
        if self.extras:
            payload["config"] = dict(self.extras)
        return payload


@dataclass(frozen=True)
class ProviderRuntimeStatus:
    resolved_name: ProviderName
    config: ProviderConfigSnapshot
    running: bool
    effective_priority: int
    status_label: Optional[str] = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def as_dict(self) -> ProviderStatisticsPayload:
        payload: ProviderStatisticsPayload = {
            "resolved_name": self.resolved_name,
            "running": self.running,
            "effective_priority": self.effective_priority,
            "config": self.config.as_dict(),
        }
        if self.status_label:
            payload["status"] = self.status_label
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True)
class ProviderStatisticsSnapshot:
    runtime: ProviderRuntimeStatus
    statistics: StatisticsMapping = field(default_factory=dict)

    def as_dict(self) -> ProviderStatisticsPayload:
        payload = self.runtime.as_dict()
        payload["statistics"] = dict(self.statistics)
        return payload


@dataclass(frozen=True)
class ManagerStatisticsSnapshot:
    total_providers: int
    available_provider_names: Tuple[ProviderName, ...]
    providers: Mapping[ProviderName, ProviderStatisticsSnapshot]

    def as_dict(self) -> ManagerStatisticsDict:
        providers_payload: Dict[str, ProviderStatisticsPayload] = {
            name: snapshot.as_dict() for name, snapshot in self.providers.items()
        }
        payload: ManagerStatisticsDict = {
            "total_providers": self.total_providers,
            "available_providers": len(self.available_provider_names),
            "available_provider_names": list(self.available_provider_names),
            "providers": providers_payload,
        }
        return payload


REQUEST_CAPABILITY_MAPPING: Final[Dict[str, DataCapability]] = {
    "historical_kline": DataCapability.KLINE_DATA,
    "minute_kline": DataCapability.MINUTE_DATA,
    "realtime_quotes": DataCapability.REALTIME_QUOTES,
    "realtime_quote": DataCapability.REALTIME_QUOTE,
    "stock_list": DataCapability.STOCK_LIST,
    "stock_info": DataCapability.STOCK_INFO,
    "order_book": DataCapability.ORDER_BOOK,
}

DEFAULT_PRIORITY: Final[int] = 999


class DataProviderManager:
    """
    数据提供者管理器

    功能：
    - 管理多个数据提供者
    - 智能选择最优数据源
    - 失败自动切换
    - 负载均衡
    - 统一的数据接口
    """

    def __init__(self) -> None:
        """初始化管理器"""
        self._providers: Dict[str, DataProvider] = {}
        self._provider_priority: Dict[str, int] = {
            "qmt": 1,  # QMT 优先级最高，提供实时数据
            "miniqmt": 2,  # MiniQMT 次优先，适合本地终端
            "amazingdata": 3,  # AmazingData 核心证券级数据源
            "akshare": 4,  # AkShare 作为 Cloudflare 代理的兜底源
        }
        self._initialized = False
        self._akshare_provider: Optional[DataProvider] = None
        self._miniqmt_provider: Optional[DataProvider] = None
        self._qmt_provider: Optional[DataProvider] = None

    async def initialize(self) -> None:
        """初始化所有数据提供者"""
        if self._initialized:
            return

        logger.info("初始化数据提供者管理器...")

        # 初始化 MiniQMT 提供者
        try:
            from deepsearch.config import get_config

            config = get_config()

            miniqmt_config = getattr(config, "miniqmt", None)
            miniqmt_enabled = False
            if isinstance(miniqmt_config, Mapping):
                miniqmt_enabled = bool(miniqmt_config.get("enabled", False))
            elif miniqmt_config is not None:
                miniqmt_enabled = bool(getattr(miniqmt_config, "enabled", False))

            if miniqmt_enabled:
                from .miniqmt import MiniQMTProvider

                self._miniqmt_provider = MiniQMTProvider()
                await self._miniqmt_provider.initialize_async()
                self._providers["miniqmt"] = self._miniqmt_provider
                logger.info("MiniQMT 提供者初始化成功")
        except Exception as e:
            logger.error(f"MiniQMT 提供者初始化失败: {e}")

        # 初始化 AkShare 提供者（可能使用Cloudflare代理）
        try:
            from deepsearch.infrastructure.providers.implementations.akshare.akshare import (
                AkShareProxyProvider,
            )

            akshare_provider = AkShareProxyProvider()

            if not hasattr(akshare_provider, "config"):
                akshare_provider.config = DataProviderConfig(
                    name="akshare",
                    source_type=DataSourceType.AKSHARE,
                    enabled=True,
                )
            if not hasattr(akshare_provider, "status"):
                akshare_provider.status = "running"

            await akshare_provider.initialize()
            self._akshare_provider = cast(DataProvider, akshare_provider)
            self._providers["akshare"] = self._akshare_provider
            logger.info("AkShare 提供者初始化成功")
        except Exception as e:
            logger.error(f"AkShare 提供者初始化失败: {e}")

        # 初始化其他已注册的提供者
        init_tasks = []
        init_names: List[str] = []
        for name, provider in self._providers.items():
            if (
                name not in ("cloudflare", "cloudflare_proxy")
                and hasattr(provider, "config")
                and provider.config.enabled
            ):
                init_tasks.append(self._init_provider(name, provider))
                init_names.append(name)

        if init_tasks:
            results = await asyncio.gather(*init_tasks, return_exceptions=True)

            # 处理初始化结果
            for name, result in zip(init_names, results):
                if isinstance(result, Exception):
                    logger.error(f"数据提供者 {name} 初始化失败: {result}")
                else:
                    logger.info(f"数据提供者 {name} 初始化成功")

        self._initialized = True
        logger.info(f"数据提供者管理器初始化完成，可用提供者: {self.get_available_providers()}")

    async def _init_provider(self, name: str, provider: DataProvider) -> None:
        """初始化单个提供者"""
        try:
            initialize_async = getattr(provider, "initialize_async", None)
            if callable(initialize_async):
                await initialize_async()
            else:
                initialize = getattr(provider, "initialize", None)
                if callable(initialize):
                    result = initialize()
                    if asyncio.iscoroutine(result):
                        await result

            start_async = getattr(provider, "start_async", None)
            if callable(start_async):
                await start_async()
        except Exception as e:
            logger.error(f"初始化提供者 {name} 失败: {e}")
            raise

    @staticmethod
    def _is_provider_running(provider: DataProvider) -> bool:
        """判断数据提供者是否处于运行状态"""
        status = getattr(provider, "status", None)
        if isinstance(status, Enum):
            return str(status.value) == "running"
        if isinstance(status, str):
            return status == "running"
        return True

    @staticmethod
    def _clone_request(request: DataRequest) -> DataRequest:
        """克隆数据请求，避免在不同提供者间共享可变引用。"""

        symbols_copy: Optional[List[str]]
        if request.symbols is None:
            symbols_copy = None
        elif isinstance(request.symbols, list):
            symbols_copy = list(request.symbols)
        else:
            symbols_copy = list(request.symbols)

        return DataRequest(
            request_type=request.request_type,
            source=request.source,
            symbol=request.symbol,
            symbols=symbols_copy,
            period=request.period,
            start_date=request.start_date,
            end_date=request.end_date,
            adjust=request.adjust,
            params=dict(request.params),
            extra_params=dict(request.extra_params),
        )

    def _build_config_snapshot(self, provider: DataProvider) -> ProviderConfigSnapshot:
        config = provider.config
        extras_source = config.config if isinstance(config.config, Mapping) else {}
        extras: Dict[str, object]
        if isinstance(extras_source, Mapping):
            extras = {str(key): extras_source[key] for key in extras_source}
        else:
            extras = {}
        return ProviderConfigSnapshot(
            name=config.name,
            source_type=config.source_type,
            enabled=config.enabled,
            priority=config.priority,
            timeout=config.timeout,
            retry_count=config.retry_count,
            extras=extras,
        )

    def _build_runtime_status(self, name: ProviderName, provider: DataProvider) -> ProviderRuntimeStatus:
        config_snapshot = self._build_config_snapshot(provider)
        status_attr = getattr(provider, "status", None)
        if isinstance(status_attr, Enum):
            status_label: Optional[str] = str(status_attr.value)
        elif status_attr is None:
            status_label = None
        else:
            status_label = str(status_attr)

        metadata: Dict[str, object] = {}
        healthy_attr = getattr(provider, "is_healthy", None)
        if callable(healthy_attr):
            try:
                metadata["healthy"] = bool(healthy_attr())
            except Exception:
                metadata["healthy"] = False

        capabilities_attr = getattr(provider, "get_capabilities", None)
        if callable(capabilities_attr):
            try:
                capabilities_raw = cast(Iterable[object], capabilities_attr())
                metadata["capabilities"] = [
                    capability.value if isinstance(capability, DataCapability) else str(capability)
                    for capability in capabilities_raw
                ]
            except Exception:
                pass

        effective_priority = self._provider_priority.get(
            (provider.config.name or name).lower(),
            config_snapshot.priority,
        )

        return ProviderRuntimeStatus(
            resolved_name=name,
            config=config_snapshot,
            running=self._is_provider_running(provider),
            effective_priority=effective_priority,
            status_label=status_label,
            metadata=metadata,
        )

    def _get_provider_statistics_mapping(self, provider: DataProvider) -> StatisticsMapping:
        raw_stats = provider.get_statistics()
        if isinstance(raw_stats, Mapping):
            return {str(key): raw_stats[key] for key in raw_stats}
        if raw_stats is None:
            return {}
        return {"value": raw_stats}

    def _build_statistics_snapshot(self) -> ManagerStatisticsSnapshot:
        provider_snapshots: Dict[ProviderName, ProviderStatisticsSnapshot] = {}
        available: List[ProviderName] = []
        for name, provider in self._providers.items():
            runtime = self._build_runtime_status(name, provider)
            if runtime.config.enabled and runtime.running:
                available.append(name)
            provider_snapshots[name] = ProviderStatisticsSnapshot(
                runtime=runtime,
                statistics=self._get_provider_statistics_mapping(provider),
            )
        return ManagerStatisticsSnapshot(
            total_providers=len(self._providers),
            available_provider_names=tuple(available),
            providers=provider_snapshots,
        )

    def _resolve_provider(self, selector: SourceSelector) -> Optional[DataProvider]:
        if isinstance(selector, DataSourceType):
            target = selector.value.lower()
        else:
            target = str(selector).strip().lower()

        if not target:
            return None

        direct = self._providers.get(target)
        if direct is not None:
            return direct

        for name, provider in self._providers.items():
            config_name = (provider.config.name or "").lower()
            if config_name and config_name == target:
                return provider
            source_type = getattr(provider.config, "source_type", None)
            if isinstance(source_type, DataSourceType) and source_type.value.lower() == target:
                return provider

        return None

    @staticmethod
    def _prepare_dataframe(data: object) -> Optional[pd.DataFrame]:
        """尝试将原始数据转换为 DataFrame。"""

        if isinstance(data, pd.DataFrame):
            return data
        if data is None:
            return None
        if isinstance(data, Mapping):
            return pd.DataFrame([data])
        if isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
            if not data:
                return pd.DataFrame()
            if all(isinstance(item, Mapping) for item in data):
                return pd.DataFrame(list(data))
        return None

    def _extract_dataframe(self, response: DataResponse, context: str) -> pd.DataFrame:
        """从响应中提取 DataFrame，失败时抛出 DataProviderError。"""

        dataframe = self._prepare_dataframe(response.data)
        if dataframe is not None:
            return dataframe

        metadata_source = response.metadata.get("source") if isinstance(response.metadata, dict) else None
        source_label = f"[{metadata_source}] " if metadata_source else ""
        error_message = response.error or "无有效数据返回"
        raise DataProviderError(f"{context}失败: {source_label}{error_message}")

    async def _fetch_with_provider(self, provider: DataProvider, request: DataRequest) -> DataResponse:
        """调用具体提供者获取数据，并包装为 DataResponse。"""

        provider_name = provider.config.name or provider.__class__.__name__
        metadata = {"source": provider_name, "request_type": request.request_type}

        fetch_fn_obj = getattr(provider, "get_data", None)
        if not callable(fetch_fn_obj):
            return DataResponse(
                success=False,
                error=f"数据提供者 {provider_name} 未实现 get_data 接口",
                metadata=metadata,
            )

        fetch_callable = cast(FetchCallable, fetch_fn_obj)
        try:
            raw_result = await fetch_callable(request)
        except Exception as exc:  # pragma: no cover - 记录异常日志
            logger.error(f"提供者 {provider_name} 异常: {exc}")
            return DataResponse(success=False, error=str(exc), metadata=metadata)

        return self._normalize_response(raw_result, provider, request)

    def _normalize_response(self, raw_result: object, provider: DataProvider, request: DataRequest) -> DataResponse:
        """将原始返回值统一转换为 DataResponse。"""

        source_name = provider.config.name or provider.__class__.__name__
        metadata = {
            "source": source_name,
            "request_type": request.request_type,
        }

        if isinstance(raw_result, DataResponse):
            raw_result.metadata.setdefault("source", metadata["source"])
            raw_result.metadata.setdefault("request_type", metadata["request_type"])
            return raw_result

        if raw_result is None:
            return DataResponse(success=False, error="数据源返回空结果", metadata=metadata)

        return DataResponse(success=True, data=raw_result, metadata=metadata)

    def register_provider(self, provider: DataProvider) -> None:
        """
        注冊数据提供者

        Args:
            provider: 数据提供者实例
        """
        name = provider.config.name or provider.__class__.__name__.lower()
        if name in self._providers:
            logger.warning(f"数据提供者 {name} 已存在，跳过注册")

        self._providers[name] = provider
        source_type = getattr(provider.config, "source_type", None)
        if isinstance(source_type, DataSourceType):
            source_label = source_type.value
        else:
            source_label = str(source_type or "unknown")
        logger.info(f"注册数据提供者: {name} ({source_label})")

    def unregister_provider(self, name: str) -> None:
        """
        注销数据提供者

        Args:
            name: 提供者名称
        """
        if name in self._providers:
            del self._providers[name]
            logger.info(f"注销数据提供者: {name}")

    def get_provider(self, name: str) -> Optional[DataProvider]:
        """
        获取指定的数据提供者

        Args:
            name: 提供者名称

        Returns:
            数据提供者实例
        """
        return self._providers.get(name)

    def get_available_providers(self) -> List[ProviderName]:
        """获取所有可用的提供者名称"""
        return [
            name
            for name, provider in self._providers.items()
            if provider.config.enabled and self._is_provider_running(provider)
        ]

    async def get_stock_daily(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        source: SourceSelector = "auto",
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """
        获取股票日线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            source: 数据源 ("auto" 表示自动选择)
            adjust: 复权类型

        Returns:
            日线数据DataFrame
        """
        request = DataRequest(
            request_type="historical_kline",
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period="1d",
            adjust=adjust,
        )

        response = await self._get_data(request, source)

        if response.success:
            return self._extract_dataframe(response, "获取股票日线数据")

        raise DataProviderError(f"获取数据失败: {response.error}")

    async def get_stock_minute(
        self, symbol: str, date: Optional[str] = None, period: str = "1m", source: SourceSelector = "auto"
    ) -> pd.DataFrame:
        """
        获取股票分钟数据

        Args:
            symbol: 股票代码
            date: 日期
            period: 周期 (1m, 5m, 15m, 30m, 60m)
            source: 数据源

        Returns:
            分钟数据DataFrame
        """
        request = DataRequest(
            request_type="minute_kline",
            symbol=symbol,
            start_date=date,
            end_date=date,
            period=period,
        )

        response = await self._get_data(request, source)

        if response.success:
            return self._extract_dataframe(response, "获取股票分钟数据")

        raise DataProviderError(f"获取数据失败: {response.error}")

    async def get_realtime_quotes(self, symbols: List[str], source: SourceSelector = "auto") -> pd.DataFrame:
        """
        获取实时行情

        Args:
            symbols: 股票代码列表
            source: 数据源

        Returns:
            实时行情DataFrame
        """
        request = DataRequest(
            request_type="realtime_quotes",
            symbols=symbols,
            period="tick",
        )

        response = await self._get_data(request, source)

        if response.success:
            return self._extract_dataframe(response, "获取实时行情")

        raise DataProviderError(f"获取数据失败: {response.error}")

    async def _get_data(self, request: DataRequest, source: SourceSelector = "auto") -> DataResponse:
        """
        获取数据（内部方法）

        Args:
            request: 数据请求
            source: 数据源

        Returns:
            数据响应
        """
        if not self._initialized:
            await self.initialize()

        # 确定使用的提供者

        provider_selector = source
        providers: List[DataProvider]

        if isinstance(provider_selector, str) and provider_selector.strip().lower() == "auto":
            providers = self._select_providers(request)
        else:
            provider = self._resolve_provider(provider_selector)
            selector_label = (
                provider_selector.value if isinstance(provider_selector, DataSourceType) else str(provider_selector)
            )
            if provider is None:
                return DataResponse(success=False, error=f"数据提供者 {selector_label} 不存在或未启用")
            if not provider.config.enabled:
                return DataResponse(success=False, error=f"数据提供者 {selector_label} 已被禁用")
            if not self._is_provider_running(provider):
                return DataResponse(success=False, error=f"数据提供者 {selector_label} 未处于运行状态")
            providers = [provider]

        if not providers:
            return DataResponse(success=False, error="没有可用的数据提供者")

        last_error: Optional[str] = None
        for provider in providers:
            provider_request = self._clone_request(request)
            provider_request.source = getattr(provider.config, "source_type", DataSourceType.CUSTOM)

            logger.debug(
                "尝试从 {} 获取数据 (request_type={})",
                provider.config.name or provider.__class__.__name__,
                provider_request.request_type,
            )

            response = await self._fetch_with_provider(provider, provider_request)

            if response.success:
                return response

            last_error = response.error or last_error
            logger.debug(
                "提供者 {} 返回失败: {}",
                provider.config.name or provider.__class__.__name__,
                response.error,
            )

        # 所有提供者都失败
        fallback_error = last_error or "未知错误"
        return DataResponse(success=False, error=f"所有数据源都失败: {fallback_error}")

    def _select_providers(self, request: DataRequest) -> List[DataProvider]:
        """
        根据请求选择合适的提供者

        Args:
            request: 数据请求

        Returns:
            按优先级排序的提供者列表
        """
        available: List[DataProvider] = []
        normalized_type = (request.request_type or "").lower()
        capability = REQUEST_CAPABILITY_MAPPING.get(normalized_type)

        if capability is not None:
            candidate_names = get_capable_providers(self._providers, capability)
            for name in candidate_names:
                provider = self._providers.get(name)
                if provider is None:
                    continue
                if not provider.config.enabled or not self._is_provider_running(provider):
                    continue
                available.append(provider)

        if not available:
            for provider in self._providers.values():
                if not provider.config.enabled or not self._is_provider_running(provider):
                    continue
                available.append(provider)

        available.sort(
            key=lambda provider: self._provider_priority.get(
                (provider.config.name or "").lower(),
                DEFAULT_PRIORITY,
            )
        )

        return available

    async def stop(self) -> None:
        """停止所有数据提供者"""
        logger.info("停止数据提供者管理器...")

        stop_tasks = []
        for provider in self._providers.values():
            if self._is_provider_running(provider):
                stop_tasks.append(provider.stop_async())

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        self._initialized = False
        logger.info("数据提供者管理器已停止")

    def get_statistics(self) -> ManagerStatisticsDict:
        """获取统计信息快照 (字典格式)。"""
        snapshot = self._build_statistics_snapshot()
        return snapshot.as_dict()

    def get_statistics_snapshot(self) -> ManagerStatisticsSnapshot:
        """获取统计信息的结构化快照。"""
        return self._build_statistics_snapshot()

    def get_runtime_status(self) -> Dict[ProviderName, ProviderRuntimeStatus]:
        """返回当前所有数据提供者的运行态概览。"""
        return {
            name: self._build_runtime_status(name, provider)
            for name, provider in self._providers.items()
        }

    async def get_data_with_capability(
        self, capability: DataCapability, request: DataRequest
    ) -> DataResponse:
        """
        根据数据能力选择合适的数据源并获取数据。

        Args:
            capability: 目标数据能力
            request: 数据请求模型

        Returns:
            数据响应对象
        """
        if not self._initialized:
            await self.initialize()

        capable_providers = get_capable_providers(self._providers, capability)

        if not capable_providers:
            return DataResponse(success=False, error=f"没有数据源支持能力: {capability.value}")

        last_error: Optional[str] = None
        for provider_name in capable_providers:
            provider = self._providers.get(provider_name)
            if not provider:
                logger.debug(f"数据源 {provider_name} 未初始化")
                continue

            if hasattr(provider, "is_healthy") and not provider.is_healthy():
                logger.debug(f"数据源 {provider_name} 健康检查未通过")
                continue
            if not self._is_provider_running(provider):
                logger.debug(f"数据源 {provider_name} 未运行")
                continue

            provider_request = self._clone_request(request)
            provider_request.source = getattr(provider.config, "source_type", DataSourceType.CUSTOM)

            try:
                logger.info(f"尝试使用 {provider_name} 获取 {capability.value} 数据")

                if provider_name == "akshare" and hasattr(provider, "_fetch_with_fallback"):
                    from .capabilities import get_akshare_api

                    api_name = get_akshare_api(capability)
                    if api_name:
                        response_payload = await provider._fetch_with_fallback(
                            api_name, provider_request.extra_params
                        )
                        normalized = self._normalize_response(
                            response_payload.get("data") if response_payload else None,
                            provider,
                            provider_request,
                        )
                        if normalized.success:
                            normalized.metadata["capability"] = capability.value
                            return normalized
                        last_error = normalized.error
                        continue

                response = await self._fetch_with_provider(provider, provider_request)
                if response.success:
                    response.metadata["capability"] = capability.value
                    return response
                last_error = response.error or last_error

            except Exception as e:  # pragma: no cover - 记录异常
                last_error = str(e)
                logger.warning(f"{provider_name} 获取 {capability.value} 失败: {e}")
                continue

        fallback_error = last_error or "未知错误"
        return DataResponse(
            success=False,
            error=f"所有数据源获取 {capability.value} 失败: {fallback_error}",
        )

    def check_capability_support(self, capability: DataCapability) -> Dict[str, bool]:
        """
        检查各数据源对指定能力的支持情况

        Args:
            capability: 数据能力

        Returns:
            各数据源的支持情况
        """
        support: Dict[str, bool] = {}
        for provider_name, provider in self._providers.items():
            support[provider_name] = check_provider_capability(provider, capability)
        return support
