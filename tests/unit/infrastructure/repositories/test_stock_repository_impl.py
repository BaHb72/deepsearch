from __future__ import annotations
import pytest

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from types import ModuleType
from typing import Any, Generic, TypeVar

import sys

# `stock_repository_impl` 依赖的 stock 实体模块在当前工作区缺失，为保证测试可导入，这里构造最小 stub。
entities_module = ModuleType("deepsearch.infrastructure.providers.entities")
stock_module = ModuleType("deepsearch.infrastructure.providers.entities.stock")


class StockMarket(str, Enum):
    CN = "CN"
    US = "US"


class StockStatus(str, Enum):
    TRADING = "TRADING"
    HALTED = "HALTED"


class StockEntity:
    def __init__(self, **kwargs: Any):
        self.__dict__.update(kwargs)


setattr(stock_module, "StockMarket", StockMarket)
setattr(stock_module, "StockStatus", StockStatus)
setattr(stock_module, "StockEntity", StockEntity)

sys.modules.setdefault("deepsearch.infrastructure.providers.entities", entities_module)
sys.modules["deepsearch.infrastructure.providers.entities.stock"] = stock_module

interfaces_module = ModuleType("deepsearch.infrastructure.providers.interfaces")
repositories_module = ModuleType("deepsearch.infrastructure.providers.interfaces.repositories")
repositories_base_module = ModuleType(
    "deepsearch.infrastructure.providers.interfaces.repositories.base"
)

EntityT = TypeVar("EntityT")
KeyT = TypeVar("KeyT")


class IRepository(Generic[EntityT, KeyT]):  # pragma: no cover - 仅满足类型签名
    ...


class QueryOptions:
    def __init__(
        self,
        filters: dict[str, object] | None = None,
        limit: int | None = None,
        offset: int = 0,
        order_by: list[str] | None = None,
    ):
        self.filters = filters or {}
        self.limit = limit
        self.offset = offset
        self.order_by = order_by or []


setattr(repositories_base_module, "IRepository", IRepository)
setattr(repositories_base_module, "QueryOptions", QueryOptions)

sys.modules.setdefault("deepsearch.infrastructure.providers.interfaces", interfaces_module)
sys.modules.setdefault(
    "deepsearch.infrastructure.providers.interfaces.repositories", repositories_module
)
sys.modules[
    "deepsearch.infrastructure.providers.interfaces.repositories.base"
] = repositories_base_module


from deepsearch.infrastructure.repositories.stock_repository_impl import StockRepository  # noqa: E402
from deepsearch.infrastructure.persistence.types import (  # noqa: E402
    DatabaseServiceProtocol,
    DatabaseSessionProtocol,
)


class RecordingResult:
    """Minimal async result wrapper emulating SQLAlchemy `AsyncResult`."""

    def __init__(self, has_row: bool):
        self._has_row = has_row

    def first(self) -> tuple[int] | None:
        return (1,) if self._has_row else None


class RecordingSession(DatabaseSessionProtocol):
    """In-memory session spy capturing `execute` usage for assertions."""

    def __init__(self):
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0
        self._known_symbols: set[str] = set()

    async def execute(self, statement: Any, params: Any = None):
        text = str(statement)
        param_map = dict(params or {})
        self.calls.append((text, param_map))

        if "SELECT 1 FROM" in text:
            symbol = str(param_map.get("symbol", ""))
            return RecordingResult(symbol in self._known_symbols)

        # 对 INSERT/UPDATE 操作模拟写入
        symbol = str(param_map.get("symbol", ""))
        if "INSERT INTO" in text and symbol:
            self._known_symbols.add(symbol)
        return RecordingResult(has_row=False)

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1

    async def close(self) -> None:
        self.close_calls += 1


class RecordingDatabaseService(DatabaseServiceProtocol):
    """只实现仓储测试所需的事务接口，其余方法触发异常以确保未被调用。"""

    def __init__(self, session: RecordingSession):
        self.session = session
        self.transaction_entries = 0

    async def fetch_one(self, query: str, params: Any = None):  # pragma: no cover - not expected
        raise AssertionError("fetch_one should not be called when reusing explicit session")

    async def fetch_all(self, query: str, params: Any = None):  # pragma: no cover - not expected
        raise AssertionError("fetch_all should not be called when reusing explicit session")

    async def execute(self, query: str, params: Any = None):  # pragma: no cover - not expected
        raise AssertionError("execute should not be called when reusing explicit session")

    @asynccontextmanager
    async def transaction(self):
        self.transaction_entries += 1
        try:
            yield self.session
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        finally:
            await self.session.close()


@dataclass
class DummyStockEntity:
    """最小化的股票实体实现，满足仓储保存接口需求。"""

    symbol: str
    name: str = "Dummy"
    market: str = "CN"
    status: str = "TRADING"
    industry: str | None = None
    listing_date: datetime | None = None
    created_at: datetime | None = field(default_factory=datetime.utcnow)
    updated_at: datetime | None = field(default_factory=datetime.utcnow)
    current_price: Decimal | None = Decimal("1")
    prev_close: Decimal | None = Decimal("1")
    open_price: Decimal | None = Decimal("1")
    high: Decimal | None = Decimal("1")
    low: Decimal | None = Decimal("1")
    amount: Decimal | None = Decimal("1")
    market_cap: Decimal | None = Decimal("1")
    pe_ratio: Decimal | None = Decimal("1")
    pb_ratio: Decimal | None = Decimal("1")
    version: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "market": self.market,
            "status": self.status,
            "industry": self.industry,
            "listing_date": self.listing_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_price": self.current_price,
            "prev_close": self.prev_close,
            "open_price": self.open_price,
            "high": self.high,
            "low": self.low,
            "amount": self.amount,
            "market_cap": self.market_cap,
            "pe_ratio": self.pe_ratio,
            "pb_ratio": self.pb_ratio,
            "version": self.version,
        }


@pytest.mark.asyncio
async def test_save_many_reuses_single_transaction():
    session = RecordingSession()
    service = RecordingDatabaseService(session)
    repo = StockRepository(service, cache_manager=None)

    entities = [DummyStockEntity(symbol="AAA"), DummyStockEntity(symbol="BBB")]
    saved = await repo.save_many(entities.copy())

    assert saved == entities
    assert service.transaction_entries == 1
    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert session.close_calls == 1
    # 两只股票各一次存在性检查 + 插入
    assert len(session.calls) == 4
    assert session.calls[0][1]["symbol"] == "AAA"
    assert session.calls[2][1]["symbol"] == "BBB"


@pytest.mark.asyncio
async def test_save_without_session_opens_transaction():
    session = RecordingSession()
    # 预先记录 symbol 存在以走更新分支
    session._known_symbols.add("AAA")
    service = RecordingDatabaseService(session)
    repo = StockRepository(service, cache_manager=None)

    entity = DummyStockEntity(symbol="AAA")
    result = await repo.save(entity)

    assert result is entity
    assert service.transaction_entries == 1
    # 一次存在性检查 + 更新语句
    assert len(session.calls) == 2
    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert session.close_calls == 1
