"""Realtime data source orchestrator."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Tuple

from loguru import logger

from deepsearch.adapters.market_data.akshare_polling_adapter import AkSharePollingAdapter
from deepsearch.config.models.data_sources import RealtimeAdapterSpec
from deepsearch.config.settings import Settings
from deepsearch.infrastructure.providers.implementations.amazingdata.ports import (
    build_board_source,
)
from deepsearch.ports.market_data import (
    MarketDataPortRegistry,
    MarketStreamPort,
    RealtimeAdapter,
    RealtimeAdapterCapabilities,
    RealtimePortBundle,
)
from deepsearch.webui.api.providers import DataProviderFactory, DataSourceType
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

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._handle: RealtimeRuntimeHandle | None = None
        self._lock = asyncio.Lock()
        self._health: Dict[str, Dict[str, Any]] = {}
        self._active_adapter: str | None = None
        self._adapter_specs: Dict[str, RealtimeAdapterSpec]
        self._configured_order: Tuple[str, ...]
        self._adapter_specs, self._configured_order = self._load_realtime_specs()

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
        raise RuntimeError(
            f"no realtime adapter available; last_error={last_error}"
        )

    def _adapter_sequence(self) -> Iterable[str]:
        if self._configured_order:
            return self._configured_order
        ds_cfg = getattr(self._settings, "data_sources", None)
        if ds_cfg and ds_cfg.fallback_order:
            return ds_cfg.fallback_order
        return ("amazingdata", "akshare", "cloudflare")

    def _load_realtime_specs(self) -> tuple[Dict[str, RealtimeAdapterSpec], Tuple[str, ...]]:
        ds_cfg = getattr(self._settings, "data_sources", None)
        realtime_cfg = getattr(ds_cfg, "realtime", None) if ds_cfg else None
        if realtime_cfg is None or not getattr(realtime_cfg, "adapters", None):
            return {}, ()

        enabled_specs = [spec for spec in realtime_cfg.adapters if spec.enabled]
        if not enabled_specs:
            return {}, ()

        enabled_specs.sort(key=lambda spec: (spec.priority, spec.name.lower()))
        mapping: Dict[str, RealtimeAdapterSpec] = {}
        order: list[str] = []
        for spec in enabled_specs:
            mapping[spec.name.lower()] = spec
            order.append(spec.name)
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

        try:
            provider = await DataProviderFactory.get_provider_async(DataSourceType.AMAZINGDATA)
        except Exception as exc:
            logger.warning("Failed to initialize AmazingData provider: {}", exc)
            raise

        if provider is None:
            raise RuntimeError("AmazingData provider unavailable")

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
            from deepsearch.adapters.market_data.miniqmt_polling_adapter import MiniQMTPollingAdapter
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

        service, cache_writer, pipeline, runner = create_realtime_streaming_pipeline(
            provider=None,
            registry=registry,
            board_fetcher=board_fetcher,
            data_source_name=adapter.name,
            realtime_config=realtime_cfg,
            enable_session_guard=False,
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
        except (TypeError, ValueError):
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
