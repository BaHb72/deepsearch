from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None  # type: ignore[assignment]


@dataclass
class KlineParams:
    symbol: str
    timeframe: str = "1d"  # 1m,3m,5m,15m,30m,60m,1d,1w,1mo
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = 500
    adjust: str = "none"  # none, qfq, hfq


@runtime_checkable
class IDataFeed(Protocol):
    async def get_kline(self, params: KlineParams) -> "pd.DataFrame | List[Dict[str, Any]]": ...

    async def get_realtime(self, symbols: List[str]) -> Dict[str, Any]: ...

    def normalize_bars(
        self, data: List[Dict[str, Any]]
    ) -> "pd.DataFrame | List[Dict[str, Any]]": ...
