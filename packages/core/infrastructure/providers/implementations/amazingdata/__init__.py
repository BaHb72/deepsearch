"""
AmazingData Provider 模块

提供 AmazingData SDK 的完整封装，包括：
- 数据提供者：基础数据查询、行情数据、财务数据
- 实时数据：行情订阅与推送
- 数据转换：格式标准化

Architecture:
    AmazingDataProvider (主入口)
    ├── AmazingDataExtended (35个API接口实现)
    ├── AmazingDataQueryManager (查询路由)
    ├── AmazingDataConverter (数据格式转换)
    └── OptimizedAmazingDataProvider (优化实现)

注意: ProcessIsolatedAmazingDataProvider 已废弃并删除。
"""

# =============================================================================
# 核心 Provider 类
# =============================================================================
from .amazingdata import AmazingDataProvider
from .amazingdata_extended import AmazingDataExtended, StockListRecord
from .amazingdata_optimized import OptimizedAmazingDataProvider

# =============================================================================
# 实时数据
# =============================================================================
from .amazingdata_realtime import AmazingDataRealtime

# =============================================================================
# 辅助工具
# =============================================================================
from .api_catalog import AMAZINGDATA_API_CATALOG, catalog_to_json
from .board_source import AmazingDataBoardSource
from .market_stream_adapter import AmazingDataMarketStreamAdapter

# =============================================================================
# 公共导出
# =============================================================================
__all__ = [
    # 核心 Provider
    "AmazingDataProvider",
    "AmazingDataExtended",
    "OptimizedAmazingDataProvider",
    "StockListRecord",
    # 实时数据
    "AmazingDataRealtime",
    "AmazingDataMarketStreamAdapter",
    # 辅助工具
    "AMAZINGDATA_API_CATALOG",
    "catalog_to_json",
    "AmazingDataBoardSource",
]
