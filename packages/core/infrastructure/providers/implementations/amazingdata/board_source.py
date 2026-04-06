"""Board universe source for AmazingData."""

from __future__ import annotations

import inspect
from datetime import timedelta
from typing import Mapping, Sequence, Tuple

from core.domain.market_data import DEFAULT_BOARD_FIELDS, StockListRecord
from core.infrastructure.persistence.ingestion_records import DataSourceRecordPersistence
from core.ports.data_sources import DataAccessType, DataSourceType
from loguru import logger

from .amazingdata import AmazingDataProvider


class AmazingDataBoardSource:
    """Fetch stock list data to hydrate the board universe."""

    def __init__(
        self,
        provider: AmazingDataProvider,
        *,
        board_fields: Sequence[str] = DEFAULT_BOARD_FIELDS,
        record_store: DataSourceRecordPersistence | None = None,
        job_type: str = "prefetch_stock_basics",
        cache_ttl: timedelta = timedelta(minutes=30),
        data_source: DataSourceType = DataSourceType.AMAZINGDATA,
    ) -> None:
        self._provider = provider
        self._board_fields: Tuple[str, ...] = tuple(board_fields)
        self._record_store = record_store
        self._job_type = job_type
        self._cache_ttl = cache_ttl
        self._data_source = data_source

    async def fetch_records(
        self, *, use_cache: bool = True, job_id: str | None = None
    ) -> Sequence[StockListRecord]:
        if use_cache:
            cached = await self._load_cached_records()
            if cached:
                with_board = sum(1 for record in cached if record.boards)
                if with_board < len(cached):
                    logger.warning(
                        "AmazingData board source 缓存板块覆盖不足，将尝试回源补齐 job_type={} size={} with_board={}",
                        self._job_type,
                        len(cached),
                        with_board,
                    )
                else:
                    logger.debug(
                        "AmazingData board source 命中持久化快照 job_type={} size={} with_board={}",
                        self._job_type,
                        len(cached),
                        with_board,
                    )
                    return cached
                # 缓存命中但板块覆盖不足，继续回源拉取最新板块信息
                # （避免旧快照仅含 symbol/name 导致 board_universe 为空）
                # 注意：若回源失败，会在下方返回缓存作为兜底。
                try:
                    records = await self._fetch_from_provider()
                    if records:
                        await self._persist_records(records, job_id=job_id)
                        return records
                except Exception as exc:  # pragma: no cover - 回源失败降级
                    logger.warning("回源刷新板块快照失败，将回退缓存: {}", exc)
                logger.debug(
                    "AmazingData board source 使用缓存兜底 job_type={} size={}",
                    self._job_type,
                    len(cached),
                )
                return cached

        records = await self._fetch_from_provider()
        await self._persist_records(records, job_id=job_id)
        return records

    async def _fetch_from_provider(self) -> Sequence[StockListRecord]:
        get_records = getattr(self._provider, "get_stock_list_records", None)
        if callable(get_records):
            result = get_records()
            if inspect.isawaitable(result):
                result = await result
            if result:
                normalized: list[StockListRecord] = []
                for entry in result:
                    if isinstance(entry, StockListRecord):
                        record = entry
                    elif isinstance(entry, Mapping):
                        record = StockListRecord.from_payload(
                            entry, board_fields=self._board_fields
                        )
                    else:
                        continue
                    record = _ensure_boards(record)
                    if record.symbol:
                        normalized.append(record)
                if normalized:
                    return tuple(normalized)

        payload = await self._provider.get_stock_list()
        records: list[StockListRecord] = []
        if payload:
            for entry in payload:
                if not isinstance(entry, Mapping):
                    continue
                record = StockListRecord.from_payload(entry, board_fields=self._board_fields)
                record = _ensure_boards(record)
                if record.symbol:
                    records.append(record)
        return tuple(records)

    async def _load_cached_records(self) -> Sequence[StockListRecord]:
        if self._record_store is None or self._cache_ttl <= timedelta(0):
            return ()
        try:
            snapshot = await self._record_store.load_latest_record_set(
                job_type=self._job_type,
                data_source=self._data_source,
                access_type=DataAccessType.STOCK_LIST,
                max_age=self._cache_ttl,
            )
        except Exception as exc:  # pragma: no cover - 缓存加载失败仅记录
            logger.debug("加载板块快照缓存失败 job_type={} error={}", self._job_type, exc)
            return ()

        if not snapshot or not snapshot.records:
            return ()
        materialized: list[StockListRecord] = []
        for entry in snapshot.records:
            if not isinstance(entry, Mapping):
                continue
            record = StockListRecord.from_payload(entry, board_fields=self._board_fields)
            record = _ensure_boards(record)
            if record.symbol:
                materialized.append(record)
        return tuple(materialized)

    async def _persist_records(
        self, records: Sequence[StockListRecord], *, job_id: str | None = None
    ) -> None:
        if self._record_store is None or not records:
            return
        expires_in = self._cache_ttl * 2 if self._cache_ttl > timedelta(0) else None
        try:
            await self._record_store.persist_stock_list(
                records,
                job_type=self._job_type,
                data_source=self._data_source,
                access_type=DataAccessType.STOCK_LIST,
                chunk_size=500,
                metadata={"board_fields": list(self._board_fields)},
                expires_in=expires_in,
                job_id=job_id,
            )
        except Exception as exc:  # pragma: no cover - 写入失败仅日志
            logger.warning(
                "写入板块快照失败 job_type={} size={} error={}", self._job_type, len(records), exc
            )

    async def fetch_stock_list(self) -> Sequence[StockListRecord]:
        """Backward compatible alias for existing call sites."""

        return await self.fetch_records()


_BSE_PREFIXES: tuple[str, ...] = ("43", "83", "87", "88")


def _extract_symbol_code(symbol: str | None) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        return ""
    head = text.split(".", 1)[0]
    code = "".join(ch for ch in head if ch.isdigit())
    return code


def _infer_boards_from_symbol(symbol: str | None) -> tuple[str, ...]:
    code = _extract_symbol_code(symbol)
    if not code:
        return ()
    if code.startswith(("688", "689")):
        return ("科创板", "主板")
    if code.startswith(("300", "301")):
        return ("创业板", "主板")
    if code.startswith(_BSE_PREFIXES) or code.startswith(("4", "8")):
        return ("北证",)
    return ("主板",)


def _ensure_boards(record: StockListRecord) -> StockListRecord:
    if record.boards:
        return record
    inferred = _infer_boards_from_symbol(record.symbol)
    if not inferred:
        return record
    return record.with_boards(inferred)
