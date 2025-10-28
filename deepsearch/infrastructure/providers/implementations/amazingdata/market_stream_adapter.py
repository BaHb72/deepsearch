"""MarketStreamPort adapter for the AmazingData provider."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Deque, Mapping, MutableMapping, Optional, Sequence

from loguru import logger

from deepsearch.ports.market_data import MarketSnapshot, WindowSpec
from deepsearch.ports.market_data.protocols import MarketStreamPort
from .amazingdata import AmazingDataProvider


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


class AmazingDataMarketStreamAdapter(MarketStreamPort):
    """基于 AmazingData Provider 的 MarketStreamPort 实现。"""

    def __init__(
            self,
            provider: AmazingDataProvider,
            *,
            retention: timedelta = timedelta(minutes=10),
    ) -> None:
        self._provider = provider
        self._retention = retention
        self._active_codes: set[str] = set()
        self._latest: MutableMapping[str, MarketSnapshot] = {}
        self._history: MutableMapping[str, Deque[MarketSnapshot]] = {}
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._poll_only: bool = False
        self._poll_reason: Optional[str] = None

    async def subscribe(self, codes: Sequence[str]) -> None:
        unique = [code.strip() for code in codes if code and code.strip()]
        if not unique:
            return
        await self._ensure_ready()
        async with self._lock:
            new_codes = [code for code in unique if code not in self._active_codes]
            if not new_codes:
                return
        if self._poll_only:
            logger.info(
                "AmazingDataMarketStreamAdapter 已启用轮询模式，跳过订阅调用: %s",
                ", ".join(new_codes),
            )
        else:
            subscribe_callable = getattr(
                self._provider, "subscribe_stock_snapshot", None
            )
            if not callable(subscribe_callable):
                self._activate_poll_only(
                    "subscribe_stock_snapshot not implemented on provider"
                )
            else:
                try:
                    success = await subscribe_callable(
                        new_codes, self._handle_stream_payload
                    )
                except Exception as exc:  # noqa: BLE001
                    if self._is_subscription_unsupported(exc):
                        self._activate_poll_only(str(exc))
                    else:
                        raise
                else:
                    if not success:
                        self._activate_poll_only(
                            "provider returned False when subscribing"
                        )
        async with self._lock:
            self._active_codes.update(new_codes)

    async def unsubscribe(self, codes: Sequence[str]) -> None:
        targets = [code for code in codes if code in self._active_codes]
        if not targets:
            return
        await self._ensure_ready()
        if not self._poll_only:
            unsubscribe_callable = getattr(self._provider, "unsubscribe_quote", None)
            if callable(unsubscribe_callable):
                try:
                    success = await unsubscribe_callable(list(targets))
                except Exception as exc:  # noqa: BLE001
                    if self._is_subscription_unsupported(exc):
                        self._activate_poll_only(str(exc))
                    else:
                        logger.warning("AmazingData unsubscribe failed: {}", exc)
                        success = False
                else:
                    if not success:
                        logger.warning("AmazingData unsubscribe failed: {}", targets)
            else:
                self._activate_poll_only(
                    "unsubscribe_quote not implemented on provider"
                )
        async with self._lock:
            for code in targets:
                self._active_codes.discard(code)

    async def list_subscriptions(self) -> Sequence[str]:
        async with self._lock:
            return sorted(self._active_codes)

    async def fetch_latest(self, codes: Sequence[str] | None = None) -> Sequence[MarketSnapshot]:
        await self._ensure_ready()
        async with self._lock:
            targets = list(codes or (self._active_codes or self._latest.keys()))
        if not targets:
            return []

        quotes = await self._provider.get_realtime_quote(targets)
        snapshots: list[MarketSnapshot] = []
        for code in targets:
            payload = quotes.get(code)
            if payload:
                snapshot = self._snapshot_from_quote_dict(payload)
                if snapshot:
                    await self._record_snapshot(snapshot)
                    snapshots.append(snapshot)
                    continue
            async with self._lock:
                existing = self._latest.get(code)
            if existing:
                snapshots.append(existing)
        return snapshots

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
            if not getattr(self._provider.config, "subscription_enabled", True):
                self._activate_poll_only("subscription disabled by configuration")
            initialized = await self._provider.initialize()
            if not initialized or not self._provider.is_connected():
                raise RuntimeError("Failed to initialize AmazingData data source")
            self._initialized = True

    async def _handle_stream_payload(self, payload: Mapping[str, Any]) -> None:
        snapshot = self._snapshot_from_stream_payload(payload)
        if snapshot is None:
            return
        await self._record_snapshot(snapshot)

    async def _record_snapshot(self, snapshot: MarketSnapshot) -> None:
        async with self._lock:
            self._latest[snapshot.code] = snapshot
            bucket = self._history.setdefault(snapshot.code, deque())
            if bucket and bucket[-1].ts > snapshot.ts:
                return
            bucket.append(snapshot)
            cutoff = snapshot.ts - self._retention
            while bucket and bucket[0].ts < cutoff:
                bucket.popleft()

    def _activate_poll_only(self, reason: str | None = None) -> None:
        if not self._poll_only:
            message = reason or "AmazingData subscription unavailable, falling back to polling"
            logger.warning(
                "AmazingDataMarketStreamAdapter 启用轮询模式: {}",
                message,
            )
        self._poll_only = True
        if reason:
            self._poll_reason = reason

    @staticmethod
    def _is_subscription_unsupported(exc: Exception) -> bool:
        message = str(exc)
        lowered = message.lower()
        return any(
            keyword in lowered
            for keyword in (
                "未开放",
                "not implemented",
                "not available",
                "not supported",
                "暂未开放",
            )
        )

    def _snapshot_from_stream_payload(
            self,
            payload: Mapping[str, Any],
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

        last = _as_decimal(data.get("price") or data.get("last") or data.get("last_price")) or Decimal("0")
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
        bid_prices = (bid1,) if bid1 != Decimal("0") else tuple()
        ask_prices = (ask1,) if ask1 != Decimal("0") else tuple()
        bid_volumes = (_as_int(payload.get("bid1_volume")),) if payload.get("bid1_volume") is not None else tuple()
        ask_volumes = (_as_int(payload.get("ask1_volume")),) if payload.get("ask1_volume") is not None else tuple()

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
            return tuple(_as_decimal(value) for value in list(raw)[:5])
        return tuple()

    @staticmethod
    def _extract_volumes(raw: Any) -> Sequence[int]:
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            return tuple(_as_int(value) for value in list(raw)[:5])
        return tuple()
