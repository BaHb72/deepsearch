"""Realtime data source orchestrator."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Iterable, Sequence, Tuple, cast

from core.adapters.market_data.akshare_polling_adapter import AkSharePollingAdapter
from core.config.models.data_sources import RealtimeAdapterSpec
from core.config.settings import Settings
from core.infrastructure.providers.implementations.amazingdata.ports import build_board_source
from core.ports.market_data import (
    MarketDataPortRegistry,
    MarketStreamPort,
    RealtimeAdapter,
    RealtimeAdapterCapabilities,
    RealtimePortBundle,
)
from loguru import logger

from .cache_reader import MarketDataCacheReader
from .cache_writer import MarketDataCacheWriter
from .factory import create_realtime_streaming_pipeline
from .pipeline import MarketDataRealtimePipeline
from .runner import MarketDataStreamingRunner
from .service import RealTimeMarketDataService


@dataclass(slots=True)
class RealtimeRuntimeHandle:
    """Artifacts produced by an active realtime adapter."""

    adapter_name: str
    capabilities: RealtimeAdapterCapabilities
    ports: RealtimePortBundle
    adapter: RealtimeAdapter | None
    service: RealTimeMarketDataService
    cache_writer: MarketDataCacheWriter
    cache_reader: MarketDataCacheReader
    pipeline: MarketDataRealtimePipeline
    runner: MarketDataStreamingRunner
    provider: Any | None = None


class PortBundleRegistry(MarketDataPortRegistry):
    """Minimal registry bridging RealtimePortBundle to domain service."""

    def __init__(self, bundle: RealtimePortBundle) -> None:
        self._bundle = bundle

    def resolve_market_stream(self) -> MarketStreamPort:
        return self._bundle.require_stream()

    def resolve_capital_pulse(self):
        if self._bundle.capital is None:
            raise NotImplementedError("capital pulse port unavailable")
        return self._bundle.capital

    def resolve_auction_quality(self):
        if self._bundle.auction is None:
            raise NotImplementedError("auction quality port unavailable")
        return self._bundle.auction

    def resolve_order_imbalance(self):
        if self._bundle.order is None:
            raise NotImplementedError("order imbalance port unavailable")
        return self._bundle.order

    def resolve_limit_strength(self):
        raise NotImplementedError

    def resolve_etf_reference(self):
        raise NotImplementedError

    def resolve_margin_flow(self):
        raise NotImplementedError

    def resolve_supply_constraint(self):
        raise NotImplementedError

    def resolve_style_preference(self):
        raise NotImplementedError

    def resolve_concept_association(self):
        raise NotImplementedError

    def resolve_external_overlay(self):
        return None


class RealtimeDataOrchestrator:
    """Manage realtime adapters with fallback + health tracking."""

    def __init__(self, settings: Settings, provider_container: Any | None = None) -> None:
        self._settings = settings
        self._provider_container = provider_container
        self._handle: RealtimeRuntimeHandle | None = None
        self._lock = asyncio.Lock()
        self._health: Dict[str, Dict[str, Any]] = {}
        self._active_adapter: str | None = None
        self._adapter_specs: Dict[str, RealtimeAdapterSpec]
        self._configured_order: Tuple[str, ...]
        self._adapter_specs, self._configured_order = self._load_realtime_specs()

    @staticmethod
    def _normalize_calendar_market_code(raw: str) -> str:
        if not raw:
            return "SH"
        normalized = raw.strip().upper()
        mapping = {
            "SH_MAIN": "SH",
            "SZ_MAIN": "SZ",
            "STAR": "SH",
            "SZ_GEM": "SZ",
            "GEM": "SZ",
            "BSE": "SH",
            "BJ": "SH",
            "INDEX": "SH",
            "ETF": "SH",
        }
        if normalized in mapping:
            return mapping[normalized]
        if "_" in normalized:
            prefix = normalized.split("_", 1)[0]
            if prefix in mapping:
                return mapping[prefix]
            if prefix in {"SH", "SZ", "BJ"}:
                return prefix
        if normalized in {"SH", "SZ", "BJ"}:
            return normalized
        return normalized

    @staticmethod
    def _allow_amazingdata_calendar_fallback(adapter_name: str) -> bool:
        normalized = (adapter_name or "").strip().lower()
        if not normalized:
            return False
        return normalized.startswith("miniqmt") or normalized in {
            "qmt",
            "xtquant",
            "mini-qmt",
        }

    @staticmethod
    def _resolve_dask_amazingdata_adapter() -> Any | None:
        try:
            from core.compute.dask_init_state import get_dask_init_manager_sync

            manager = get_dask_init_manager_sync()
        except Exception as exc:
            logger.debug("读取 Dask 初始化状态失败，无法获取 amazingdata adapter: {}", exc)
            return None

        if manager is None:
            return None
        adapter = getattr(manager, "amazingdata_adapter", None)
        if adapter is not None:
            return adapter
        if not bool(getattr(manager, "amazingdata_ready", False)):
            return None
        return None

    @staticmethod
    def _normalize_calendar_result(result: Sequence[int] | Sequence[str] | None) -> tuple[int, ...]:
        normalized: list[int] = []
        seen: set[int] = set()
        for value in result or ():
            text = str(value).strip()
            if not text:
                continue
            digits = "".join(ch for ch in text if ch.isdigit())
            if len(digits) != 8:
                continue
            try:
                parsed = int(digits)
            except ValueError:
                continue
            if parsed in seen:
                continue
            seen.add(parsed)
            normalized.append(parsed)
        return tuple(normalized)

    async def _call_calendar_provider(
        self,
        *,
        provider: Any,
        provider_name: str,
        market: str,
        adapter_name: str,
    ) -> tuple[int, ...]:
        calendar_getter = getattr(provider, "get_calendar", None)
        if not callable(calendar_getter):
            logger.warning(
                "交易日历 fallback 失败：{} provider 缺少 get_calendar 接口 adapter={}",
                provider_name,
                adapter_name,
            )
            return ()

        normalized_market = self._normalize_calendar_market_code(market)
        getter = cast(
            Callable[..., Awaitable[Sequence[int] | Sequence[str] | None]],
            calendar_getter,
        )
        call_specs: tuple[dict[str, str], ...] = (
            {"data_type": "int", "market": normalized_market},
            {"market": normalized_market},
            {},
        )
        signature_errors: list[str] = []
        for kwargs in call_specs:
            try:
                result = await getter(**kwargs)
                normalized_result = self._normalize_calendar_result(result)
                if normalized_result:
                    logger.info(
                        "交易日历 fallback 命中 {} adapter={} market={} normalized={} count={}",
                        provider_name,
                        adapter_name,
                        market,
                        normalized_market,
                        len(normalized_result),
                    )
                    return normalized_result

                logger.warning(
                    "交易日历 fallback 返回空结果 source={} adapter={} market={} normalized={}",
                    provider_name,
                    adapter_name,
                    market,
                    normalized_market,
                )
                return ()
            except TypeError as exc:
                signature_errors.append(str(exc))
                continue
            except Exception as exc:
                logger.warning(
                    "交易日历 fallback 调用 {} 失败 adapter={} market={} normalized={} error={}",
                    provider_name,
                    adapter_name,
                    market,
                    normalized_market,
                    exc,
                )
                return ()

        logger.warning(
            "交易日历 fallback 调用 {} 失败：get_calendar 参数签名不兼容 adapter={} errors={}",
            provider_name,
            adapter_name,
            " | ".join(signature_errors) if signature_errors else "unknown",
        )
        return ()

    async def _load_akshare_calendar(
        self,
        *,
        market: str,
        adapter_name: str,
    ) -> tuple[int, ...]:
        container = self._provider_container
        provider: Any | None = None
        can_use_container = container is not None

        if can_use_container:
            has_method = getattr(container, "has", None)
            if callable(has_method):
                try:
                    can_use_container = bool(has_method("akshare"))
                except Exception as exc:
                    can_use_container = False
                    logger.debug("检查 provider_container.has(akshare) 失败: {}", exc)

        if can_use_container:
            get_method = getattr(container, "get", None)
            if callable(get_method):
                try:
                    provider = await cast(Callable[[str], Awaitable[Any]], get_method)("akshare")
                except Exception as exc:
                    logger.warning(
                        "交易日历 fallback 获取 akshare provider 失败 adapter={} error={}",
                        adapter_name,
                        exc,
                    )

        if provider is None:
            logger.warning(
                "交易日历 secondary fallback 未命中 akshare provider adapter={} (container_registered={})",
                adapter_name,
                can_use_container,
            )
            return ()

        return await self._call_calendar_provider(
            provider=provider,
            provider_name="akshare",
            market=market,
            adapter_name=adapter_name,
        )

    async def _load_amazingdata_calendar(
        self,
        *,
        market: str,
        adapter_name: str,
    ) -> tuple[int, ...]:
        container = self._provider_container
        provider: Any | None = None
        can_use_container = container is not None

        if can_use_container:
            has_method = getattr(container, "has", None)
            if callable(has_method):
                try:
                    can_use_container = bool(has_method("amazingdata"))
                except Exception as exc:
                    can_use_container = False
                    logger.debug("检查 provider_container.has(amazingdata) 失败: {}", exc)

        if can_use_container:
            get_method = getattr(container, "get", None)
            if callable(get_method):
                try:
                    provider = await cast(Callable[[str], Awaitable[Any]], get_method)(
                        "amazingdata"
                    )
                except Exception as exc:
                    logger.warning(
                        "交易日历 fallback 获取 amazingdata provider 失败 adapter={} error={}",
                        adapter_name,
                        exc,
                    )
                    provider = None
            else:
                logger.warning(
                    "交易日历 fallback 无法读取 provider_container.get adapter={}",
                    adapter_name,
                )

        if provider is None:
            provider = self._resolve_dask_amazingdata_adapter()
            if provider is not None:
                logger.info(
                    "交易日历 fallback 使用 Dask 初始化管理器中的 amazingdata adapter adapter={}",
                    adapter_name,
                )

        if provider is None:
            logger.warning(
                "交易日历 fallback 未命中 amazingdata provider adapter={} (container_registered={})",
                adapter_name,
                can_use_container,
            )
            return await self._load_akshare_calendar(market=market, adapter_name=adapter_name)

        amazingdata_calendar = await self._call_calendar_provider(
            provider=provider,
            provider_name="amazingdata",
            market=market,
            adapter_name=adapter_name,
        )
        if amazingdata_calendar:
            return amazingdata_calendar
        return await self._load_akshare_calendar(market=market, adapter_name=adapter_name)

    def _build_adapter_calendar_loader(
        self,
        adapter: RealtimeAdapter,
    ) -> Callable[[str], Awaitable[Sequence[int]]]:
        adapter_name = adapter.name
        enable_amazingdata_fallback = self._allow_amazingdata_calendar_fallback(adapter_name)

        async def _adapter_calendar_loader(market: str) -> Sequence[int]:
            has_cal = hasattr(adapter, "get_calendar")
            logger.debug(
                "日历加载器: adapter={} hasattr(get_calendar)={} market={}",
                adapter_name,
                has_cal,
                market,
            )
            if has_cal:
                try:
                    result = await adapter.get_calendar(market)  # type: ignore[attr-defined]
                    normalized = tuple(result or ())
                    logger.debug(
                        "日历加载器: adapter={} 返回 {} 条记录",
                        adapter_name,
                        len(normalized),
                    )
                    if normalized:
                        return normalized
                    logger.warning(
                        "日历加载器: adapter={} 返回空交易日历，尝试后备源",
                        adapter_name,
                    )
                except Exception as exc:
                    logger.warning("适配器日历获取失败 {}: {}", adapter_name, exc)

            if not enable_amazingdata_fallback:
                return ()

            return await self._load_amazingdata_calendar(
                market=market,
                adapter_name=adapter_name,
            )

        return _adapter_calendar_loader

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def active_handle(self) -> RealtimeRuntimeHandle | None:
        return self._handle

    async def ensure_handle(self) -> RealtimeRuntimeHandle:
        if self._handle is not None:
            return self._handle
        async with self._lock:
            if self._handle is None:
                self._handle = await self._bootstrap_sequence()
        return self._handle

    async def shutdown(self) -> None:
        async with self._lock:
            await self._dispose_active_handle()

    def get_status_snapshot(self) -> Dict[str, Any]:
        return {
            "active": self._active_adapter,
            "adapters": {name: dict(status) for name, status in self._health.items()},
        }

    async def _bootstrap_sequence(self) -> RealtimeRuntimeHandle:
        last_error: Exception | None = None
        for adapter_name in self._adapter_sequence():
            try:
                handle = await self._start_adapter(adapter_name)
                if handle:
                    self._active_adapter = handle.adapter_name
                    self._record_success(handle.adapter_name)
                    return handle
            except Exception as exc:
                last_error = exc
                self._record_failure(adapter_name, exc)
                logger.warning("Realtime adapter {} failed: {}", adapter_name, exc)
        raise RuntimeError(f"no realtime adapter available; last_error={last_error}")

    def _adapter_sequence(self) -> Iterable[str]:
        if self._configured_order:
            return self._configured_order
        ds_cfg = getattr(self._settings, "data_sources", None)
        if ds_cfg and ds_cfg.fallback_order:
            return tuple(ds_cfg.fallback_order)
        return ("amazingdata", "akshare", "cloudflare")

    def _load_realtime_specs(self) -> tuple[Dict[str, RealtimeAdapterSpec], Tuple[str, ...]]:
        ds_cfg = getattr(self._settings, "data_sources", None)
        realtime_cfg = getattr(ds_cfg, "realtime", None) if ds_cfg else None
        if realtime_cfg is None or not getattr(realtime_cfg, "adapters", None):
            return {}, ()

        indexed_specs: list[tuple[int, int, RealtimeAdapterSpec]] = []
        for index, spec in enumerate(realtime_cfg.adapters):
            if not spec.enabled:
                continue
            name = spec.name.strip()
            if not name:
                continue
            indexed_specs.append((int(spec.priority), index, spec))
        if not indexed_specs:
            return {}, ()

        indexed_specs.sort(key=lambda item: (item[0], item[1]))
        mapping: Dict[str, RealtimeAdapterSpec] = {}
        order: list[str] = []
        seen: set[str] = set()
        for _, _, spec in indexed_specs:
            normalized_name = spec.name.strip().lower()
            if normalized_name in seen:
                continue
            seen.add(normalized_name)
            mapping[normalized_name] = spec
            order.append(spec.name.strip())
        return mapping, tuple(order)

    def _record_success(self, name: str) -> None:
        self._health[name] = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _record_failure(self, name: str, exc: Exception) -> None:
        self._health[name] = {
            "status": "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
        }

    async def switch_to(self, adapter_name: str) -> RealtimeRuntimeHandle:
        """Force switch to the specified adapter, rebuilding runtime artifacts."""

        normalized = adapter_name.strip().lower()
        if not normalized:
            raise ValueError("adapter_name must not be empty")

        sequence = tuple(self._adapter_sequence())
        candidate = next((name for name in sequence if name.lower() == normalized), None)
        if candidate is None:
            raise ValueError(f"adapter {adapter_name} is not configured or enabled")

        async with self._lock:
            if self._handle and self._handle.adapter_name.lower() == normalized:
                return self._handle

            await self._dispose_active_handle()

            try:
                handle = await self._start_adapter(candidate)
            except Exception as exc:
                self._record_failure(candidate, exc)
                logger.warning("Realtime adapter {} failed during switch: {}", candidate, exc)
                raise

            if handle is None:
                raise RuntimeError(f"unable to start realtime adapter {candidate}")

            self._handle = handle
            self._active_adapter = handle.adapter_name
            self._record_success(handle.adapter_name)
            return handle

    async def _start_adapter(self, adapter_name: str) -> RealtimeRuntimeHandle | None:
        spec = self._adapter_specs.get(adapter_name.lower())
        label = spec.name if spec else adapter_name
        driver = (spec.driver if spec and spec.driver else adapter_name).lower()
        options = dict(getattr(spec, "options", {}) or {})

        if driver in {"amazingdata", "amazing-data"}:
            return await self._start_amazingdata(label)

        if driver in {"akshare", "akshare_polling", "akshare-proxy", "akshare_proxy", "cloudflare"}:
            use_proxy_default = driver in {"cloudflare", "akshare_proxy", "akshare-proxy"}
            use_proxy = self._bool_option(options.get("use_proxy"), default=use_proxy_default)
            batch_size = self._int_option(options.get("batch_size"), default=20)
            return await self._start_polling_adapter(
                AkSharePollingAdapter(name=label, use_proxy=use_proxy, batch_size=batch_size)
            )

        if driver in {"miniqmt", "qmt", "xtquant", "mini-qmt"}:
            return await self._start_miniqmt(label)

        raise RuntimeError(f"unsupported realtime adapter driver={driver} name={label}")

    async def _start_amazingdata(self, adapter_alias: str | None = None) -> RealtimeRuntimeHandle:
        market_cfg = getattr(self._settings, "market_data", None)
        if market_cfg is None:
            raise RuntimeError("market_data config missing, cannot start realtime runtime")
        realtime_cfg = getattr(market_cfg, "realtime", None)
        if realtime_cfg is None:
            raise RuntimeError("market_data.realtime config missing")

        provider = None

        # 优先从 ProviderContainer 获取已注册的 Provider（避免重复创建导致 SDK 冲突）
        if self._provider_container is not None:
            try:
                if self._provider_container.has("amazingdata"):
                    provider = await self._provider_container.get("amazingdata")
                    logger.info("使用 ProviderContainer 中已注册的 AmazingData Provider")
            except Exception as exc:
                logger.warning("从 ProviderContainer 获取 AmazingData Provider 失败: {}", exc)

        # QMT 不可用时会继续回退到 AmazingData。为避免过早降级到 AkShare，
        # 在真正尝试 AmazingData 时按配置等待 Dask 代理就绪。
        if provider is None and self._provider_container is not None:
            try:
                from core.compute.dask_init_state import get_dask_init_manager_sync

                dask_manager = get_dask_init_manager_sync()
            except Exception as exc:  # pragma: no cover - defensive import
                dask_manager = None
                logger.debug("获取 Dask 初始化状态管理器失败: {}", exc)

            if dask_manager and not dask_manager.amazingdata_ready:
                timeouts_cfg = getattr(self._settings, "timeouts", None)
                wait_timeout = timeouts_cfg.dask.amazingdata_init if timeouts_cfg else 60.0
                logger.info(
                    "AmazingData Dask 代理未就绪，等待最多 {:.1f}s 后重试获取 Provider",
                    wait_timeout,
                )
                try:
                    ready = await dask_manager.wait_amazingdata_ready(timeout=wait_timeout)
                except Exception as exc:  # pragma: no cover - defensive wait
                    ready = False
                    logger.warning("等待 AmazingData Dask 代理时发生异常: {}", exc)

                if ready:
                    try:
                        if self._provider_container.has("amazingdata"):
                            provider = await self._provider_container.get("amazingdata")
                            logger.info("AmazingData Dask 代理就绪，已获取 ProviderContainer 实例")
                    except Exception as exc:
                        logger.warning("Dask 代理就绪后获取 AmazingData Provider 失败: {}", exc)
                else:
                    logger.warning("等待 AmazingData Dask 代理超时 ({:.1f}s)", wait_timeout)

        # 如果 ProviderContainer 中没有 AmazingData，不要回退到主进程加载 SDK
        # AmazingData SDK 不支持多进程同时登录，主进程加载会导致 Segfault
        # 让 orchestrator 使用其他 fallback 适配器（如 AkShare）
        if provider is None:
            raise RuntimeError(
                "AmazingData provider 未在 ProviderContainer 中注册，"
                "且主进程不应直接加载 SDK（会与 Dask Worker 冲突导致 Segfault）。"
                "请确保 Dask Worker 已启动，或使用其他数据源。"
            )

        service, cache_writer, pipeline, runner = create_realtime_streaming_pipeline(
            provider,
            realtime_config=realtime_cfg,
        )
        cache_reader = MarketDataCacheReader(cache_writer)

        # Port bundle currently仅暴露 stream + board 能力，后续会补充指标端口。
        board_source = build_board_source(provider)
        service.stock_list_fetcher = board_source.fetch_records
        ports = RealtimePortBundle(
            stream=service.registry.resolve_market_stream(),
            board=board_source,
        )

        capabilities = RealtimeAdapterCapabilities(
            streaming=True,
            snapshot=True,
            board_universe=True,
            capital_pulse=True,
            auction=True,
            order_imbalance=True,
        )

        adapter_name = adapter_alias or "amazingdata"
        return RealtimeRuntimeHandle(
            adapter_name=adapter_name,
            capabilities=capabilities,
            ports=ports,
            adapter=None,
            service=service,
            cache_writer=cache_writer,
            cache_reader=cache_reader,
            pipeline=pipeline,
            runner=runner,
            provider=provider,
        )

    async def _start_miniqmt(self, adapter_alias: str | None = None) -> RealtimeRuntimeHandle:
        """Start MiniQMT/xtquant adapter for realtime market data."""
        market_cfg = getattr(self._settings, "market_data", None)
        if market_cfg is None:
            raise RuntimeError("market_data config missing, cannot start miniqmt runtime")
        realtime_cfg = getattr(market_cfg, "realtime", None)
        if realtime_cfg is None:
            raise RuntimeError("market_data.realtime config missing")

        try:
            from core.adapters.market_data.miniqmt_polling_adapter import MiniQMTPollingAdapter

            adapter = MiniQMTPollingAdapter(name=adapter_alias or "miniqmt")
            return await self._start_polling_adapter(adapter)
        except ImportError as exc:
            logger.warning("MiniQMT adapter not available: {}", exc)
            raise RuntimeError(f"MiniQMT adapter import failed: {exc}") from exc

    async def _start_polling_adapter(self, adapter: RealtimeAdapter) -> RealtimeRuntimeHandle:
        market_cfg = getattr(self._settings, "market_data", None)
        realtime_cfg = getattr(market_cfg, "realtime", None) if market_cfg else None
        if realtime_cfg is None:
            raise RuntimeError("market_data.realtime config missing")

        bundle = await adapter.start()
        registry: MarketDataPortRegistry = PortBundleRegistry(bundle)
        board_fetcher = bundle.board.fetch_records if bundle.board else None

        calendar_loader = self._build_adapter_calendar_loader(adapter)

        service, cache_writer, pipeline, runner = create_realtime_streaming_pipeline(
            provider=None,
            registry=registry,
            board_fetcher=board_fetcher,
            data_source_name=adapter.name,
            realtime_config=realtime_cfg,
            enable_session_guard=True,
            calendar_loader=calendar_loader,
        )
        cache_reader = MarketDataCacheReader(cache_writer)

        return RealtimeRuntimeHandle(
            adapter_name=adapter.name,
            capabilities=adapter.capabilities,
            ports=bundle,
            adapter=adapter,
            service=service,
            cache_writer=cache_writer,
            cache_reader=cache_reader,
            pipeline=pipeline,
            runner=runner,
            provider=None,
        )

    @staticmethod
    def _bool_option(value: Any, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized or normalized == "auto":
                return default
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return bool(value)

    @staticmethod
    def _int_option(value: Any, *, default: int) -> int:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except TypeError, ValueError:
            return default

    async def probe_adapters(self) -> Dict[str, Dict[str, Any]]:
        """Probe all configured adapters without keeping runtime state."""

        results: Dict[str, Dict[str, Any]] = {}
        for adapter_name in self._adapter_sequence():
            try:
                handle = await self._start_adapter(adapter_name)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Realtime adapter probe failed for {}: {}", adapter_name, exc)
                results[adapter_name] = {
                    "status": "failed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                }
                continue

            if handle is None:
                continue

            results[handle.adapter_name] = {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self._teardown_handle(handle)

        if not results:
            results["<none>"] = {
                "status": "skipped",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": "no realtime adapters configured",
            }
        return results

    async def _teardown_handle(self, handle: RealtimeRuntimeHandle) -> None:
        """Stop adapter artifacts created during probe routines."""

        with contextlib.suppress(Exception):
            await handle.runner.stop()
        if handle.adapter:
            with contextlib.suppress(Exception):
                await handle.adapter.stop()
        with contextlib.suppress(Exception):
            await handle.cache_writer.close()

    async def _dispose_active_handle(self) -> None:
        """Tear down the currently active runtime handle."""

        if self._handle is None:
            return

        try:
            await self._teardown_handle(self._handle)
        finally:
            self._handle = None
            self._active_adapter = None


__all__ = ["RealtimeDataOrchestrator", "RealtimeRuntimeHandle"]
