"""AkShare-based polling adapter for the realtime orchestrator."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, MutableSet, Sequence

from core.core.components.data_components import DatabaseComponent
from core.domain.market_data import StockListRecord
from core.infrastructure.persistence.database import DatabaseService
from core.infrastructure.persistence.ingestion_records import DataSourceRecordPersistence
from core.infrastructure.providers.implementations.akshare.akshare_adapter import AkShareAdapter
from core.ports.data_sources import DataAccessType, DataSourceType
from core.ports.market_data import (
    BoardUniversePort,
    MarketSnapshot,
    RealtimeAdapter,
    RealtimeAdapterCapabilities,
    RealtimePortBundle,
    RealtimeStreamPort,
)
from loguru import logger


def _normalize_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    if text.endswith(".SH") or text.endswith(".SZ"):
        return text[:6]
    if len(text) == 6 and text.isdigit():
        return text
    return text


def _resolve_exchange(symbol: str) -> str:
    code = _normalize_symbol(symbol)
    if code.startswith("6"):
        return "SH"
    if code.startswith(("0", "3")):
        return "SZ"
    if code.startswith(("4", "8")):
        return "BJ"
    return "SH"


_BSE_PREFIXES: tuple[str, ...] = (
    "43",
    "83",
    "87",
    "88",
)


def _infer_board_labels(symbol: str) -> tuple[str, ...]:
    code = _normalize_symbol(symbol)
    if not code:
        return ()
    boards: list[str] = []
    if code.startswith(("688", "689")):
        boards.extend(("科创板", "主板"))
    elif code.startswith(("300", "301")):
        boards.extend(("创业板", "主板"))
    elif code.startswith(_BSE_PREFIXES) or code.startswith(("4", "8")):
        boards.append("北证")
    else:
        boards.append("主板")
    # dict preserves insertion order for deduplication
    return tuple(dict.fromkeys(board for board in boards if board))


def _augment_stock_record(record: StockListRecord) -> StockListRecord:
    updates: dict[str, Any] = {}
    if not record.exchange:
        updates["exchange"] = _resolve_exchange(record.symbol)
    inferred_boards = record.boards or _infer_board_labels(record.symbol)
    if inferred_boards and inferred_boards != record.boards:
        updates["boards"] = inferred_boards
    if updates:
        return replace(record, **updates)
    return record


_AKSHARE_RECORD_STORE: DataSourceRecordPersistence | None = None
_AKSHARE_BOARD_CACHE_MAX_AGE = timedelta(hours=12)


def _resolve_record_store() -> DataSourceRecordPersistence | None:
    global _AKSHARE_RECORD_STORE
    if _AKSHARE_RECORD_STORE is not None:
        return _AKSHARE_RECORD_STORE
    try:
        from core.core.runtime.context import get_context

        component = get_context().get_component("database")
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.debug("AkShare 板块快照持久化不可用: {}", exc)
        return None
    if not isinstance(component, DatabaseComponent):
        logger.debug("AkShare 板块快照未找到有效的 database 组件")
        return None
    _AKSHARE_RECORD_STORE = DataSourceRecordPersistence(DatabaseService(component))
    return _AKSHARE_RECORD_STORE


def _to_decimal(value: Any) -> Decimal:
    try:
        if value is None or value == "":
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except InvalidOperation, ValueError, TypeError:
        return Decimal("0")


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except TypeError, ValueError:
        return 0


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                pass
    return datetime.now(timezone.utc)


def _build_snapshot(symbol: str, payload: Mapping[str, Any]) -> MarketSnapshot:
    code = _normalize_symbol(symbol)
    exchange = _resolve_exchange(code)
    name = str(payload.get("name") or payload.get("stock_name") or code)
    last_price = _to_decimal(payload.get("current") or payload.get("price"))
    prev_close = payload.get("prev_close") or payload.get("yesterday_close")
    return MarketSnapshot(
        code=code,
        name=name,
        exchange=exchange,
        ts=_parse_timestamp(payload.get("timestamp")),
        last=last_price,
        open=_to_decimal(payload.get("open")),
        high=_to_decimal(payload.get("high")),
        low=_to_decimal(payload.get("low")),
        prev_close=_to_decimal(prev_close),
        amount=_to_decimal(payload.get("amount")),
        volume=_to_int(payload.get("volume")),
        num_trades=None,
        bid_prices=(),
        bid_volumes=(),
        ask_prices=(),
        ask_volumes=(),
        upper_limit=None,
        lower_limit=None,
        trading_phase=None,
    )


class AkSharePollingStreamPort(RealtimeStreamPort):
    """Implement MarketStreamPort by polling AkShareAdapter."""

    def __init__(self, adapter: AkShareAdapter, batch_size: int = 20) -> None:
        self._adapter = adapter
        self._subscribed: MutableSet[str] = set()
        self._lock = asyncio.Lock()
        self._batch_size = max(1, batch_size)

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

    async def fetch_latest(self, codes: Sequence[str] | None = None) -> Sequence[MarketSnapshot]:
        target: list[str]
        if codes:
            target = [_normalize_symbol(code) for code in codes if _normalize_symbol(code)]
        else:
            async with self._lock:
                target = list(self._subscribed)
        if not target:
            return []

        snapshots: list[MarketSnapshot] = []
        for i in range(0, len(target), self._batch_size):
            batch = target[i : i + self._batch_size]
            result = await self._adapter.get_realtime_data(batch)
            for sym in batch:
                payload = result.get(sym) or result.get(sym.lower()) or {}
                if not isinstance(payload, Mapping):
                    continue
                if payload.get("error"):
                    logger.debug(
                        "AkShare polling returned error for {}: {}", sym, payload.get("error")
                    )
                    continue
                snapshots.append(_build_snapshot(sym, payload))
        return snapshots

    async def collect_window(self, window) -> Sequence[MarketSnapshot]:
        # 没有累计窗口概念，直接返回最新快照
        return await self.fetch_latest()


class AkShareBoardUniversePort(BoardUniversePort):
    """Expose AkShare stock list as board-universe fetcher."""

    def __init__(
        self,
        adapter: AkShareAdapter,
        *,
        record_store: DataSourceRecordPersistence | None,
        data_source: DataSourceType,
        job_type: str,
    ) -> None:
        self._adapter = adapter
        self._record_store = record_store
        self._data_source = data_source
        self._job_type = job_type

    async def fetch_records(self) -> Sequence[StockListRecord]:
        cached_records = await self._load_cached_records()
        if cached_records:
            return tuple(cached_records)

        rows = await self._adapter.fetch_stock_list()
        succeeded = rows is not None
        records: list[StockListRecord] = []
        payloads: list[dict[str, Any]] = []
        captured_at = datetime.now(timezone.utc)
        for row in rows or []:
            if not isinstance(row, Mapping):
                continue
            record = StockListRecord.from_payload(row)
            if not record.symbol:
                continue
            record = _augment_stock_record(record)
            records.append(record)
            payload = dict(record.as_mapping())
            payload["captured_at"] = captured_at.isoformat()
            payloads.append(payload)
        if succeeded:
            await self._persist_snapshot(payloads, captured_at=captured_at)
        return tuple(records)

    async def _load_cached_records(self) -> list[StockListRecord]:
        record_store = self._record_store
        if record_store is None:
            return []

        async def _load_by_job_type(job_type: str) -> list[StockListRecord]:
            try:
                snapshot = await record_store.load_latest_record_set(
                    job_type=job_type,
                    data_source=self._data_source,
                    access_type=DataAccessType.STOCK_LIST,
                    max_age=_AKSHARE_BOARD_CACHE_MAX_AGE,
                )
            except Exception as exc:
                logger.debug("AkShare 板块快照读取失败 job_type={} error={}", job_type, exc)
                return []

            if snapshot is None or not snapshot.records:
                return []

            materialized: list[StockListRecord] = []
            for row in snapshot.records:
                if not isinstance(row, Mapping):
                    continue
                record = StockListRecord.from_payload(row)
                if not record.symbol:
                    continue
                materialized.append(_augment_stock_record(record))
            if materialized:
                logger.debug(
                    "AkShare 板块快照命中缓存 job_type={} records={} completed_at={}",
                    job_type,
                    len(materialized),
                    snapshot.completed_at,
                )
            return materialized

        records = await _load_by_job_type(self._job_type)
        if records:
            return records

        # 同源同能力的快照可能由其他任务写入（例如实时 fallback 任务）。
        # 若当前 job_type 未命中，按最近成功作业回退一次，避免盘后“有快照却空表”。
        try:
            jobs = await record_store.fetch_jobs(limit=40)
        except Exception as exc:
            logger.debug("AkShare 板块快照回退扫描失败: {}", exc)
            return []

        candidate_job_types: list[str] = []
        for job in jobs:
            if not isinstance(job, Mapping):
                continue
            if str(job.get("status") or "").lower() != "succeeded":
                continue
            if str(job.get("data_source") or "").lower() != self._data_source.value:
                continue
            if str(job.get("access_type") or "").lower() != DataAccessType.STOCK_LIST.value:
                continue
            job_type = str(job.get("job_type") or "").strip()
            if not job_type:
                continue
            if job_type not in candidate_job_types:
                candidate_job_types.append(job_type)

        for job_type in candidate_job_types:
            if job_type == self._job_type:
                continue
            records = await _load_by_job_type(job_type)
            if records:
                return records

        return []

    async def _persist_snapshot(
        self,
        payloads: Sequence[Mapping[str, Any]],
        *,
        captured_at: datetime,
    ) -> None:
        if self._record_store is None:
            return
        try:
            await self._record_store.persist_stock_list(
                payloads,
                job_type=self._job_type,
                data_source=self._data_source,
                metadata={
                    "provider": "akshare",
                    "record_count": len(payloads),
                    "captured_at": captured_at.isoformat(),
                },
                requested_at=captured_at,
            )
        except Exception as exc:
            logger.warning("AkShare 板块快照持久化失败: {}", exc)


class AkSharePollingAdapter(RealtimeAdapter):
    """RealtimeAdapter implementation backed by AkShare polling."""

    def __init__(
        self,
        *,
        name: str = "akshare",
        use_proxy: bool = False,
        batch_size: int = 20,
    ) -> None:
        self.name = name
        self._adapter = AkShareAdapter(use_proxy=use_proxy)
        self._stream_port = AkSharePollingStreamPort(self._adapter, batch_size=batch_size)
        self._board_port = AkShareBoardUniversePort(
            self._adapter,
            record_store=_resolve_record_store(),
            data_source=DataSourceType.AKSHARE,
            job_type=f"{name}_board_universe",
        )
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
            await self._adapter.initialize()
            self._started = True
        return RealtimePortBundle(
            stream=self._stream_port,
            board=self._board_port,
        )

    async def stop(self) -> None:
        # AkShare adapter currently does not expose shutdown hooks
        self._started = False


__all__ = ["AkSharePollingAdapter", "AkSharePollingStreamPort", "AkShareBoardUniversePort"]
