"""On-demand fallback fetcher for market data modules."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple

from loguru import logger

from deepsearch.config.models.market_data import (
    MarketDataConfig,
    MarketModuleConfig,
    MarketModuleFallbackConfig,
)
from deepsearch.config.settings import Settings
from deepsearch.application.market_data.orchestrator import RealtimeDataOrchestrator, RealtimeRuntimeHandle


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class FallbackFetchResult:
    """Fetch result metadata returned to API layer."""

    module: str
    source: str
    status: str
    detail: Dict[str, Any] | None = None


class ModuleFallbackManager:
    """Coordinates module-level fallback fetches without disturbing primary runtime."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._orchestrator = RealtimeDataOrchestrator(settings)
        self._locks: Dict[Tuple[str, str], asyncio.Lock] = {}
        self._last_fetch: Dict[Tuple[str, str], datetime] = {}

    async def fetch_once(self, module: str, source: str) -> FallbackFetchResult:
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
                return FallbackFetchResult(module=module_name, source=source_name, status="throttled", detail=detail)

            handle = await self._start_adapter(source_name)
            if handle is None:
                return FallbackFetchResult(
                    module=module_name,
                    source=source_name,
                    status="error",
                    detail={"message": "adapter unavailable"},
                )

            try:
                await handle.pipeline.run_once()
                self._last_fetch[key] = datetime.now(timezone.utc)
                detail = {
                    "timestamp": _iso_now(),
                    "writer_source": handle.cache_writer.data_source,
                    "boards": list(getattr(handle.pipeline, "boards", ())),
                }
                return FallbackFetchResult(module=module_name, source=source_name, status="ok", detail=detail)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Fallback fetch failed for module={} source={}: {}", module_name, source_name, exc)
                return FallbackFetchResult(
                    module=module_name,
                    source=source_name,
                    status="error",
                    detail={"message": str(exc)},
                )
            finally:
                await self._orchestrator._teardown_handle(handle)

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

    @staticmethod
    def _normalize_identifier(value: str) -> str:
        return (value or "").strip().lower()


__all__ = ["ModuleFallbackManager", "FallbackFetchResult"]
