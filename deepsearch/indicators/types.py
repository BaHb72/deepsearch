"""指标模块内部通用的类型别名。"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeAlias

import numpy as np

# 支持 numpy 数组与原生序列作为指标计算输入。
FloatArray: TypeAlias = np.ndarray[Any, np.dtype[np.float64]] | Sequence[float]

