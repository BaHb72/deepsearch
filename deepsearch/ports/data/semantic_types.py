"""
数据访问层语义类型定义。

该模块定义了统一的语义类型，用于在不同数据源之间建立共同语言：
- AssetSpec: 资产标识
- Timeframe: 时间周期
- AdjustType: 复权类型
- TimeRange: 时间范围
- LatencyHint: 延迟提示
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import ClassVar


class Exchange(StrEnum):
    """交易所枚举"""

    SH = "SH"  # 上海证券交易所
    SZ = "SZ"  # 深圳证券交易所
    BJ = "BJ"  # 北京证券交易所
    HK = "HK"  # 香港交易所
    US = "US"  # 美股


class AssetType(StrEnum):
    """资产类型枚举"""

    STOCK = "stock"  # 股票
    ETF = "etf"  # ETF
    INDEX = "index"  # 指数
    FUND = "fund"  # 基金
    BOND = "bond"  # 债券
    FUTURE = "future"  # 期货
    OPTION = "option"  # 期权


class Timeframe(StrEnum):
    """时间周期枚举"""

    TICK = "tick"
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MO1 = "1mo"

    def __lt__(self, other: "Timeframe") -> bool:
        """支持周期比较"""
        order = list(Timeframe)
        return order.index(self) < order.index(other)

    def __le__(self, other: "Timeframe") -> bool:
        return self == other or self < other

    def __gt__(self, other: "Timeframe") -> bool:
        return not self <= other

    def __ge__(self, other: "Timeframe") -> bool:
        return not self < other


class AdjustType(StrEnum):
    """复权类型枚举"""

    NONE = "none"  # 不复权
    FORWARD = "qfq"  # 前复权
    BACKWARD = "hfq"  # 后复权


class LatencyHint(StrEnum):
    """延迟提示枚举，用于场景路由"""

    REALTIME = "realtime"  # 实时，<100ms
    LOW = "low"  # 低延迟，<1s
    NORMAL = "normal"  # 正常，<10s
    BATCH = "batch"  # 批量，可容忍分钟级


class InstrumentStatus(StrEnum):
    """标的状态枚举"""

    ACTIVE = "active"  # 正常上市
    SUSPENDED = "suspended"  # 停牌
    DELISTED = "delisted"  # 退市


@dataclass(frozen=True, slots=True)
class AssetSpec:
    """
    资产标识规格。

    统一格式，支持从多种字符串格式解析。
    """

    symbol: str
    exchange: Exchange
    asset_type: AssetType = AssetType.STOCK

    # 解析正则：支持 000001.SZ, 000001.sz, SZ000001, sz.000001 等格式
    _PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"^(\d{6})\.([A-Za-z]{2})$"),  # 000001.SZ
        re.compile(r"^([A-Za-z]{2})(\d{6})$"),  # SZ000001
        re.compile(r"^([A-Za-z]{2})\.(\d{6})$"),  # SZ.000001
    ]

    @classmethod
    def from_code(cls, code: str, asset_type: AssetType = AssetType.STOCK) -> "AssetSpec":
        """
        从代码字符串解析资产标识。

        支持格式：
        - 000001.SZ
        - SZ000001
        - SZ.000001

        Args:
            code: 资产代码字符串
            asset_type: 资产类型，默认股票

        Returns:
            AssetSpec 实例

        Raises:
            ValueError: 无法解析的代码格式
        """
        code = code.strip().upper()

        # 尝试模式1: 000001.SZ
        match = cls._PATTERNS[0].match(code)
        if match:
            return cls(
                symbol=match.group(1),
                exchange=Exchange(match.group(2)),
                asset_type=asset_type,
            )

        # 尝试模式2: SZ000001
        match = cls._PATTERNS[1].match(code)
        if match:
            return cls(
                symbol=match.group(2),
                exchange=Exchange(match.group(1)),
                asset_type=asset_type,
            )

        # 尝试模式3: SZ.000001
        match = cls._PATTERNS[2].match(code)
        if match:
            return cls(
                symbol=match.group(2),
                exchange=Exchange(match.group(1)),
                asset_type=asset_type,
            )

        raise ValueError(f"Cannot parse asset code: {code}")

    def to_standard(self) -> str:
        """返回标准格式：000001.SZ"""
        return f"{self.symbol}.{self.exchange.value}"

    def to_compact(self) -> str:
        """返回紧凑格式：SZ000001"""
        return f"{self.exchange.value}{self.symbol}"

    def __str__(self) -> str:
        return self.to_standard()


@dataclass(frozen=True, slots=True)
class TimeRange:
    """
    时间范围规格。

    统一处理 start/end/limit 的语义，避免参数冲突。
    """

    start: datetime | None = None
    end: datetime | None = None
    limit: int | None = None
    timezone: str = "Asia/Shanghai"

    @classmethod
    def last_n(cls, n: int, timezone: str = "Asia/Shanghai") -> "TimeRange":
        """创建「最近 N 条」的时间范围"""
        return cls(limit=n, timezone=timezone)

    @classmethod
    def between(
        cls,
        start: datetime,
        end: datetime | None = None,
        timezone: str = "Asia/Shanghai",
    ) -> "TimeRange":
        """创建指定时间区间的范围"""
        return cls(start=start, end=end or datetime.now(), timezone=timezone)

    @classmethod
    def last_days(cls, days: int, timezone: str = "Asia/Shanghai") -> "TimeRange":
        """创建「最近 N 天」的时间范围"""
        now = datetime.now()
        return cls(start=now - timedelta(days=days), end=now, timezone=timezone)

    def is_bounded(self) -> bool:
        """是否有明确的时间边界"""
        return self.start is not None or self.end is not None

    def is_limited(self) -> bool:
        """是否有条数限制"""
        return self.limit is not None


__all__ = [
    "Exchange",
    "AssetType",
    "Timeframe",
    "AdjustType",
    "LatencyHint",
    "AssetSpec",
    "TimeRange",
]
