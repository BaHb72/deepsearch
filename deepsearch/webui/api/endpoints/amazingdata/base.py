"""
AmazingData API 基础模块
提供共享的基类、模型和工具函数
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Optional, TypeAlias, cast

import pandas as pd
from fastapi import HTTPException
from loguru import logger

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_extended import (
    AmazingDataExtended,
)
from deepsearch.webui.api.providers import DataProviderFactory, DataSourceType

DEFAULT_LOCAL_PATH = "D://AmazingData_local_data//"
_DATE_COLUMN_CANDIDATES: tuple[str, ...] = (
    "report_date",
    "REPORT_DATE",
    "ann_date",
    "ANN_DATE",
    "trade_date",
    "TRADE_DATE",
    "date",
    "DATE",
)

JSONValue: TypeAlias = object
JSONDict: TypeAlias = dict[str, JSONValue]

async def get_amazingdata_provider() -> AmazingDataExtended:
    """
    获取AmazingData提供者实例

    Returns:
        AmazingDataExtended实例

    Raises:
        HTTPException: 获取提供者失败时
    """
    try:
        provider = await DataProviderFactory.get_provider_async(DataSourceType.AMAZINGDATA)
        if not isinstance(provider, AmazingDataExtended):
            # 如果不是扩展版本，尝试创建扩展版本
            from deepsearch.config import get_config

            config = get_config()
            data_sources_section = getattr(config, "data_sources", None)
            amazingdata_config = None
            if data_sources_section is not None:
                providers_section = getattr(data_sources_section, "providers", None)
                if providers_section is None and data_sources_section is not None and hasattr(data_sources_section,
                                                                                              "model_dump"):
                    providers_section = data_sources_section.model_dump().get("providers")
                if providers_section is not None and hasattr(providers_section, "get"):
                    amazingdata_config = providers_section.get("amazingdata")
            if amazingdata_config is None and data_sources_section is not None and hasattr(data_sources_section,
                                                                                           "model_dump"):
                try:
                    providers_map = data_sources_section.model_dump().get("providers", {})
                except Exception:
                    providers_map = {}
                if isinstance(providers_map, dict):
                    amazingdata_config = providers_map.get("amazingdata")
            if amazingdata_config is None:
                raise HTTPException(status_code=500, detail="AmazingData 配置缺失")
            if hasattr(amazingdata_config, "model_dump"):
                amazingdata_payload = amazingdata_config.model_dump()
            elif isinstance(amazingdata_config, Mapping):
                amazingdata_payload = dict(amazingdata_config)
            else:
                raise HTTPException(status_code=500, detail="AmazingData 配置格式不受支持")
            provider = AmazingDataExtended(amazingdata_payload)
            await provider.initialize()
        return provider
    except Exception as e:
        logger.error(f"获取AmazingData提供者失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get AmazingData provider: {e}")


def dataframe_to_dict(data: object) -> JSONValue:
    """将任意表格或序列数据转换为 JSON 友好结构"""
    if data is None:
        return None

    if isinstance(data, pd.DataFrame):
        if data.empty:
            return {"data": [], "columns": [], "count": 0}

        try:
            for col in data.columns:
                if pd.api.types.is_datetime64_any_dtype(data[col]):
                    data[col] = data[col].astype(str)

            return {
                "data": data.to_dict(orient="records"),
                "columns": data.columns.tolist(),
                "count": len(data),
                "dtypes": {col: str(dtype) for col, dtype in data.dtypes.items()},
            }
        except Exception as exc:
            logger.error(f"DataFrame转换失败: {exc}")
            return {"data": [], "columns": [], "count": 0, "error": str(exc)}

    if isinstance(data, pd.Series):
        return dataframe_to_dict(data.to_frame())

    if isinstance(data, Mapping):
        return {key: dataframe_to_dict(value) for key, value in data.items()}

    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        return {"data": [dataframe_to_dict(item) for item in data], "count": len(data)}

    if hasattr(data, "to_dict") and callable(getattr(data, "to_dict")):
        try:
            return dataframe_to_dict(data.to_dict())
        except Exception as exc:
            logger.warning(f"对象 to_dict 转换失败: {exc}")
            return data

    return data


def ensure_dataframe(data: object) -> pd.DataFrame | None:
    """辅助函数：将输入安全转换为 DataFrame，无法转换时返回 None。"""
    return data if isinstance(data, pd.DataFrame) else None

def handle_api_error(api_name: str, error: Exception) -> JSONDict:
    """
    统一处理API错误

    Args:
        api_name: API名称
        error: 异常对象

    Returns:
        错误响应字典
    """
    error_msg = str(error)
    logger.error(f"AmazingData API [{api_name}] 调用失败: {error_msg}")

    # 根据错误类型返回不同的状态码
    if "login" in error_msg.lower() or "auth" in error_msg.lower():
        status_code = 401
    elif "not found" in error_msg.lower():
        status_code = 404
    elif "timeout" in error_msg.lower():
        status_code = 408
    else:
        status_code = 500

    response: JSONDict = {"success": False, "error": error_msg, "api": api_name, "status_code": status_code}
    return response


def validate_date_range(start_date: int, end_date: int) -> bool:
    """
    验证日期范围

    Args:
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)

    Returns:
        是否有效
    """
    try:
        if start_date > end_date:
            return False

        # 验证日期格式
        start_str = str(start_date)
        end_str = str(end_date)

        if len(start_str) != 8 or len(end_str) != 8:
            return False

        # 简单验证月份和日期
        start_month = int(start_str[4:6])
        start_day = int(start_str[6:8])
        end_month = int(end_str[4:6])
        end_day = int(end_str[6:8])

        if not (1 <= start_month <= 12 and 1 <= end_month <= 12):
            return False

        if not (1 <= start_day <= 31 and 1 <= end_day <= 31):
            return False

        return True
    except Exception:
        return False


def format_response(success: bool, data: JSONValue | None = None, error: str | None = None, **kwargs: JSONValue) -> JSONDict:
    """
    格式化API响应

    Args:
        success: 是否成功
        data: 响应数据
        error: 错误信息
        **kwargs: 附加字段

    Returns:
        格式化后的响应字典
    """
    response: JSONDict = {"success": success, "timestamp": pd.Timestamp.now().isoformat()}

    if success and data is not None:
        response["data"] = data
    elif not success and error:
        response["error"] = error

    # 添加额外字段
    response.update(kwargs)

    return response


def normalize_date_int(value: object) -> Optional[int]:
    """将日期值转换为 YYYYMMDD 整数格式"""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if isinstance(value, (pd.Timestamp, datetime)):
        actual = value.to_pydatetime() if isinstance(value, pd.Timestamp) else value
        return int(actual.strftime("%Y%m%d"))
    text_value = str(value).strip()
    if not text_value:
        return None
    digits = ''.join(ch for ch in text_value if ch.isdigit())
    if len(digits) >= 8:
        try:
            return int(digits[:8])
        except ValueError:
            return None
    return None


def filter_dataframe_by_dates(
    data: pd.DataFrame | None,
    start_date: int,
    end_date: int,
    *,
    columns: Optional[Sequence[str]] = None,
) -> pd.DataFrame | None:
    """根据日期范围筛选 DataFrame，如果无法筛选则返回原始数据"""
    if data is None or data.empty:
        return data
    column_candidates = tuple(columns) if columns else _DATE_COLUMN_CANDIDATES
    columns_lower = {col.lower() for col in column_candidates}
    for column in data.columns:
        if column.lower() in columns_lower:
            mask = data[column].apply(normalize_date_int).apply(
                lambda value: value is not None and start_date <= value <= end_date
            )
            return cast(pd.DataFrame, data.loc[mask])
    if data.index.nlevels == 1:
        index_mask = [
            (normalized is not None and start_date <= normalized <= end_date)
            for normalized in (normalize_date_int(value) for value in data.index)
        ]
        if any(index_mask):
            return cast(pd.DataFrame, data.loc[index_mask])
    return data


def filter_dataframe_by_value(
    data: pd.DataFrame | None,
    target: Optional[str],
    *,
    columns: Sequence[str],
    case_insensitive: bool = True,
) -> pd.DataFrame | None:
    """根据给定取值筛选 DataFrame 指定字段"""
    if target is None or data is None or data.empty:
        return data
    columns_lower = {col.lower() for col in columns}
    compare_value = target.lower() if case_insensitive else target
    for column in data.columns:
        if column.lower() in columns_lower:
            series = data[column].astype(str)
            if case_insensitive:
                mask = series.str.lower() == compare_value
            else:
                mask = series == target
            return cast(pd.DataFrame, data.loc[mask])
    return data
