"""
AmazingData API 基础模块
提供共享的基类、模型和工具函数
"""

from typing import Optional, Dict, Any, List
from loguru import logger
import pandas as pd
from fastapi import HTTPException

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_extended import AmazingDataExtended
from deepsearch.webui.api.providers import DataProviderFactory, DataSourceType


async def get_amazingdata_provider() -> AmazingDataExtended:
    """
    获取AmazingData提供者实例

    Returns:
        AmazingDataExtended实例

    Raises:
        HTTPException: 获取提供者失败时
    """
    try:
        provider = await DataProviderFactory.get_provider(DataSourceType.AMAZINGDATA)
        if not isinstance(provider, AmazingDataExtended):
            # 如果不是扩展版本，尝试创建扩展版本
            from deepsearch.config import get_config
            config = get_config()
            amazingdata_config = config.data_sources.amazingdata.model_dump()
            provider = AmazingDataExtended(amazingdata_config)
            await provider.initialize()
        return provider
    except Exception as e:
        logger.error(f"获取AmazingData提供者失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get AmazingData provider: {e}")


def dataframe_to_dict(df: Optional[pd.DataFrame]) -> Optional[Dict]:
    """
    将DataFrame转换为字典

    Args:
        df: pandas DataFrame

    Returns:
        字典格式的数据
    """
    if df is None:
        return None

    if df.empty:
        return {"data": [], "columns": [], "count": 0}

    try:
        # 处理时间类型
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype(str)

        return {
            "data": df.to_dict(orient='records'),
            "columns": df.columns.tolist(),
            "count": len(df),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()}
        }
    except Exception as e:
        logger.error(f"DataFrame转换失败: {e}")
        return {
            "data": [],
            "columns": [],
            "count": 0,
            "error": str(e)
        }


def handle_api_error(api_name: str, error: Exception) -> Dict:
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

    return {
        "success": False,
        "error": error_msg,
        "api": api_name,
        "status_code": status_code
    }


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
    except:
        return False


def format_response(success: bool, data: Any = None, error: str = None, **kwargs) -> Dict:
    """
    格式化API响应

    Args:
        success: 是否成功
        data: 响应数据
        error: 错误信息
        **kwargs: 其他附加字段

    Returns:
        格式化的响应字典
    """
    response = {
        "success": success,
        "timestamp": pd.Timestamp.now().isoformat()
    }

    if success and data is not None:
        response["data"] = data
    elif not success and error:
        response["error"] = error

    # 添加额外字段
    response.update(kwargs)

    return response