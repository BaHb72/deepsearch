"""
AmazingData API 基础模块
提供共享的基类、模型和工具函数
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Optional, TypeAlias, cast

import pandas as pd
from core.infrastructure.providers.interfaces.base import TGWError
from fastapi import HTTPException
from loguru import logger

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


async def get_amazingdata_provider():
    """
    获取 AmazingData DaskAdapter 实例

    通过 DaskInitManager 获取已注册的 DaskAdapter，该 adapter 通过 Redis 任务队列
    与 Worker 上的 AmazingDataActor 通信，完全避免直连 SDK 的单连接限制和事件循环冲突。

    注意：此函数依赖 require_amazingdata_ready 守卫（在 router 级别注入），
    确保调用时 DaskAdapter 已就绪。

    Returns:
        AmazingDataDaskAdapter 实例

    Raises:
        HTTPException: DaskAdapter 不可用时
    """
    from core.compute.dask_init_state import get_dask_init_manager_sync

    from apps.api.api.provider_deps import resolve_provider

    provider = await resolve_provider("amazingdata", strict=False)
    if provider is not None:
        is_initialized = getattr(provider, "_initialized", True)
        if is_initialized:
            return provider

    manager = get_dask_init_manager_sync()

    if manager is not None:
        adapter = manager.amazingdata_adapter
        if adapter is not None and getattr(adapter, "_initialized", False):
            return adapter

    # 如果到这里说明 require_amazingdata_ready 守卫未生效或状态异常
    raise HTTPException(
        status_code=503,
        detail="AmazingData 数据源不可用，Dask Worker 可能尚未就绪",
    )


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
            # 返回空结构而非原始对象，避免序列化错误
            return {"data": [], "columns": [], "count": 0, "error": str(exc)}

    # 确保返回值是JSON可序列化的基础类型
    if isinstance(data, (str, int, float, bool, type(None))):
        return data

    # 其他类型转为字符串表示
    try:
        return str(data)
    except Exception:
        return {"error": f"无法序列化类型: {type(data).__name__}"}


def ensure_dataframe(data: object) -> pd.DataFrame | None:
    """辅助函数：将输入安全转换为 DataFrame，无法转换时返回 None。

    支持的转换类型：
    - pd.DataFrame: 直接返回
    - pd.Series: 转换为 DataFrame
    - Mapping (dict等): 尝试创建 DataFrame
    - Sequence (list等): 尝试创建 DataFrame
    - 具有 to_dataframe/to_frame 方法的对象
    """
    if data is None:
        return None

    # 直接是 DataFrame
    if isinstance(data, pd.DataFrame):
        return data

    # pickle反序列化后的DataFrame可能类型检测失败，检查类名
    type_name = type(data).__name__
    if type_name == "DataFrame":
        # 可能是pickle反序列化后的DataFrame，尝试重新转换
        try:
            return pd.DataFrame(data)
        except Exception:
            pass

    # pd.Series 转换为 DataFrame
    if isinstance(data, pd.Series):
        return data.to_frame()

    # 检查是否有 to_dataframe 或 to_frame 方法
    if hasattr(data, "to_dataframe") and callable(getattr(data, "to_dataframe")):
        try:
            result = data.to_dataframe()
            if isinstance(result, pd.DataFrame):
                return result
        except Exception:
            pass

    if hasattr(data, "to_frame") and callable(getattr(data, "to_frame")):
        try:
            result = data.to_frame()
            if isinstance(result, pd.DataFrame):
                return result
        except Exception:
            pass

    # Mapping (dict) 类型尝试转换
    if isinstance(data, Mapping):
        try:
            return pd.DataFrame(data)
        except Exception:
            try:
                return pd.DataFrame([data])
            except Exception:
                pass

    # Sequence (list) 类型尝试转换
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        try:
            return pd.DataFrame(data)
        except Exception:
            pass

    return None


def _is_tgw_related_error(error_msg: str) -> bool:
    """识别是否为TGW相关错误"""
    tgw_patterns = [
        "tgw",
        "not login",
        "login first",
        "未登录",
        "登录失败",
        "connection",
        "timeout",
        "超时",
        "连接失败",
        "push_init_failed",
        "进程崩溃",
        "network",
        "socket",
        "sdk unavailable",
        "sdk not detected",
        "未连接",
    ]
    error_lower = error_msg.lower()
    return any(pattern in error_lower for pattern in tgw_patterns)


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

    # TGW相关错误返回503，表示服务暂时不可用
    if isinstance(error, TGWError):
        error_code = getattr(error, "error_code", None)
        is_recoverable = getattr(error, "is_recoverable", False)
        return {
            "success": False,
            "error": error_msg,
            "error_type": "TGW_ERROR",
            "error_code": error_code,
            "api": api_name,
            "status_code": 503,
            "recoverable": is_recoverable,
            "suggestion": "TGW网关连接异常，请检查网络或稍后重试",
        }

    # 根据错误消息模式识别TGW相关错误
    if _is_tgw_related_error(error_msg):
        return {
            "success": False,
            "error": error_msg,
            "error_type": "TGW_ERROR",
            "api": api_name,
            "status_code": 503,
            "recoverable": True,
            "suggestion": "TGW网关连接异常，请检查网络或稍后重试",
        }

    # 根据错误类型返回不同的状态码
    if "login" in error_msg.lower() or "auth" in error_msg.lower():
        status_code = 401
    elif "not found" in error_msg.lower():
        status_code = 404
    elif "timeout" in error_msg.lower():
        status_code = 408
    else:
        status_code = 500

    # 获取错误堆栈信息
    import traceback

    tb_info = traceback.format_exc()

    response: JSONDict = {
        "success": False,
        "error": error_msg,
        "api": api_name,
        "status_code": status_code,
        "traceback": tb_info,
    }
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


def _ensure_json_serializable(data: object) -> JSONValue:
    """递归确保数据是JSON可序列化的类型

    处理DataFrame、Series、Mapping、Sequence等复杂类型，
    确保返回给前端的数据都可以被JSON.stringify处理。
    """
    if data is None:
        return None

    # 基础类型直接返回
    if isinstance(data, (str, int, float, bool)):
        return data

    # pandas类型特殊处理
    if isinstance(data, pd.DataFrame):
        return dataframe_to_dict(data)

    if isinstance(data, pd.Series):
        return dataframe_to_dict(data.to_frame())

    # numpy类型处理
    if hasattr(data, "item") and callable(getattr(data, "item")):
        try:
            return data.item()
        except Exception:
            pass

    # 检查类名（pickle反序列化后的DataFrame）
    type_name = type(data).__name__
    if type_name == "DataFrame":
        try:
            return dataframe_to_dict(pd.DataFrame(data))
        except Exception:
            pass

    # Mapping类型递归处理
    if isinstance(data, Mapping):
        return {str(k): _ensure_json_serializable(v) for k, v in data.items()}

    # Sequence类型递归处理
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        return [_ensure_json_serializable(item) for item in data]

    # Timestamp类型
    if isinstance(data, (pd.Timestamp, datetime)):
        return data.isoformat() if hasattr(data, "isoformat") else str(data)

    # 其他类型尝试转换为字符串
    try:
        return str(data)
    except Exception:
        return f"<无法序列化: {type(data).__name__}>"


def format_response(
    success: bool, data: JSONValue | None = None, error: str | None = None, **kwargs: JSONValue
) -> JSONDict:
    """
    格式化API响应

    自动确保所有数据都是JSON可序列化的类型。

    Args:
        success: 是否成功
        data: 响应数据
        error: 错误信息
        **kwargs: 附加字段

    Returns:
        格式化后的响应字典（保证可JSON序列化）
    """
    response: JSONDict = {"success": success, "timestamp": pd.Timestamp.now().isoformat()}

    if success:
        # 确保data是JSON可序列化的，即使是None也提供空数据结构
        if data is not None:
            response["data"] = _ensure_json_serializable(data)
        else:
            response["data"] = {"data": [], "columns": [], "count": 0}
    elif not success and error:
        response["error"] = error

    # 添加额外字段，同时确保可序列化
    for key, value in kwargs.items():
        response[key] = _ensure_json_serializable(value)

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
    digits = "".join(ch for ch in text_value if ch.isdigit())
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
            mask = (
                data[column]
                .apply(normalize_date_int)
                .apply(lambda value: value is not None and start_date <= value <= end_date)
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
    # 确保target是字符串类型再调用.lower()
    if not isinstance(target, str):
        target = str(target)
    columns_lower = {col.lower() for col in columns}
    compare_value = target.lower() if case_insensitive else target
    for column in data.columns:
        # 确保column是字符串后再调用lower()
        column_str = str(column)
        if column_str.lower() in columns_lower:
            series = data[column].astype(str)
            if case_insensitive:
                mask = series.str.lower() == compare_value
            else:
                mask = series == target
            return cast(pd.DataFrame, data.loc[mask])
    return data
