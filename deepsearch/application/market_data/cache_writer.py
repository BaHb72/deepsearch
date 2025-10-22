"""Cache writer for market data indicators."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Mapping, MutableMapping, Sequence

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
    strength_ttl: int = 180
    imbalance_ttl: int = 180
    auction_ttl: int = 180
    max_strength_entries: int = 50
    _memory_cache: MutableMapping[str, Any] = field(default_factory=dict, init=False)

    @classmethod
    def from_url(cls, url: str) -> "MarketDataCacheWriter":
        if aioredis is None:
            raise RuntimeError("redis is not available")
        client = aioredis.from_url(url, encoding="utf-8", decode_responses=False)
        return cls(redis=client)

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.close()  # type: ignore[arg-type]

    async def write_capital_pulse(
            self,
            entries: Sequence[CapitalPulseEntry],
            *,
            limit: int | None = None,
    ) -> None:
        limit = limit or self.max_strength_entries
        aggregated: Dict[str, list[Dict[str, Any]]] = {}
        for entry in entries:
            entry_dict = self._serialize_capital_entry(entry)
            board_key = f"market:strength:{entry.board}:{entry.window.name}"
            await self._set(board_key, entry_dict, ttl=self.strength_ttl)
            window_bucket = aggregated.setdefault(entry.window.name, [])
            window_bucket.append(entry_dict)

        for window_name, items in aggregated.items():
            sorted_items = sorted(items, key=lambda x: x["speed_per_min"], reverse=True)
            key = f"market:strength:{window_name}"
            await self._set(key, {"window": window_name, "entries": sorted_items[:limit]}, ttl=self.strength_ttl)

    async def write_order_imbalance(
            self,
            entries: Sequence[OrderImbalanceEntry],
            *,
            window: WindowSpec,
            limit: int,
    ) -> None:
        serialized = [self._serialize_imbalance_entry(entry) for entry in entries]
        serialized.sort(key=lambda x: abs(x["obi"]), reverse=True)
        key = f"market:order-imbalance:{window.name}"
        await self._set(key, {"window": window.name, "entries": serialized[:limit]}, ttl=self.imbalance_ttl)

    async def write_auction_quality(
            self,
            entries: Sequence[AuctionQualityEntry],
    ) -> None:
        for entry in entries:
            data = self._serialize_auction_entry(entry)
            key = f"market:auction:{entry.board}"
            await self._set(key, data, ttl=self.auction_ttl)

    async def _set(self, key: str, value: Mapping[str, Any], *, ttl: int) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        if self.redis is not None:
            try:
                await self.redis.set(key, payload, ex=ttl)
                return
            except Exception as exc:  # pragma: no cover - fallback path
                # Log through standard logger to avoid dependency cycle
                from loguru import logger

                logger.warning("Redis write failed for %s: %s", key, exc)
        # In-memory fallback for tests or when Redis unavailable
        self._memory_cache[key] = {"value": value, "expires_in": ttl}

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
