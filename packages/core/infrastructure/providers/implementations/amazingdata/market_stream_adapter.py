"""MarketStreamPort adapter for the AmazingData provider."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Deque, Mapping, MutableMapping, Sequence, cast

from core.ports.market_data import MarketSnapshot, WindowSpec
from core.ports.market_data.protocols import MarketStreamPort

from .amazingdata import AmazingDataProvider
from .amazingdata_types import AmazingDataStreamPayload, AmazingDataStreamQuote, RealtimeQuoteMap
from .logging_utils import ProcessLoggerAdapter

logger = ProcessLoggerAdapter(action="market_stream")


def _as_decimal(value: object | None, default: Decimal | None = Decimal("0")) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _as_int(value: object | None, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip() or 0)
    except Exception:
        return default


def _short_exchange(symbol: str, fallback: str = "") -> str:
    upper = symbol.upper()
    if upper.endswith(".SH"):
        return "SSE"
    if upper.endswith(".SZ"):
        return "SZSE"
    if upper.endswith(".HK"):
        return "HKEX"
    return fallback


def _parse_timestamp(raw: object | None, fallback: datetime | None = None) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw))
        except Exception:
            pass
    if isinstance(raw, str):
        candidate = raw.strip()
        if not candidate:
            pass
        else:
            patterns = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y%m%d%H%M%S",
                "%H:%M:%S",
            ]
            for pattern in patterns:
                try:
                    ts = datetime.strptime(candidate, pattern)
                    if pattern == "%H:%M:%S":
                        today = datetime.utcnow()
                        ts = ts.replace(year=today.year, month=today.month, day=today.day)
                    return ts
                except ValueError:
                    continue
    if isinstance(fallback, datetime):
        return fallback
    return datetime.utcnow()


def _coerce_stream_payload(payload: Mapping[str, Any]) -> AmazingDataStreamPayload | None:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return None

    typed: AmazingDataStreamPayload = {
        "data": cast(AmazingDataStreamQuote, dict(data)),
    }

    timestamp = payload.get("timestamp")
    if isinstance(timestamp, datetime):
        typed["timestamp"] = timestamp
    elif timestamp is not None:
        typed["timestamp"] = _parse_timestamp(timestamp)

    period = payload.get("period")
    if isinstance(period, str) and period.strip():
        typed["period"] = period.strip()

    return typed


def _coerce_realtime_quotes(raw: Mapping[str, Any] | None) -> RealtimeQuoteMap:
    if not raw:
        return {}
    typed: dict[str, AmazingDataStreamQuote] = {}
    for symbol, payload in raw.items():
        if not isinstance(symbol, str) or not symbol:
            continue
        if not isinstance(payload, Mapping):
            continue
        typed[symbol] = cast(AmazingDataStreamQuote, dict(payload))
    return typed


class AmazingDataMarketStreamAdapter(MarketStreamPort):
    """基于 AmazingData Provider 的 MarketStreamPort 实现。"""

    def __init__(
        self,
        provider: AmazingDataProvider,
        *,
        retention: timedelta = timedelta(minutes=10),
        freshness_window: timedelta | None = None,
    ) -> None:
        self.name = "AmazingData"
        self._provider = provider
        self._retention = retention
        self._active_codes: set[str] = set()
        self._latest: MutableMapping[str, MarketSnapshot] = {}
        self._history: MutableMapping[str, Deque[MarketSnapshot]] = {}
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._latest_update: MutableMapping[str, float] = {}
        self._refresh_cursor: int = 0
        default_freshness = timedelta(seconds=10)
        freshness = freshness_window or default_freshness
        if freshness.total_seconds() <= 0:
            freshness = default_freshness
        self._freshness_window_seconds = freshness.total_seconds()
        subscription_cfg = getattr(self._provider, "config", None)
        subscription_batch = getattr(
            getattr(subscription_cfg, "subscription", None), "batch_size", None
        )
        max_symbols = getattr(getattr(subscription_cfg, "subscription", None), "max_symbols", None)
        batch_candidates = [
            value
            for value in (subscription_batch, max_symbols)
            if isinstance(value, int) and value > 0
        ]
        self._refresh_batch_size = min(batch_candidates) if batch_candidates else 100

    async def subscribe(self, codes: Sequence[str]) -> None:
        unique = [code.strip() for code in codes if code and code.strip()]
        if not unique:
            return
        await self._ensure_ready()
        async with self._lock:
            new_codes = [code for code in unique if code not in self._active_codes]
            if not new_codes:
                logger.debug(
                    "AmazingData订阅跳过：全部代码已在活跃列表 codes={}",
                    ",".join(unique),
                )
                return
        success = await self._provider.subscribe_stock_snapshot(
            new_codes, self._handle_stream_payload
        )
        if not success:
            raise RuntimeError(f"AmazingData subscribe failed: {', '.join(new_codes)}")
        async with self._lock:
            self._active_codes.update(new_codes)
        logger.debug(
            "AmazingData订阅完成 新增={} 总计={}",
            len(new_codes),
            len(self._active_codes),
        )

    async def unsubscribe(self, codes: Sequence[str]) -> None:
        targets = [code for code in codes if code in self._active_codes]
        if not targets:
            return
        await self._ensure_ready()
        success = await self._provider.unsubscribe_quote(list(targets))
        if not success:
            logger.warning("AmazingData unsubscribe failed: {}", targets)
        async with self._lock:
            for code in targets:
                self._active_codes.discard(code)
                self._latest.pop(code, None)
                self._history.pop(code, None)
                self._latest_update.pop(code, None)
            if not self._active_codes:
                self._refresh_cursor = 0
        logger.debug(
            "AmazingData取消订阅完成 目标={} 剩余={}",
            len(targets),
            len(self._active_codes),
        )

    async def list_subscriptions(self) -> Sequence[str]:
        async with self._lock:
            return sorted(self._active_codes)

    async def fetch_latest(self, codes: Sequence[str] | None = None) -> Sequence[MarketSnapshot]:
        await self._ensure_ready()
        async with self._lock:
            targets = list(codes or (self._active_codes or self._latest.keys()))
            cached_snapshots = {code: self._latest.get(code) for code in targets}
            update_times = {code: self._latest_update.get(code) for code in targets}
        if not targets:
            return []

        result_map: dict[str, MarketSnapshot] = {}
        now_monotonic = time.monotonic()
        stale_codes: list[str] = []

        logger.debug(
            "AmazingData fetch_latest 开始 targets={} provided_codes={}",
            len(targets),
            ",".join(codes) if codes else "<auto>",
        )

        for code in targets:
            cached = cached_snapshots.get(code)
            if cached is None:
                stale_codes.append(code)
                continue
            last_update = update_times.get(code)
            if last_update is None or now_monotonic - last_update > self._freshness_window_seconds:
                stale_codes.append(code)
            else:
                result_map[code] = cached

        refresh_codes: list[str] = []
        if stale_codes:
            total_stale = len(stale_codes)
            batch_size = min(self._refresh_batch_size, total_stale)
            offset = self._refresh_cursor % total_stale if total_stale else 0
            refresh_codes = [stale_codes[(offset + idx) % total_stale] for idx in range(batch_size)]
            self._refresh_cursor = (offset + batch_size) % max(total_stale, 1)
        logger.debug(
            "AmazingData fetch_latest 判定完成 stale={} refresh={} batch_size={} cursor={}",
            len(stale_codes),
            len(refresh_codes),
            self._refresh_batch_size,
            self._refresh_cursor,
        )

        if refresh_codes:
            refresh_start = time.perf_counter()
            try:
                quotes_raw = await self._provider.get_realtime_quote(refresh_codes)  # type: ignore[attr-defined]
            except Exception as exc:  # pragma: no cover - provider errors handled upstream
                logger.warning("AmazingDataʵʱ鲹ʧ: {}", exc)
                quotes_map: RealtimeQuoteMap = {}
            else:
                logger.debug(
                    "AmazingDataʵʱ鲹 codes={} duration={:.3f}s",
                    len(refresh_codes),
                    time.perf_counter() - refresh_start,
                )
                quotes_map = _coerce_realtime_quotes(quotes_raw)

            for code in refresh_codes:
                snapshot: MarketSnapshot | None = None
                payload = quotes_map.get(code)
                if payload:
                    snapshot = self._snapshot_from_quote_dict(payload)
                    if snapshot:
                        await self._record_snapshot(snapshot)
                if snapshot is None:
                    snapshot = cached_snapshots.get(code)
                if snapshot:
                    result_map[code] = snapshot

        for code in stale_codes:
            if code not in result_map:
                cached = cached_snapshots.get(code)
                if cached:
                    result_map[code] = cached

        return [result_map[code] for code in targets if code in result_map]

    async def collect_window(self, window: WindowSpec) -> Sequence[MarketSnapshot]:
        cutoff = datetime.utcnow() - window.duration
        result: list[MarketSnapshot] = []
        async with self._lock:
            for bucket in self._history.values():
                for snapshot in reversed(bucket):
                    if snapshot.ts >= cutoff:
                        result.append(snapshot)
                    else:
                        break
        return result

    async def _ensure_ready(self) -> None:
        if self._initialized and self._provider.is_connected():
            return
        async with self._init_lock:
            if self._initialized and self._provider.is_connected():
                return
            # 安全访问 provider.config，避免 MockErrorProvider 等兜底类没有 config 属性
            provider_config = getattr(self._provider, "config", None)
            subscription_enabled = (
                getattr(provider_config, "subscription_enabled", True) if provider_config else True
            )
            if not subscription_enabled:
                raise RuntimeError("AmazingData subscription disabled in config")
            logger.debug("AmazingData adapter开始初始化连接")
            initialized = await self._provider.initialize()
            if not initialized or not self._provider.is_connected():
                status = {}
                try:
                    status = self._provider.connection_status()  # type: ignore[attr-defined]
                except Exception:  # pragma: no cover - 防御性
                    status = {}
                logger.error(
                    "AmazingData adapter 初始化失败 status=%s",
                    status,
                )
                raise RuntimeError("Failed to initialize AmazingData data source")
            self._initialized = True
            logger.debug("AmazingData adapter初始化完成")

    async def _handle_stream_payload(self, payload: Mapping[str, Any]) -> None:
        typed_payload = _coerce_stream_payload(payload)
        if typed_payload is None:
            logger.debug("Skipping AmazingData stream payload without data field")
            return
        snapshot = self._snapshot_from_stream_payload(typed_payload)
        if snapshot is None:
            return
        await self._record_snapshot(snapshot)

    async def _record_snapshot(self, snapshot: MarketSnapshot) -> None:
        async with self._lock:
            self._latest[snapshot.code] = snapshot
            bucket = self._history.setdefault(snapshot.code, deque())
            self._latest_update[snapshot.code] = time.monotonic()
            if bucket and bucket[-1].ts > snapshot.ts:
                return
            bucket.append(snapshot)
            cutoff = snapshot.ts - self._retention
            while bucket and bucket[0].ts < cutoff:
                bucket.popleft()

    def _snapshot_from_stream_payload(
        self,
        payload: AmazingDataStreamPayload,
    ) -> MarketSnapshot | None:
        data = payload.get("data")
        if not isinstance(data, Mapping):
            return None
        code_raw = data.get("code") or data.get("symbol")
        if not code_raw:
            return None
        code = str(code_raw).upper()
        name = str(data.get("name") or "")
        exchange = _short_exchange(code, str(data.get("exchange") or ""))
        ts = _parse_timestamp(data.get("time"), payload.get("timestamp"))

        last = _as_decimal(
            data.get("price") or data.get("last") or data.get("last_price")
        ) or Decimal("0")
        open_px = _as_decimal(data.get("open"), default=Decimal("0")) or Decimal("0")
        high_px = _as_decimal(data.get("high"), default=Decimal("0")) or Decimal("0")
        low_px = _as_decimal(data.get("low"), default=Decimal("0")) or Decimal("0")
        prev_close = _as_decimal(
            data.get("pre_close") or data.get("prev_close"), default=Decimal("0")
        ) or Decimal("0")
        amount = _as_decimal(data.get("amount"), default=Decimal("0")) or Decimal("0")
        volume = _as_int(data.get("volume"), default=0)
        num_trades = _as_int(data.get("num_trades") or data.get("trade_num"), default=0)

        bid_prices = self._extract_prices(data.get("bid") or data.get("bid_prices"))
        ask_prices = self._extract_prices(data.get("ask") or data.get("ask_prices"))
        bid_volumes = self._extract_volumes(data.get("bid_volume") or data.get("bid_volumes"))
        ask_volumes = self._extract_volumes(data.get("ask_volume") or data.get("ask_volumes"))

        upper_limit = _as_decimal(data.get("high_limit") or data.get("upper_limit"), default=None)
        lower_limit = _as_decimal(data.get("low_limit") or data.get("lower_limit"), default=None)
        trading_phase_raw = data.get("trading_phase") or data.get("status")
        trading_phase = str(trading_phase_raw) if trading_phase_raw else None

        return MarketSnapshot(
            code=code,
            name=name,
            exchange=exchange,
            ts=ts,
            last=last,
            open=open_px,
            high=high_px,
            low=low_px,
            prev_close=prev_close,
            amount=amount,
            volume=volume,
            num_trades=num_trades or None,
            bid_prices=bid_prices,
            bid_volumes=bid_volumes,
            ask_prices=ask_prices,
            ask_volumes=ask_volumes,
            upper_limit=upper_limit if upper_limit not in (None, Decimal("0")) else None,
            lower_limit=lower_limit if lower_limit not in (None, Decimal("0")) else None,
            trading_phase=trading_phase,
        )

    def _snapshot_from_quote_dict(self, payload: Mapping[str, Any]) -> MarketSnapshot | None:
        symbol = payload.get("symbol")
        if not symbol:
            return None
        code = str(symbol).upper()
        name = str(payload.get("name") or "")
        exchange = _short_exchange(code, "")
        ts = _parse_timestamp(payload.get("time"))
        last = _as_decimal(payload.get("last")) or Decimal("0")
        open_px = _as_decimal(payload.get("open")) or Decimal("0")
        high_px = _as_decimal(payload.get("high")) or Decimal("0")
        low_px = _as_decimal(payload.get("low")) or Decimal("0")
        prev_close = _as_decimal(payload.get("close") or payload.get("prev_close")) or Decimal("0")
        amount = _as_decimal(payload.get("amount")) or Decimal("0")
        volume = _as_int(payload.get("volume"))
        num_trades = _as_int(payload.get("num_trades") or payload.get("trade_num"), default=0)

        bid1 = _as_decimal(payload.get("bid1"))
        ask1 = _as_decimal(payload.get("ask1"))
        bid_prices: tuple[Decimal, ...] = (
            (bid1,) if bid1 is not None and bid1 != Decimal("0") else ()
        )
        ask_prices: tuple[Decimal, ...] = (
            (ask1,) if ask1 is not None and ask1 != Decimal("0") else ()
        )
        bid_volumes = (
            (_as_int(payload.get("bid1_volume")),)
            if payload.get("bid1_volume") is not None
            else tuple()
        )
        ask_volumes = (
            (_as_int(payload.get("ask1_volume")),)
            if payload.get("ask1_volume") is not None
            else tuple()
        )

        upper_limit = _as_decimal(payload.get("high_limit"), default=None)
        lower_limit = _as_decimal(payload.get("low_limit"), default=None)
        trading_phase = str(payload.get("status")) if payload.get("status") else None

        return MarketSnapshot(
            code=code,
            name=name,
            exchange=exchange,
            ts=ts,
            last=last,
            open=open_px,
            high=high_px,
            low=low_px,
            prev_close=prev_close,
            amount=amount,
            volume=volume,
            num_trades=num_trades or None,
            bid_prices=bid_prices,
            bid_volumes=bid_volumes,
            ask_prices=ask_prices,
            ask_volumes=ask_volumes,
            upper_limit=upper_limit if upper_limit not in (None, Decimal("0")) else None,
            lower_limit=lower_limit if lower_limit not in (None, Decimal("0")) else None,
            trading_phase=trading_phase,
        )

    @staticmethod
    def _extract_prices(raw: Any) -> Sequence[Decimal]:
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            result: list[Decimal] = []
            for value in list(raw)[:5]:
                dec = _as_decimal(value)
                if dec is not None:
                    result.append(dec)
            return tuple(result)
        return tuple()

    @staticmethod
    def _extract_volumes(raw: Any) -> Sequence[int]:
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            return tuple(_as_int(value) for value in list(raw)[:5])
        return tuple()
