"""MiniQMT-based polling adapter for the realtime orchestrator.

This adapter provides market data by polling MiniQMT/xtquant SDK.
It supports both the socket-based MiniQMTProvider and the xtdata-based MiniQMTCollector.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Mapping, MutableSet, Sequence

from loguru import logger

from deepsearch.domain.market_data import StockListRecord
from deepsearch.ports.market_data import (
    BoardUniversePort,
    MarketSnapshot,
    RealtimeAdapter,
    RealtimeAdapterCapabilities,
    RealtimePortBundle,
    RealtimeStreamPort,
)


def _normalize_symbol(symbol: str) -> str:
    """Normalize symbol to xtquant format (e.g., 000001.SZ)."""
    text = str(symbol or "").strip().upper()
    if "." in text:
        return text
    # Add exchange suffix if missing
    if len(text) == 6 and text.isdigit():
        if text.startswith("6"):
            return f"{text}.SH"
        elif text.startswith(("0", "3")):
            return f"{text}.SZ"
        elif text.startswith(("4", "8")):
            return f"{text}.BJ"
    return text


def _resolve_exchange(symbol: str) -> str:
    """Extract exchange from symbol."""
    text = str(symbol or "").strip().upper()
    if text.endswith(".SH"):
        return "SH"
    if text.endswith(".SZ"):
        return "SZ"
    if text.endswith(".BJ"):
        return "BJ"
    code = text.split(".")[0] if "." in text else text
    if code.startswith("6"):
        return "SH"
    if code.startswith(("0", "3")):
        return "SZ"
    if code.startswith(("4", "8")):
        return "BJ"
    return "SH"


def _infer_board_labels(symbol: str) -> tuple[str, ...]:
    """Infer board classification from symbol."""
    code = symbol.split(".")[0] if "." in symbol else symbol
    if not code:
        return ()
    boards: list[str] = []
    if code.startswith(("688", "689")):
        boards.extend(("科创板", "主板"))
    elif code.startswith(("300", "301")):
        boards.extend(("创业板", "主板"))
    elif code.startswith(("43", "83", "87", "88", "4", "8")):
        boards.append("北证")
    else:
        boards.append("主板")
    return tuple(dict.fromkeys(board for board in boards if board))


def _to_decimal(value: Any) -> Decimal:
    try:
        if value is None or value == "":
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _build_snapshot(symbol: str, tick_data: Mapping[str, Any]) -> MarketSnapshot:
    """Convert MiniQMTCollector tick data to MarketSnapshot."""
    code = symbol.split(".")[0] if "." in symbol else symbol
    exchange = _resolve_exchange(symbol)
    name = str(tick_data.get("name") or code)

    # MiniQMTCollector normalized field names
    last_price = _to_decimal(tick_data.get("last_price") or tick_data.get("lastPrice", 0))
    prev_close = _to_decimal(tick_data.get("pre_close") or tick_data.get("lastClose", 0))

    # Parse bid/ask arrays
    bid_prices = tuple(_to_decimal(p) for p in (tick_data.get("bid_price") or tick_data.get("bidPrice") or [])[:5])
    bid_volumes = tuple(_to_int(v) for v in (tick_data.get("bid_volume") or tick_data.get("bidVol") or [])[:5])
    ask_prices = tuple(_to_decimal(p) for p in (tick_data.get("ask_price") or tick_data.get("askPrice") or [])[:5])
    ask_volumes = tuple(_to_int(v) for v in (tick_data.get("ask_volume") or tick_data.get("askVol") or [])[:5])

    # Handle timestamp
    ts_value = tick_data.get("time")
    if isinstance(ts_value, (int, float)) and ts_value > 0:
        # MiniQMT timestamp is in milliseconds
        if ts_value > 1e12:
            ts = datetime.fromtimestamp(ts_value / 1000, tz=timezone.utc)
        else:
            ts = datetime.fromtimestamp(ts_value, tz=timezone.utc)
    else:
        ts = datetime.now(timezone.utc)

    return MarketSnapshot(
        code=code,
        name=name,
        exchange=exchange,
        ts=ts,
        last=last_price,
        open=_to_decimal(tick_data.get("open", 0)),
        high=_to_decimal(tick_data.get("high", 0)),
        low=_to_decimal(tick_data.get("low", 0)),
        prev_close=prev_close,
        amount=_to_decimal(tick_data.get("amount", 0)),
        volume=_to_int(tick_data.get("volume", 0)),
        num_trades=None,
        bid_prices=bid_prices,
        bid_volumes=bid_volumes,
        ask_prices=ask_prices,
        ask_volumes=ask_volumes,
        upper_limit=None,
        lower_limit=None,
        trading_phase=None,
    )


# Global collector instance for reuse
_GLOBAL_COLLECTOR: Any = None
_COLLECTOR_LOCK = asyncio.Lock()


async def _get_or_create_collector():
    """Get or create a global MiniQMTCollector instance."""
    global _GLOBAL_COLLECTOR

    if _GLOBAL_COLLECTOR is not None:
        return _GLOBAL_COLLECTOR

    async with _COLLECTOR_LOCK:
        if _GLOBAL_COLLECTOR is not None:
            return _GLOBAL_COLLECTOR

        try:
            from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
                MiniQMTCollector,
            )
            loop = asyncio.get_event_loop()
            _GLOBAL_COLLECTOR = await loop.run_in_executor(None, MiniQMTCollector)
            logger.info("MiniQMTCollector 实例创建成功")
            return _GLOBAL_COLLECTOR
        except ImportError as exc:
            logger.error("MiniQMTCollector 导入失败: {}", exc)
            raise RuntimeError(f"MiniQMTCollector not available: {exc}") from exc
        except Exception as exc:
            logger.error("MiniQMTCollector 初始化失败: {}", exc)
            raise


class MiniQMTPollingStreamPort(RealtimeStreamPort):
    """Implement MarketStreamPort by polling MiniQMTCollector."""

    def __init__(self, batch_size: int = 50) -> None:
        self._subscribed: MutableSet[str] = set()
        self._lock = asyncio.Lock()
        self._batch_size = max(1, batch_size)
        self._collector: Any = None
        self._name_cache: Dict[str, str] = {}

    async def _ensure_collector(self) -> Any:
        """Lazy initialize the MiniQMTCollector."""
        if self._collector is None:
            self._collector = await _get_or_create_collector()
        return self._collector

    async def subscribe(self, codes: Sequence[str]) -> None:
        async with self._lock:
            for code in codes:
                normalized = _normalize_symbol(code)
                if normalized:
                    self._subscribed.add(normalized)

    async def unsubscribe(self, codes: Sequence[str]) -> None:
        async with self._lock:
            for code in codes:
                normalized = _normalize_symbol(code)
                if normalized in self._subscribed:
                    self._subscribed.discard(normalized)

    async def list_subscriptions(self) -> Sequence[str]:
        async with self._lock:
            return tuple(sorted(self._subscribed))

    async def _fetch_stock_names(self, collector: Any, symbols: Sequence[str]) -> None:
        """Fetch and cache stock names from instrument details."""
        missing = [s for s in symbols if s not in self._name_cache]
        if not missing:
            return

        loop = asyncio.get_event_loop()
        for symbol in missing[:20]:  # Limit to avoid blocking
            try:
                info = await loop.run_in_executor(
                    None, collector.get_instrument_detail, symbol
                )
                if info and info.get("name"):
                    self._name_cache[symbol] = info["name"]
            except Exception:
                pass

    async def fetch_latest(self, codes: Sequence[str] | None = None) -> Sequence[MarketSnapshot]:
        target: list[str]
        if codes:
            target = [_normalize_symbol(code) for code in codes if _normalize_symbol(code)]
        else:
            async with self._lock:
                target = list(self._subscribed)
        if not target:
            return []

        collector = await self._ensure_collector()
        if not collector.connected:
            logger.warning("MiniQMTCollector 未连接")
            return []

        snapshots: list[MarketSnapshot] = []
        loop = asyncio.get_event_loop()

        for i in range(0, len(target), self._batch_size):
            batch = target[i:i + self._batch_size]
            try:
                # Run synchronous collector call in executor
                result = await loop.run_in_executor(None, collector.get_full_tick, batch)

                if not result:
                    continue

                # Prefetch names for this batch
                await self._fetch_stock_names(collector, batch)

                for symbol in batch:
                    tick_data = result.get(symbol)
                    if not isinstance(tick_data, Mapping):
                        continue
                    if not tick_data or tick_data.get("last_price", 0) == 0:
                        continue

                    # Enrich with cached name
                    enriched = dict(tick_data)
                    if symbol in self._name_cache:
                        enriched["name"] = self._name_cache[symbol]

                    snapshots.append(_build_snapshot(symbol, enriched))

            except Exception as exc:
                logger.warning("MiniQMT polling error for batch: {}", exc)
                continue

        return snapshots

    async def collect_window(self, window) -> Sequence[MarketSnapshot]:
        return await self.fetch_latest()


class MiniQMTBoardUniversePort(BoardUniversePort):
    """Expose MiniQMT/xtquant stock list as board-universe fetcher."""

    def __init__(self) -> None:
        self._collector: Any = None
        self._name_cache: Dict[str, str] = {}

    async def _ensure_collector(self) -> Any:
        if self._collector is None:
            self._collector = await _get_or_create_collector()
        return self._collector

    async def fetch_records(self) -> Sequence[StockListRecord]:
        logger.info("MiniQMT fetch_records 开始执行")
        collector = await self._ensure_collector()
        if not collector.connected:
            logger.warning("MiniQMTCollector 未连接，无法获取板块数据")
            return ()

        records: list[StockListRecord] = []
        loop = asyncio.get_running_loop()

        try:
            # Get A-share stock list from multiple sectors
            sectors = ["沪深A股", "北交所"]
            all_symbols: set[str] = set()

            for sector in sectors:
                try:
                    logger.debug("MiniQMT 获取板块 {} 股票列表...", sector)
                    stock_list = await loop.run_in_executor(
                        None, collector.get_stock_list_in_sector, sector
                    )
                    if stock_list:
                        all_symbols.update(stock_list)
                        logger.debug("MiniQMT 板块 {} 获取到 {} 只股票", sector, len(stock_list))
                except Exception as exc:
                    logger.warning("获取板块 {} 失败: {}", sector, exc)

            if not all_symbols:
                logger.warning("MiniQMT 返回空股票列表")
                return ()

            logger.info("MiniQMT 获取到 {} 只股票", len(all_symbols))

            # Build records directly without fetching names (too slow for 5000+ stocks)
            # Names will be fetched lazily during fetch_latest
            symbols_list = list(all_symbols)
            for symbol in symbols_list:
                if not symbol or not isinstance(symbol, str):
                    continue
                code = symbol.split(".")[0] if "." in symbol else symbol
                exchange = _resolve_exchange(symbol)
                boards = _infer_board_labels(symbol)
                name = self._name_cache.get(symbol, code)  # Use code as fallback name

                record = StockListRecord(
                    symbol=code,
                    name=name,
                    exchange=exchange,
                    boards=boards,
                    is_listed=None,
                    delist_date=None,
                    status=None,
                )
                records.append(record)

            logger.info("MiniQMT 构建 {} 条股票记录", len(records))

        except Exception as exc:
            logger.warning("MiniQMT fetch stock list failed: {}", exc)

        return tuple(records)


class MiniQMTPollingAdapter(RealtimeAdapter):
    """RealtimeAdapter implementation backed by MiniQMT/xtquant polling."""

    def __init__(self, *, name: str = "miniqmt", batch_size: int = 50) -> None:
        self.name = name
        self._stream_port = MiniQMTPollingStreamPort(batch_size=batch_size)
        self._board_port = MiniQMTBoardUniversePort()
        self._started = False

    @property
    def capabilities(self) -> RealtimeAdapterCapabilities:
        return RealtimeAdapterCapabilities(
            streaming=True,
            snapshot=True,
            board_universe=True,
            capital_pulse=True,
            auction=True,
            order_imbalance=True,
        )

    async def start(self) -> RealtimePortBundle:
        if not self._started:
            # Verify MiniQMTCollector is available
            collector = await self._stream_port._ensure_collector()
            if not collector.connected:
                raise RuntimeError("MiniQMTCollector 未连接")
            self._started = True
            logger.info("MiniQMT 适配器启动成功")

        return RealtimePortBundle(
            stream=self._stream_port,
            board=self._board_port,
        )

    async def stop(self) -> None:
        self._started = False
        logger.info("MiniQMT 适配器已停止")


__all__ = ["MiniQMTPollingAdapter", "MiniQMTPollingStreamPort", "MiniQMTBoardUniversePort"]
