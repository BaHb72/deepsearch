"""
JSON sanitization utilities

处理 NaN、Infinity 等非 JSON 兼容的值
"""
from __future__ import annotations


import math
from typing import Any, Dict, List, Union, cast

np: Any
try:
    import numpy as _np
except ImportError:
    HAS_NUMPY = False
    np = None
else:
    HAS_NUMPY = True
    np = _np

pd: Any
try:
    import pandas as _pd
except ImportError:
    HAS_PANDAS = False
    pd = None
else:
    HAS_PANDAS = True
    pd = _pd

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
        df_clean = data.replace([math.inf, -math.inf], None)
        df_clean = df_clean.where(pd.notna(df_clean), None)
        return df_clean.to_dict(orient="records")

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


def sanitize_data(data: Any) -> Any:
    """
    清理数据中的 NaN 和 Infinity 值（别名函数，用于向后兼容）

    Args:
        data: 需要清理的数据

    Returns:
        清理后的数据，NaN/Infinity 替换为 None
    """
    return sanitize_for_json(data)


def clean_dataframe_for_json(
    df: Any, orient: str = "records"
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Convert a pandas DataFrame into JSON-friendly data."""
    if not HAS_PANDAS:
        return []

    # Replace NaN and Infinity values
    df_clean = df.replace([math.inf, -math.inf], None)
    if HAS_NUMPY and np is not None:
        df_clean = df_clean.replace({np.nan: None})
    df_clean = df_clean.where(pd.notna(df_clean), None)

    # Convert to the requested orientation
    result = df_clean.to_dict(orient=orient)

    # Final sanitation pass
    sanitized = sanitize_for_json(result)
    return cast(Union[List[Dict[str, Any]], Dict[str, Any]], sanitized)
