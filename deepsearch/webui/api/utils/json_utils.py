"""
JSON sanitization utilities

处理 NaN、Infinity 等非 JSON 兼容的值
"""
import math
from typing import Any, Dict, List, Union

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None


def sanitize_for_json(data: Any) -> Any:
    """
    清理数据中的 NaN 和 Infinity 值，使其符合 JSON 规范
    
    Args:
        data: 需要清理的数据
        
    Returns:
        清理后的数据，NaN/Infinity 替换为 None
    """
    if data is None:
        return None

    # 处理 pandas DataFrame
    if HAS_PANDAS and isinstance(data, pd.DataFrame):
        # 将 NaN 替换为 None
        import numpy as np
        return data.replace({np.nan: None, float('inf'): None, float('-inf'): None}).to_dict(orient='records')

    # 处理 pandas Series
    if HAS_PANDAS and isinstance(data, pd.Series):
        return sanitize_for_json(data.to_dict())

    # 处理 numpy 数组
    if HAS_NUMPY and isinstance(data, np.ndarray):
        return sanitize_for_json(data.tolist())

    # 处理字典
    if isinstance(data, dict):
        return {key: sanitize_for_json(value) for key, value in data.items()}

    # 处理列表
    if isinstance(data, list):
        return [sanitize_for_json(item) for item in data]

    # 处理浮点数
    if isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return data

    # 处理 numpy 浮点数
    if HAS_NUMPY and isinstance(data, (np.float32, np.float64)):
        if np.isnan(data) or np.isinf(data):
            return None
        return float(data)

    # 处理 numpy 整数
    if HAS_NUMPY and isinstance(data, (np.int32, np.int64)):
        return int(data)

    # 其他类型直接返回
    return data


def clean_dataframe_for_json(df: "pd.DataFrame", orient: str = "records") -> Union[List[Dict], Dict]:
    """
    清理 DataFrame 并转换为 JSON 兼容格式
    
    Args:
        df: pandas DataFrame
        orient: 输出格式 ('records', 'dict', 'list', 'series', 'split', 'index')
        
    Returns:
        清理后的数据
    """
    if not HAS_PANDAS:
        return []

    # 替换 NaN 和 Infinity
    import numpy as np
    df_clean = df.replace({
        np.nan: None,
        float('inf'): None,
        float('-inf'): None
    })

    # 转换为指定格式
    result = df_clean.to_dict(orient=orient)

    # 进一步清理
    return sanitize_for_json(result)
