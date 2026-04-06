from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import pytest
from core.adapters.market_data.akshare_polling_adapter import AkShareBoardUniversePort
from core.ports.data_sources import DataAccessType, DataSourceType


@dataclass
class _Snapshot:
    records: tuple[Mapping[str, Any], ...]
    completed_at: datetime | None


class _FakeRecordStore:
    def __init__(self) -> None:
        self.job_types: list[str] = []

    async def load_latest_record_set(self, **kwargs):
        job_type = str(kwargs.get("job_type") or "")
        self.job_types.append(job_type)
        if job_type == "legacy_stock_job":
            return _Snapshot(
                records=(
                    {
                        "symbol": "000001",
                        "name": "平安银行",
                        "exchange": "SZ",
                        "boards": ["主板"],
                    },
                ),
                completed_at=datetime.now(timezone.utc),
            )
        return None

    async def fetch_jobs(self, **kwargs):
        del kwargs
        return [
            {
                "job_type": "legacy_stock_job",
                "data_source": DataSourceType.AKSHARE.value,
                "access_type": DataAccessType.STOCK_LIST.value,
                "status": "succeeded",
            }
        ]

    async def persist_stock_list(self, *args, **kwargs):
        del args, kwargs
        raise AssertionError("cache hit path should not persist")


class _FailIfFetchedAdapter:
    async def fetch_stock_list(self):
        raise AssertionError("cache hit path should not fetch upstream")


@pytest.mark.asyncio
async def test_akshare_board_universe_fallbacks_to_recent_job_type_cache() -> None:
    store = _FakeRecordStore()
    port = AkShareBoardUniversePort(
        _FailIfFetchedAdapter(),
        record_store=store,
        data_source=DataSourceType.AKSHARE,
        job_type="akshare_board_universe",
    )

    records = await port.fetch_records()

    assert len(records) == 1
    assert records[0].symbol == "000001"
    assert records[0].name == "平安银行"
    assert store.job_types == ["akshare_board_universe", "legacy_stock_job"]
