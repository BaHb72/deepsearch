"""On-demand fallback fetcher for market data modules."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Tuple

from core.config.models.market_data import (
    MarketDataConfig,
    MarketModuleConfig,
    MarketModuleFallbackConfig,
)
from core.config.settings import Settings
from core.infrastructure.providers.container import ProviderContainer
from core.ports.market_data import CapitalPulseQuery
from loguru import logger

from .trading_guard import PhaseState

if TYPE_CHECKING:
    from core.application.market_data.orchestrator import (
        RealtimeDataOrchestrator,
        RealtimeRuntimeHandle,
    )


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class FallbackFetchResult:
    """Fetch result metadata returned to API layer."""

    module: str
    source: str
    status: str
    detail: Dict[str, Any] | None = None


class _ModuleRunError(RuntimeError):
    """携带实际运行句柄的模块执行异常。"""

    def __init__(self, *, handle: RealtimeRuntimeHandle, cause: Exception) -> None:
        super().__init__(str(cause))
        self.handle = handle


class ModuleFallbackManager:
    """Coordinates module-level fallback fetches without disturbing primary runtime."""

    def __init__(
        self,
        settings: Settings,
        *,
        orchestrator: "RealtimeDataOrchestrator | None" = None,
        provider_container: ProviderContainer | None = None,
    ) -> None:
        from core.application.market_data.orchestrator import RealtimeDataOrchestrator

        self._settings = settings
        self._orchestrator = orchestrator or RealtimeDataOrchestrator(
            settings,
            provider_container=provider_container,
        )
        self._locks: Dict[Tuple[str, str], asyncio.Lock] = {}
        self._source_locks: Dict[str, asyncio.Lock] = {}
        self._source_run_locks: Dict[str, asyncio.Lock] = {}
        self._source_handles: Dict[str, RealtimeRuntimeHandle] = {}
        self._source_last_success: Dict[str, datetime] = {}
        self._last_fetch: Dict[Tuple[str, str], datetime] = {}

    async def fetch_once(
        self,
        module: str,
        source: str,
        *,
        phase: PhaseState | str | None = None,
    ) -> FallbackFetchResult:
        """Trigger a single pipeline run for the given module/source combination."""

        module_name = self._normalize_identifier(module)
        source_name = self._normalize_identifier(source)
        module_cfg = self._require_module_config(module_name)
        rule = self._locate_rule(module_name, module_cfg, source_name)

        key = (module_name, source_name)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            remaining = self._remaining_interval(rule, self._last_fetch.get(key))
            if remaining is not None:
                next_allowed = datetime.now(timezone.utc) + timedelta(seconds=remaining)
                detail = {
                    "message": "fallback fetch throttled",
                    "nextAllowedAt": next_allowed.isoformat().replace("+00:00", "Z"),
                    "retryAfterSeconds": round(remaining, 2),
                }
                return FallbackFetchResult(
                    module=module_name, source=source_name, status="throttled", detail=detail
                )

            handle = await self._acquire_source_handle(source_name)
            if handle is None:
                return FallbackFetchResult(
                    module=module_name,
                    source=source_name,
                    status="error",
                    detail={"message": "adapter unavailable"},
                )

            phase_state = self._resolve_phase_state(phase)
            run_failed = False
            failed_handle: RealtimeRuntimeHandle | None = handle
            try:
                run_meta, active_handle = await self._run_module_once_with_source_lock(
                    source_name=source_name,
                    module_name=module_name,
                    handle=handle,
                    phase_state=phase_state,
                )
                success_at = datetime.now(timezone.utc)
                self._last_fetch[key] = success_at
                self._source_last_success[source_name] = success_at
                detail = {
                    "timestamp": _iso_now(),
                    "writer_source": active_handle.cache_writer.data_source,
                    "boards": list(getattr(active_handle.pipeline, "boards", ())),
                    "phase": phase_state.value if phase_state else PhaseState.CONTINUOUS.value,
                }
                if run_meta:
                    detail.update(run_meta)
                logger.info(
                    "模块 fallback 拉取完成: module={} source={} writer_source={}",
                    module_name,
                    source_name,
                    active_handle.cache_writer.data_source,
                )
                return FallbackFetchResult(
                    module=module_name, source=source_name, status="ok", detail=detail
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                if isinstance(exc, _ModuleRunError):
                    failed_handle = exc.handle
                    underlying_exc = exc.__cause__ if exc.__cause__ is not None else exc
                else:
                    underlying_exc = exc
                logger.error(
                    "Fallback fetch failed for module={} source={}: {}",
                    module_name,
                    source_name,
                    underlying_exc,
                )
                run_failed = True
                return FallbackFetchResult(
                    module=module_name,
                    source=source_name,
                    status="error",
                    detail={"message": str(underlying_exc)},
                )
            finally:
                if run_failed:
                    await self._invalidate_source_handle(source_name, expected_handle=failed_handle)

    async def shutdown(self) -> None:
        """Release warmed fallback handles."""

        handles = list(self._source_handles.items())
        self._source_handles.clear()
        self._source_last_success.clear()
        self._source_locks.clear()
        self._source_run_locks.clear()
        for source_name, handle in handles:
            await self._safe_teardown_handle(source_name, handle)

    def is_source_warm(self, source: str) -> bool:
        """Return whether a fallback source already has a warmed runtime handle."""

        normalized = self._normalize_identifier(source)
        return normalized in self._source_handles

    def is_source_ready(self, source: str) -> bool:
        """Return whether a source has at least one successful fallback run."""

        normalized = self._normalize_identifier(source)
        return normalized in self._source_last_success

    def _remaining_interval(
        self,
        rule: MarketModuleFallbackConfig,
        last: datetime | None,
    ) -> float | None:
        interval = rule.min_interval_seconds
        if interval <= 0 or last is None:
            return None
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        remaining = interval - elapsed
        return remaining if remaining > 0 else None

    def _require_module_config(self, module: str) -> MarketModuleConfig:
        config = self._market_config().modules.get(module)
        if config is None:
            raise ValueError(f"module {module} is not configured in market_data.modules")
        return config

    def _market_config(self) -> MarketDataConfig:
        if not self._settings.market_data:
            raise ValueError("market_data configuration is missing")
        return self._settings.market_data

    def _locate_rule(
        self,
        module_name: str,
        module_cfg: MarketModuleConfig,
        source: str,
    ) -> MarketModuleFallbackConfig:
        normalized_source = self._normalize_identifier(source)
        for rule in module_cfg.fallbacks:
            if self._normalize_identifier(rule.source) == normalized_source:
                return rule
        raise ValueError(f"source {source} is not allowed for module {module_name}")

    async def _start_adapter(self, source: str) -> RealtimeRuntimeHandle | None:
        try:
            handle = await self._orchestrator._start_adapter(source)
            return handle
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Unable to start fallback adapter {}: {}", source, exc)
            return None

    async def _acquire_source_handle(self, source: str) -> RealtimeRuntimeHandle | None:
        normalized_source = self._normalize_identifier(source)
        handle = self._source_handles.get(normalized_source)
        if handle is not None:
            return handle

        source_lock = self._source_locks.setdefault(normalized_source, asyncio.Lock())
        async with source_lock:
            handle = self._source_handles.get(normalized_source)
            if handle is not None:
                return handle
            handle = await self._start_adapter(normalized_source)
            if handle is not None:
                await self._prepare_source_handle(normalized_source, handle)
                self._source_handles[normalized_source] = handle
            return handle

    async def _prepare_source_handle(self, source: str, handle: RealtimeRuntimeHandle) -> None:
        """在 fallback 句柄首次创建时预热缓存，避免 run_once 首轮走重刷新。"""
        try:
            board_snapshot, _ = await handle.cache_reader.fetch_board_universe(source=source)
            if not board_snapshot:
                board_snapshot, _ = await handle.cache_reader.fetch_board_universe()
            if not board_snapshot:
                return
            handle.service.board_universe.load_snapshot(board_snapshot)
            logger.debug(
                "fallback 句柄预热板块缓存完成 source={} boards={}",
                source,
                len(board_snapshot),
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug("fallback 句柄预热板块缓存失败 source={} error={}", source, exc)

    async def _run_module_once(
        self,
        *,
        module_name: str,
        handle: RealtimeRuntimeHandle,
        phase_state: PhaseState | None,
    ) -> Dict[str, Any] | None:
        normalized_module = self._normalize_identifier(module_name)
        if normalized_module in {"strength", "board_overview"}:
            pipeline = getattr(handle, "pipeline", None)
            service = getattr(handle, "service", None)
            cache_writer = getattr(handle, "cache_writer", None)
            has_capital_runtime = (
                pipeline is not None
                and hasattr(pipeline, "capital_windows")
                and hasattr(pipeline, "capital_limit")
                and hasattr(pipeline, "boards")
                and service is not None
                and hasattr(service, "compute_capital_pulse")
                and cache_writer is not None
                and hasattr(cache_writer, "write_capital_pulse")
            )
            if not has_capital_runtime:
                await handle.pipeline.run_once(phase_state)
                return {"run_mode": "pipeline-run-once"}
            return await self._run_capital_module_once(handle=handle, phase_state=phase_state)
        await handle.pipeline.run_once(phase_state)
        return None

    async def _run_module_once_with_source_lock(
        self,
        *,
        source_name: str,
        module_name: str,
        handle: RealtimeRuntimeHandle,
        phase_state: PhaseState | None,
    ) -> tuple[Dict[str, Any] | None, RealtimeRuntimeHandle]:
        source_lock = self._source_run_locks.setdefault(
            self._normalize_identifier(source_name),
            asyncio.Lock(),
        )
        async with source_lock:
            active_handle = await self._resolve_handle_for_run(source_name, handle)
            if active_handle is None:
                raise RuntimeError("adapter unavailable")
            try:
                run_meta = await self._run_module_once(
                    module_name=module_name,
                    handle=active_handle,
                    phase_state=phase_state,
                )
            except Exception as exc:
                raise _ModuleRunError(handle=active_handle, cause=exc) from exc
            return run_meta, active_handle

    async def _resolve_handle_for_run(
        self,
        source: str,
        expected_handle: RealtimeRuntimeHandle | None,
    ) -> RealtimeRuntimeHandle | None:
        normalized_source = self._normalize_identifier(source)
        source_lock = self._source_locks.setdefault(normalized_source, asyncio.Lock())
        async with source_lock:
            current = self._source_handles.get(normalized_source)
            if current is expected_handle and current is not None:
                return current
            if current is not None:
                return current
        return await self._acquire_source_handle(normalized_source)

    async def _run_capital_module_once(
        self,
        *,
        handle: RealtimeRuntimeHandle,
        phase_state: PhaseState | None,
    ) -> Dict[str, Any]:
        """仅执行资金脉冲路径，避免 fallback 触发整条流水线造成超时。"""
        effective_phase = phase_state or PhaseState.CONTINUOUS
        if effective_phase in {PhaseState.OFF_DAY, PhaseState.NO_TRADE}:
            bootstrap_ingest = False
            if effective_phase == PhaseState.NO_TRADE and not self._has_cached_snapshots(handle):
                # 盘后冷启动需要先补一轮 ingest，确保 summary 计算有可用快照基线。
                await handle.service.ensure_subscription(handle.pipeline.boards)
                await handle.service.ingest_from_stream()
                bootstrap_ingest = True

            # 盘后/休市不主动触发全市场快照抓取，优先复用已有缓存与内存状态，
            # 避免 query_snapshot 大批量请求导致 fallback 长时间阻塞。
            capital_query = CapitalPulseQuery(
                boards=tuple(handle.pipeline.boards),
                windows=tuple(handle.pipeline.capital_windows),
                limit=handle.pipeline.capital_limit,
                summary_mode=True,
            )
            capital_entries = await handle.service.compute_capital_pulse(capital_query)
            if capital_entries:
                await handle.cache_writer.write_capital_pulse(
                    capital_entries,
                    limit=handle.pipeline.capital_limit,
                )
            return {
                "run_mode": (
                    "capital-summary-after-bootstrap"
                    if bootstrap_ingest
                    else "capital-summary-cache-only"
                ),
                "capital_entries": len(capital_entries),
                "skipped_ingest": not bootstrap_ingest,
                "bootstrap_ingest": bootstrap_ingest,
            }

        await handle.service.ensure_subscription(handle.pipeline.boards)
        await handle.service.ingest_from_stream()
        capital_query = CapitalPulseQuery(
            boards=tuple(handle.pipeline.boards),
            windows=tuple(handle.pipeline.capital_windows),
            limit=handle.pipeline.capital_limit,
            summary_mode=effective_phase == PhaseState.NO_TRADE,
        )
        capital_entries = await handle.service.compute_capital_pulse(capital_query)
        await handle.cache_writer.write_capital_pulse(
            capital_entries,
            limit=handle.pipeline.capital_limit,
        )
        return {
            "run_mode": "capital-only",
            "capital_entries": len(capital_entries),
        }

    @staticmethod
    def _has_cached_snapshots(handle: RealtimeRuntimeHandle) -> bool:
        service = getattr(handle, "service", None)
        snapshot_buffer = getattr(service, "snapshot_buffer", None) if service else None
        latest_snapshot = None
        if snapshot_buffer is not None and hasattr(snapshot_buffer, "latest_snapshot"):
            try:
                latest_snapshot = snapshot_buffer.latest_snapshot()
            except Exception:  # pragma: no cover - defensive fallback
                latest_snapshot = None
        return latest_snapshot is not None

    async def _invalidate_source_handle(
        self,
        source: str,
        *,
        expected_handle: RealtimeRuntimeHandle | None = None,
    ) -> None:
        normalized_source = self._normalize_identifier(source)
        source_run_lock = self._source_run_locks.setdefault(normalized_source, asyncio.Lock())
        source_lock = self._source_locks.setdefault(normalized_source, asyncio.Lock())
        handle_to_teardown: RealtimeRuntimeHandle | None = None

        async with source_run_lock:
            async with source_lock:
                current = self._source_handles.get(normalized_source)
                if current is None:
                    return
                if expected_handle is not None and current is not expected_handle:
                    return
                handle_to_teardown = self._source_handles.pop(normalized_source, None)
                self._source_last_success.pop(normalized_source, None)

        if handle_to_teardown is not None:
            await self._safe_teardown_handle(normalized_source, handle_to_teardown)

    async def _safe_teardown_handle(
        self,
        source: str,
        handle: RealtimeRuntimeHandle,
    ) -> None:
        try:
            await self._orchestrator._teardown_handle(handle)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.debug("Teardown fallback adapter {} failed: {}", source, exc)

    @staticmethod
    def _normalize_identifier(value: str) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def _resolve_phase_state(phase: PhaseState | str | None) -> PhaseState | None:
        if isinstance(phase, PhaseState):
            return phase
        if not isinstance(phase, str):
            return None
        normalized = phase.strip().lower()
        mapping = {
            "off_day": PhaseState.OFF_DAY,
            "no_trade": PhaseState.NO_TRADE,
            "auction": PhaseState.AUCTION,
            "continuous": PhaseState.CONTINUOUS,
        }
        return mapping.get(normalized)


__all__ = ["ModuleFallbackManager", "FallbackFetchResult"]
