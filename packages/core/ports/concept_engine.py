"""Concept 引擎端口定义。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable, Mapping, Protocol, Sequence

if TYPE_CHECKING:
    import pandas as pd

SnapshotPayload = Sequence[Mapping[str, object]] | Mapping[str, object]
SnapshotCallback = Callable[[SnapshotPayload], Awaitable[None]]


class ConceptDataProviderPort(Protocol):
    """Concept 引擎依赖的数据源能力集合。"""

    async def get_industry_base_info(self) -> "pd.DataFrame":
        """获取行业/概念基础信息。"""

    async def get_industry_constituent(self, concept_code: str) -> "pd.DataFrame":
        """获取指定概念成分股。"""

    async def get_stock_list(self) -> "pd.DataFrame":
        """获取股票列表。"""

    async def subscribe_stock_snapshot(
        self,
        stock_codes: Sequence[str],
        callback: SnapshotCallback,
    ) -> None:
        """订阅股票快照数据。"""


__all__ = [
    "ConceptDataProviderPort",
    "SnapshotCallback",
    "SnapshotPayload",
]

