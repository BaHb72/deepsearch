"""数据类型别名，支撑指标模块的类型检查。"""

from __future__ import annotations

from typing import TypeAlias

import numpy as np
import numpy.typing as npt
import pandas as pd

NumericArray: TypeAlias = npt.NDArray[np.float_]
NumericSeries: TypeAlias = pd.Series
BoolSeries: TypeAlias = pd.Series
StringSeries: TypeAlias = pd.Series
TimestampSeries: TypeAlias = pd.Series
TimedeltaSeries: TypeAlias = pd.Series
DatetimeScalar: TypeAlias = pd.Timestamp
TimedeltaScalar: TypeAlias = pd.Timedelta

__all__ = [
    "NumericArray",
    "NumericSeries",
    "BoolSeries",
    "StringSeries",
    "TimestampSeries",
    "TimedeltaSeries",
    "DatetimeScalar",
    "TimedeltaScalar",
]
