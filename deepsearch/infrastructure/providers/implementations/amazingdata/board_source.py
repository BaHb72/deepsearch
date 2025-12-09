"""Board universe source for AmazingData."""

from __future__ import annotations

import inspect
from datetime import timedelta
from typing import Mapping, Sequence, Tuple

from loguru import logger

from deepsearch.domain.market_data import DEFAULT_BOARD_FIELDS, StockListRecord
from deepsearch.infrastructure.persistence.ingestion_records import DataSourceRecordPersistence
from deepsearch.ports.data_sources import DataAccessType, DataSourceType

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

    async def fetch_records(self, *, use_cache: bool = True, job_id: str | None = None) -> Sequence[StockListRecord]:
        if use_cache:
            cached = await self._load_cached_records()
            if cached:
                logger.debug("AmazingData board source 命中持久化快照 job_type={} size={}", self._job_type, len(cached))
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
                        record = StockListRecord.from_payload(entry, board_fields=self._board_fields)
                    else:
                        continue
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
            if record.symbol:
                materialized.append(record)
        return tuple(materialized)

    async def _persist_records(self, records: Sequence[StockListRecord], *, job_id: str | None = None) -> None:
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
            logger.warning("写入板块快照失败 job_type={} size={} error={}", self._job_type, len(records), exc)

    async def fetch_stock_list(self) -> Sequence[StockListRecord]:
        """Backward compatible alias for existing call sites."""

        return await self.fetch_records()
