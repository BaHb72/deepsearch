"""
数据类型定义
"""

from typing import Sequence, Union

import numpy as np
import pandas as pd

# NumericSeries 类型：支持 pandas Series、numpy array 或数值序列
NumericSeries = Union[pd.Series, np.ndarray, Sequence[float]]
