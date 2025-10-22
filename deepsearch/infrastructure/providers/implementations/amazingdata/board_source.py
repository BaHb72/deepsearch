"""Board universe source for AmazingData."""

from __future__ import annotations

from typing import Mapping, Sequence

from .amazingdata import AmazingDataProvider


class AmazingDataBoardSource:
    """Fetch stock list data to hydrate the board universe."""

    def __init__(self, provider: AmazingDataProvider) -> None:
        self._provider = provider

    async def fetch_stock_list(self) -> Sequence[Mapping[str, object]]:
        payload = await self._provider.get_stock_list()
        if not payload:
            return []
        return payload
