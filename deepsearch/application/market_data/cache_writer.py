"""Cache writer for market data indicators."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from inspect import iscoroutinefunction
from typing import Any, Awaitable, Callable, Dict, Mapping, MutableMapping, Sequence, cast

try:
    import redis as aioredis
    from redis import Redis as AsyncRedis
except Exception:  # pragma: no cover - optional import fallback
    aioredis = None  # type: ignore
    AsyncRedis = None  # type: ignore

from deepsearch.ports.market_data import (
    AuctionQualityEntry,
    CapitalPulseEntry,
    OrderImbalanceEntry,
    WindowSpec,
)


@dataclass(slots=True)
class MarketDataCacheWriter:
    """Persist real-time indicator snapshots to Redis (with in-memory fallback)."""

    redis: AsyncRedis | None = None
    data_source: str = "amazingdata"
    namespace: str = "market"
    strength_ttl: int = 180
    imbalance_ttl: int = 180
    auction_ttl: int = 180
    max_strength_entries: int = 50
    board_universe_ttl: int = 900
    _memory_cache: MutableMapping[str, Any] = field(default_factory=dict, init=False)

    @classmethod
    def from_url(cls, url: str, *, data_source: str = "amazingdata") -> "MarketDataCacheWriter":
        if aioredis is None:
            raise RuntimeError("redis is not available")
        from_url = getattr(aioredis, "from_url", None)
        if from_url is None:
            raise RuntimeError("redis.from_url is not available")
        client = cast(AsyncRedis, from_url(url, encoding="utf-8", decode_responses=False))
        return cls(redis=client, data_source=data_source)

    async def close(self) -> None:
        if self.redis is not None:
            close_method = getattr(self.redis, "close", None)
            if close_method is None:
                return
            if iscoroutinefunction(close_method):
                await cast(Callable[[], Awaitable[None]], close_method)()
            else:  # 同步 redis 客户端
                await asyncio.to_thread(cast(Callable[[], object], close_method))

    async def write_capital_pulse(
            self,
            entries: Sequence[CapitalPulseEntry],
            *,
            limit: int | None = None,
            module: str = "strength",
            source: str | None = None,
    ) -> None:
        limit = limit or self.max_strength_entries
        aggregated: Dict[str, list[Dict[str, Any]]] = {}
        window_as_of: Dict[str, str] = {}
        module_name = module or "strength"
        normalized_source = self._normalize_source(source)
        for entry in entries:
            entry_dict = self._serialize_capital_entry(entry)
            entry_dict["as_of"] = entry_dict["ts"]
            board_key = self._build_key(module_name, entry.board, entry.window.name, source=normalized_source)
            await self._set(board_key, entry_dict, ttl=self.strength_ttl)
            window_bucket = aggregated.setdefault(entry.window.name, [])
            window_bucket.append(entry_dict)
            existing = window_as_of.get(entry.window.name)
            if not existing or entry_dict["ts"] > existing:
                window_as_of[entry.window.name] = entry_dict["ts"]

        for window_name, items in aggregated.items():
            sorted_items = sorted(items, key=lambda x: x["speed_per_min"], reverse=True)
            key = self._build_key(module_name, window_name, source=normalized_source)
            payload = {
                "window": window_name,
                "entries": sorted_items[:limit],
            }
            as_of = window_as_of.get(window_name)
            if as_of:
                payload["as_of"] = as_of
            await self._set(key, payload, ttl=self.strength_ttl)

    async def write_order_imbalance(
            self,
            entries: Sequence[OrderImbalanceEntry],
            *,
            window: WindowSpec,
            limit: int,
            module: str = "order_imbalance",
            source: str | None = None,
    ) -> None:
        serialized = [self._serialize_imbalance_entry(entry) for entry in entries]
        serialized.sort(key=lambda x: abs(x["obi"]), reverse=True)
        key = self._build_key(module, window.name, source=self._normalize_source(source))
        payload: Dict[str, Any] = {
            "window": window.name,
            "entries": serialized[:limit],
        }
        as_of = self._resolve_latest_ts(serialized)
        if as_of:
            payload["as_of"] = as_of
        await self._set(key, payload, ttl=self.imbalance_ttl)

    async def write_auction_quality(
            self,
            entries: Sequence[AuctionQualityEntry],
            *,
            module: str = "auction_quality",
            source: str | None = None,
    ) -> None:
        normalized_source = self._normalize_source(source)
        for entry in entries:
            data = self._serialize_auction_entry(entry)
            data["as_of"] = data["ts"]
            key = self._build_key(module, entry.board, source=normalized_source)
            await self._set(key, data, ttl=self.auction_ttl)

    async def write_board_universe(
            self,
            mapping: Mapping[str, Sequence[str]],
            *,
            ttl: int | None = None,
            source: str | None = None,
    ) -> None:
        serializable = {
            str(board): [str(code) for code in codes if code]
            for board, codes in mapping.items()
        }
        effective_ttl = ttl or self.board_universe_ttl
        key = self._build_key("boards", source=self._normalize_source(source or self.data_source))
        await self._set(key, {"boards": serializable}, ttl=effective_ttl)

    async def _set(self, key: str, value: Mapping[str, Any], *, ttl: int) -> None:
        envelope = self._wrap_payload(value, ttl)
        payload = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        if self.redis is not None:
            try:
                set_method = getattr(self.redis, "set")
                if iscoroutinefunction(set_method):
                    await cast(Callable[..., Awaitable[object]], set_method)(key, payload, ex=ttl)
                else:  # 同步 redis 客户端
                    await asyncio.to_thread(cast(Callable[..., object], set_method), key, payload, ex=ttl)
                return
            except Exception as exc:  # pragma: no cover - fallback path
                # Log through standard logger to avoid dependency cycle
                from loguru import logger

                logger.warning("Redis write failed for {}: {}", key, exc)
        # In-memory fallback for tests or when Redis unavailable
        self._memory_cache[key] = envelope
    @staticmethod
    def _serialize_capital_entry(entry: CapitalPulseEntry) -> Dict[str, Any]:
        return {
            "board": entry.board,
            "window": entry.window.name,
            "window_seconds": entry.window.duration.total_seconds(),
            "amount_total": MarketDataCacheWriter._to_numeric(entry.amount_total),
            "speed_per_min": MarketDataCacheWriter._to_numeric(entry.speed_per_min),
            "accel_per_min2": MarketDataCacheWriter._to_numeric(entry.accel_per_min2),
            "ts": entry.ts.isoformat(),
            "data_source": entry.data_source,
        }

    @staticmethod
    def _serialize_imbalance_entry(entry: OrderImbalanceEntry) -> Dict[str, Any]:
        return {
            "code": entry.code,
            "name": entry.name,
            "obi": MarketDataCacheWriter._to_numeric(entry.obi),
            "eis": MarketDataCacheWriter._to_numeric(entry.eis),
            "ntm": MarketDataCacheWriter._to_numeric(entry.ntm),
            "ts": entry.ts.isoformat(),
            "data_source": entry.data_source,
        }

    @staticmethod
    def _serialize_auction_entry(entry: AuctionQualityEntry) -> Dict[str, Any]:
        return {
            "board": entry.board,
            "amount_acc": MarketDataCacheWriter._to_numeric(entry.amount_acc),
            "volume_acc": MarketDataCacheWriter._to_numeric(entry.volume_acc),
            "speed_per_min": MarketDataCacheWriter._to_numeric(entry.speed_per_min),
            "price_stability": MarketDataCacheWriter._to_numeric(entry.price_stability),
            "ts": entry.ts.isoformat(),
            "data_source": entry.data_source,
        }

    @staticmethod
    def _to_numeric(value: Any) -> float | int | None:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (float, int)):
            return value
        return None

    def dump_memory_cache(self) -> Mapping[str, Any]:
        """Expose in-memory fallback (mainly for tests)."""

        return dict(self._memory_cache)

    def _normalize_source(self, source: str | None = None) -> str:
        candidate = (source or self.data_source or "").strip().lower()
        return candidate or "default"

    def _build_key(self, module: str, *parts: str, source: str | None = None) -> str:
        normalized_module = (module or "default").strip() or "default"
        normalized_source = self._normalize_source(source)
        cleaned_parts = [str(part) for part in parts if str(part)]
        return ":".join([self.namespace, normalized_module, normalized_source, *cleaned_parts])

    @staticmethod
    def _resolve_latest_ts(entries: Sequence[Mapping[str, Any]]) -> str | None:
        latest: str | None = None
        for entry in entries:
            ts_value = str(entry.get("ts") or entry.get("as_of") or "")
            if not ts_value:
                continue
            if not latest or ts_value > latest:
                latest = ts_value
        return latest

    @staticmethod
    def _wrap_payload(value: Mapping[str, Any], ttl: int) -> Dict[str, Any]:
        cached_at = datetime.now(timezone.utc)
        expires_at = cached_at + timedelta(seconds=max(ttl, 0))
        payload = dict(value)
        return {
            "payload": payload,
            "__meta": {
                "cached_at": cached_at.isoformat().replace("+00:00", "Z"),
                "ttl": ttl,
                "expires_at": expires_at.isoformat().replace("+00:00", "Z")
                if ttl > 0
                else None,
            },
        }
