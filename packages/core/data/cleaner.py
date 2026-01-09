"""
数据清理器

提供数据清洗和标准化功能。
"""

from typing import Any, Dict, Optional

import pandas as pd


class DataCleaner:
    """
    数据清理器

    用于清洗和标准化金融数据，包括：
    - 缺失值处理
    - 异常值过滤
    - 数据格式标准化
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化数据清理器

        Args:
            config: 清理配置
        """
        self._config = config or {}

    def clean(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        清理数据

        Args:
            data: 原始数据

        Returns:
            清理后的数据
        """
        if data.empty:
            return data

        result = data.copy()

        # 处理缺失值
        if self._config.get("fill_na", True):
            result = self._fill_missing_values(result)

        # 移除重复行
        if self._config.get("drop_duplicates", True):
            result = result.drop_duplicates()

        return result

    def _fill_missing_values(self, data: pd.DataFrame) -> pd.DataFrame:
        """填充缺失值"""
        method = self._config.get("fill_method", "ffill")
        if method == "ffill":
            return data.ffill()
        elif method == "bfill":
            return data.bfill()
        elif method == "zero":
            return data.fillna(0)
        else:
            return data

    def validate(self, data: pd.DataFrame) -> bool:
        """
        验证数据质量

        Args:
            data: 待验证数据

        Returns:
            是否通过验证
        """
        if data.empty:
            return False

        # 检查是否有全空列
        if data.isna().all().any():
            return False

        return True
