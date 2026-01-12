"""
快照对齐策略枚举

定义了查询历史快照时的日期对齐行为。
"""

from enum import Enum
from typing import Optional


class SnapshotAlignPolicy(str, Enum):
    """快照日期对齐策略

    用于处理查询日期不在交易日或交易时段内的情况。

    Attributes:
        PASSTHROUGH: 不做任何对齐，直接使用请求日期
        NEAREST_PREV: 对齐到最近的前一个交易日
        STRICT: 严格模式，非交易日返回空结果
    """

    PASSTHROUGH = "passthrough"
    NEAREST_PREV = "nearest_prev"
    STRICT = "strict"

    @classmethod
    def from_value(cls, value: Optional["SnapshotAlignPolicy | str"]) -> "SnapshotAlignPolicy":
        """从字符串或枚举值创建实例

        Args:
            value: 策略值，可以是字符串或枚举

        Returns:
            SnapshotAlignPolicy 枚举成员
        """
        if value is None:
            return cls.PASSTHROUGH
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            value_lower = value.lower().strip()
            for member in cls:
                if member.value == value_lower:
                    return member
        return cls.PASSTHROUGH
