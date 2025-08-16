"""存储模块

提供数据持久化相关功能，包括：
- 时序数据库 (TimescaleDB)
- 分析数据库 (DuckDB)
- 数据模型定义
- 数据访问接口
"""

# from .timeseries import RedisTimeSeriesStorage  # 暂时禁用，待修复兼容性问题
try:
    from .models_dir.base import Base, BaseModel, TimeSeriesBase, TimestampMixin
    from .models_dir.market import (
        MarketTick, Market1Min, Market5Min, MarketDaily, MarketSnapshot
    )
    from .models_dir.trading import (
        Order, Position, Trade, Account, DailySettlement,
        OrderSide, OrderType, OrderStatus
    )
except ImportError:
    # 如果models_dir不存在，使用models.py
    from .models import Base, StockInfo

__all__ = [
    # "RedisTimeSeriesStorage",  # 暂时禁用
    # 基础类
    'Base', 'BaseModel', 'TimeSeriesBase', 'TimestampMixin',
    # 行情模型
    'MarketTick', 'Market1Min', 'Market5Min', 'MarketDaily', 'MarketSnapshot',
    # 交易模型
    'Order', 'Position', 'Trade', 'Account', 'DailySettlement',
    'OrderSide', 'OrderType', 'OrderStatus'
]
