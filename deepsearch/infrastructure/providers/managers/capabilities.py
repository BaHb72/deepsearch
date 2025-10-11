"""AkShare 能力映射表。

该模块提供一个最小兼容层，将 `DataCapability` 映射到 AkShare Proxy
内部使用的 API 名称，供管理器在缺少 SDK 时 graceful degrade。
"""

from __future__ import annotations

from typing import Dict, Optional

from deepsearch.infrastructure.providers.interfaces.capabilities import DataCapability

_AKSHARE_CAPABILITY_API: Dict[DataCapability, str] = {
    DataCapability.KLINE_DATA: "stock_zh_a_hist",
    DataCapability.REALTIME_QUOTES: "stock_zh_a_spot",
    DataCapability.REALTIME_QUOTE: "stock_zh_a_spot",
    DataCapability.STOCK_LIST: "stock_zh_a_spot",
    DataCapability.FINANCIAL_DATA: "stock_financial_abstract",
}


def get_akshare_api(capability: DataCapability) -> Optional[str]:
    """根据数据能力返回 AkShare API 名称。"""

    return _AKSHARE_CAPABILITY_API.get(capability)


__all__ = ["get_akshare_api"]
