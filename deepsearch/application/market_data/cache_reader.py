"""Cache reader utilities for market data realtime snapshots."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping, Sequence, cast

from loguru import logger

from .cache_writer import MarketDataCacheWriter


def _decode_json(raw: Any) -> Mapping[str, Any] | None:
    """Best-effort JSON decoder that accepts bytes/str/mapping."""

    if raw is None:
        return None

    if isinstance(raw, Mapping):
        return raw

    payload: str | None = None
    if isinstance(raw, bytes):
        try:
            payload = raw.decode("utf-8")
        except Exception:
            payload = raw.decode("utf-8", errors="ignore")
    elif isinstance(raw, str):
        payload = raw

    if not payload:
        return None

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        logger.debug("无法解析 JSON: {}", payload)
        return None

    if isinstance(parsed, Mapping):
        return cast(Mapping[str, Any], parsed)
    return None


@dataclass(slots=True)
class MarketDataCacheReader:
    """Read realtime market data aggregates from Redis or in-memory fallback."""

    writer: MarketDataCacheWriter

    @dataclass(slots=True)
    class CacheEnvelope:
        payload: Mapping[str, Any]
        cached_at: datetime | None
        ttl: int | None
        expires_at: datetime | None

        def resolve_as_of(self) -> datetime | None:
            value = self.payload.get("as_of") or self.payload.get("asOf")
            candidate = MarketDataCacheReader._parse_iso_datetime(value)
            if candidate:
                return candidate

            entries = self.payload.get("entries")
            if isinstance(entries, Sequence):
                latest: datetime | None = None
                for entry in entries:
                    if not isinstance(entry, Mapping):
                        continue
                    ts_candidate = MarketDataCacheReader._parse_iso_datetime(
                        entry.get("as_of") or entry.get("asOf") or entry.get("ts")
                    )
                    if ts_candidate and (latest is None or ts_candidate > latest):
                        latest = ts_candidate
                if latest:
                    return latest

            if "ts" in self.payload:
                return MarketDataCacheReader._parse_iso_datetime(self.payload.get("ts"))
            return None

        def is_stale(self, reference: datetime | None = None) -> bool:
            if self.expires_at is None:
                return False
            ref = reference or datetime.now(timezone.utc)
            return ref >= self.expires_at

    @dataclass(slots=True)
    class CacheResult:
        items: list[Mapping[str, Any]]
        as_of: str | None
        stale: bool
        cached_at: str | None
        expires_at: str | None

    async def fetch_strength(
        self,
        windows: Sequence[str],
        *,
        boards: Sequence[str] | None = None,
        limit: int | None = None,
        module: str = "strength",
        source: str | None = None,
    ) -> CacheResult:
        """Load capital strength aggregations for specified windows."""

        board_set = {board for board in (boards or ()) if board}
        items: list[Mapping[str, Any]] = []
        envelopes: list[MarketDataCacheReader.CacheEnvelope] = []
        module_name = module or "strength"
        for window in windows:
            envelope = await self._get_envelope(self._build_key(module_name, window, source=source))
            if not envelope:
                legacy_key = self._legacy_key(module_name, window)
                envelope = await self._get_envelope(legacy_key)
            if not envelope:
                continue
            envelopes.append(envelope)
            payload = envelope.payload
            entries = list(payload.get("entries", []))
            if board_set:
                entries = [entry for entry in entries if entry.get("board") in board_set]
            if limit and limit > 0:
                entries = entries[:limit]
            items.extend(entries)
        return self._build_result(items, envelopes)

    async def fetch_order_imbalance(
        self,
        window: str,
        *,
        limit: int | None = None,
        module: str = "order_imbalance",
        source: str | None = None,
    ) -> CacheResult:
        """Load order imbalance rankings for a window."""

        module_name = module or "order_imbalance"
        envelope = await self._get_envelope(self._build_key(module_name, window, source=source))
        if not envelope:
            legacy_key = self._legacy_key(module_name, window)
            envelope = await self._get_envelope(legacy_key)
        if not envelope:
            return self._build_result([], [])

        payload = envelope.payload
        entries = list(payload.get("entries", []))
        if limit and limit > 0:
            entries = entries[:limit]
        return self._build_result(entries, [envelope])

    async def fetch_auction_quality(
        self,
        boards: Sequence[str],
        *,
        module: str = "auction_quality",
        source: str | None = None,
    ) -> CacheResult:
        """Load auction quality snapshot per board."""

        results: list[Mapping[str, Any]] = []
        envelopes: list[MarketDataCacheReader.CacheEnvelope] = []
        module_name = module or "auction_quality"
        for board in boards:
            if not board:
                continue
            envelope = await self._get_envelope(self._build_key(module_name, board, source=source))
            if not envelope:
                legacy_key = self._legacy_key("auction", board)
                envelope = await self._get_envelope(legacy_key)
            if envelope:
                envelopes.append(envelope)
                results.append(envelope.payload)
        return self._build_result(results, envelopes)

    async def fetch_board_universe(
        self,
        *,
        module: str = "boards",
        source: str | None = None,
    ) -> tuple[dict[str, tuple[str, ...]], CacheEnvelope | None]:
        """Load cached board membership snapshot if available."""

        envelope = await self._get_envelope(self._build_key(module or "boards", source=source))
        if not envelope:
            legacy_key = self._legacy_key(module or "boards")
            envelope = await self._get_envelope(legacy_key)
        if not envelope:
            return {}, None

        payload = envelope.payload
        boards_raw = payload.get("boards")
        snapshot: dict[str, tuple[str, ...]] = {}
        if isinstance(boards_raw, Mapping):
            for board, codes in boards_raw.items():
                if not board:
                    continue
                normalized: list[str] = []
                if isinstance(codes, Sequence):
                    for code in codes:
                        if not code:
                            continue
                        normalized_code = str(code).upper().strip()
                        if normalized_code:
                            normalized.append(normalized_code)
                if normalized:
                    snapshot[str(board)] = tuple(sorted(set(normalized)))
        return snapshot, envelope

    async def _get_envelope(self, key: str) -> CacheEnvelope | None:
        """Retrieve cached entry metadata + payload from Redis with in-memory fallback."""

        redis_client = getattr(self.writer, "redis", None)
        if redis_client is not None:
            try:
                raw_value = redis_client.get(key)
                if asyncio.iscoroutine(raw_value):
                    raw_value = await raw_value
                payload = _decode_json(raw_value)
                if payload is not None:
                    return self._to_envelope(payload)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.debug("读取 Redis key {} 失败: {}", key, exc)

        fallback = self._get_memory_entry(key)
        if fallback is not None:
            return fallback

        return None

    def _get_memory_entry(self, key: str) -> CacheEnvelope | None:
        """Read entry from writer in-memory cache."""

        cache: MutableMapping[str, Any] = dict(self.writer.dump_memory_cache())
        if not cache:
            return None

        entry = cache.get(key)
        if entry is None:
            return None

        if isinstance(entry, Mapping):
            return self._to_envelope(entry)

        decoded = _decode_json(entry)
        if decoded is not None:
            return self._to_envelope(decoded)

        return None

    def _to_envelope(self, data: Mapping[str, Any]) -> CacheEnvelope:
        if "__meta" in data and isinstance(data["__meta"], Mapping) and "payload" in data:
            payload = data.get("payload")
            meta = data.get("__meta") or {}
        else:
            payload = data
            meta = {}

        if not isinstance(payload, Mapping):
            payload = {}

        cached_at = self._parse_iso_datetime(meta.get("cached_at"))
        expires_at = self._parse_iso_datetime(meta.get("expires_at"))
        ttl_raw = meta.get("ttl")
        ttl_value: int | None
        try:
            ttl_value = int(ttl_raw) if ttl_raw is not None else None
        except (TypeError, ValueError):
            ttl_value = None

        return self.CacheEnvelope(
            payload=payload,
            cached_at=cached_at,
            ttl=ttl_value,
            expires_at=expires_at,
        )

    def _build_result(
        self,
        items: list[Mapping[str, Any]],
        envelopes: Sequence[CacheEnvelope],
    ) -> CacheResult:
        now = datetime.now(timezone.utc)
        as_of_dt: datetime | None = None
        cached_latest: datetime | None = None
        expires_first: datetime | None = None

        for envelope in envelopes:
            candidate_as_of = envelope.resolve_as_of()
            if candidate_as_of and (as_of_dt is None or candidate_as_of > as_of_dt):
                as_of_dt = candidate_as_of
            if envelope.cached_at and (cached_latest is None or envelope.cached_at > cached_latest):
                cached_latest = envelope.cached_at
            if envelope.expires_at:
                if expires_first is None or envelope.expires_at < expires_first:
                    expires_first = envelope.expires_at

        stale = not envelopes or all(envelope.is_stale(now) for envelope in envelopes)

        return self.CacheResult(
            items=items,
            as_of=self._format_iso(as_of_dt),
            stale=stale,
            cached_at=self._format_iso(cached_latest),
            expires_at=self._format_iso(expires_first),
        )

    @staticmethod
    def _parse_iso_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(text).astimezone(timezone.utc)
            except ValueError:
                return None
        return None

    @staticmethod
    def _format_iso(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _build_key(self, module: str, *parts: str, source: str | None = None) -> str:
        namespace = getattr(self.writer, "namespace", "market")
        normalized_module = (module or "default").strip() or "default"
        normalized_source = self._normalize_source(source)
        cleaned_parts = [str(part) for part in parts if str(part)]
        return ":".join([namespace, normalized_module, normalized_source, *cleaned_parts])

    def _legacy_key(self, module: str, *parts: str) -> str:
        namespace = getattr(self.writer, "namespace", "market")
        legacy_module = self._legacy_module_name(module)
        cleaned_parts = [str(part) for part in parts if str(part)]
        return ":".join([namespace, legacy_module, *cleaned_parts])

    @staticmethod
    def _legacy_module_name(module: str) -> str:
        mapping = {
            "order_imbalance": "order-imbalance",
            "auction_quality": "auction",
        }
        normalized = (module or "").strip()
        if normalized in mapping:
            return mapping[normalized]
        return normalized or "boards"

    def _normalize_source(self, source: str | None = None) -> str:
        if source:
            candidate = source.strip().lower()
            if candidate:
                return candidate
        writer_source = getattr(self.writer, "data_source", None)
        if isinstance(writer_source, str) and writer_source.strip():
            return writer_source.strip().lower()
        return "default"
