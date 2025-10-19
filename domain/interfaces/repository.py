"""仓储协议与分页模型的最小实现。"""

from __future__ import annotations


from dataclasses import dataclass
from typing import Generic, Optional, Protocol, Sequence, TypeVar

from domain.entities.stock import Stock

T_co = TypeVar("T_co", covariant=True)
T = TypeVar("T")


@dataclass(slots=True, frozen=True)
class PageRequest:
    """分页请求参数。"""

    page: int = 1
    size: int = 20

    @property
    def offset(self) -> int:
        """计算偏移量。"""
        if self.page <= 1:
            return 0
        return (self.page - 1) * self.size


@dataclass(slots=True)
class PageResult(Generic[T_co]):
    """分页结果。"""

    items: Sequence[T_co]
    total: int
    page: int
    size: int


class IRepository(Protocol[T]):
    """通用仓储接口。"""

    async def get_by_id(self, id: str) -> Optional[T]:
        """根据标识获取实体。"""

    async def get_all(self) -> list[T]:
        """返回全部实体。"""

    async def add(self, entity: T) -> None:
        """新增实体。"""

    async def update(self, entity: T) -> None:
        """更新实体。"""

    async def delete(self, id: str) -> None:
        """删除实体。"""

    async def exists(self, id: str) -> bool:
        """判断实体是否存在。"""


class IStockRepository(IRepository[Stock], Protocol):
    """股票仓储专用接口。"""

    async def get_by_symbol(self, symbol: str) -> Optional[Stock]:
        """通过证券代码获取股票。"""

    async def get_by_market(self, market: str, page_request: PageRequest) -> PageResult[Stock]:
        """按市场分页查询股票。"""

    async def search(self, keyword: str, page_request: PageRequest) -> PageResult[Stock]:
        """按关键字分页搜索股票。"""

    async def get_top_gainers(self, limit: int = 10, market: Optional[str] = None) -> list[Stock]:
        """获取涨幅榜。"""

    async def get_top_losers(self, limit: int = 10, market: Optional[str] = None) -> list[Stock]:
        """获取跌幅榜。"""


class IUnitOfWork(Protocol):
    """事务单元接口。"""

    @property
    def stocks(self) -> IStockRepository:
        """股票仓储实例。"""

    async def __aenter__(self) -> "IUnitOfWork":
        """进入上下文环境。"""

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """退出上下文环境。"""

    async def commit(self) -> None:
        """提交事务。"""

    async def rollback(self) -> None:
        """回滚事务。"""
