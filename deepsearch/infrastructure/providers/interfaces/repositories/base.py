"""仓储接口定义，供各类数据提供者实现复用。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Mapping, Protocol, TypeVar

EntityT = TypeVar("EntityT")
KeyT = TypeVar("KeyT", contravariant=True)


class IRepository(Protocol, Generic[EntityT, KeyT]):
    """异步仓储协议，约束最常见的 CRUD 操作。"""

    async def get_by_id(self, key: KeyT) -> EntityT | None:
        ...

    async def get_all(self, options: "QueryOptions" | None = None) -> list[EntityT]:
        ...

    async def find(self, criteria: Mapping[str, object]) -> list[EntityT]:
        ...

    async def find_one(self, criteria: Mapping[str, object]) -> EntityT | None:
        ...

    async def save(self, entity: EntityT, *args, **kwargs) -> EntityT:
        ...

    async def save_many(self, entities: list[EntityT]) -> list[EntityT]:
        ...

    async def update(self, key: KeyT, updates: Mapping[str, object]) -> EntityT | None:
        ...

    async def delete(self, key: KeyT) -> bool:
        ...


@dataclass(slots=True)
class QueryOptions:
    """通用查询选项，封装过滤、分页与排序参数。"""

    filters: dict[str, object] = field(default_factory=dict)
    limit: int = 100
    skip: int = 0
    sort_by: str | None = None
    sort_desc: bool = False

    def __post_init__(self) -> None:
        if self.limit is None:
            self.limit = 100
        if self.skip < 0:
            self.skip = 0
        if isinstance(self.filters, Mapping):
            self.filters = dict(self.filters)
