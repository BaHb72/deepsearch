"""
AmazingData 历史数据API模块
包含历史快照和K线查询接口
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from loguru import logger

from .base import (
    get_amazingdata_provider,
    dataframe_to_dict,
    handle_api_error,
    validate_date_range,
    format_response
)

# 创建路由器
router = APIRouter(tags=["AmazingData-历史数据"])


# ================== 请求模型 ==================

class QuerySnapshotRequest(BaseModel):
    """历史快照查询请求"""
    code_list: List[str] = Field(..., description="代码列表")
    begin_date: int = Field(..., description="开始日期")
    end_date: int = Field(..., description="结束日期")
    is_local: bool = Field(False, description="是否使用本地存储")
    local_path: Optional[str] = Field(None, description="本地存储路径")


class QueryKlineRequest(BaseModel):
    """历史K线查询请求"""
    code_list: List[str] = Field(..., description="代码列表")
    begin_date: int = Field(..., description="开始日期")
    end_date: int = Field(..., description="结束日期")
    period: str = Field("daily", description="K线周期：1min/5min/15min/30min/60min/daily/weekly/monthly")
    adjust_type: str = Field("none", description="复权类型：none(不复权)/forward(前复权)/backward(后复权)")
    is_local: bool = Field(False, description="是否使用本地存储")
    local_path: Optional[str] = Field(None, description="本地存储路径")


# ================== API接口 ==================

@router.post("/query-snapshot", summary="查询历史快照")
async def query_snapshot(request: QuerySnapshotRequest):
    """
    查询历史快照数据

    Args:
        request: 历史快照查询请求

    Returns:
        历史快照数据
    """
    # 验证日期范围
    if not validate_date_range(request.begin_date, request.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    try:
        provider = await get_amazingdata_provider()

        # 调用SDK查询历史快照
        result = await provider.query_snapshot(
            code_list=request.code_list,
            begin_date=request.begin_date,
            end_date=request.end_date,
            is_local=request.is_local,
            local_path=request.local_path
        )

        # 格式化响应
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
            date_range=f"{request.begin_date}-{request.end_date}",
            query_type="snapshot"
        )
    except Exception as e:
        return handle_api_error("query_snapshot", e)


@router.post("/query-kline", summary="查询历史K线")
async def query_kline(request: QueryKlineRequest):
    """
    查询历史K线数据

    Args:
        request: 历史K线查询请求

    Returns:
        历史K线数据
    """
    # 验证日期范围
    if not validate_date_range(request.begin_date, request.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    # 验证K线周期
    valid_periods = ["1min", "5min", "15min", "30min", "60min", "daily", "weekly", "monthly"]
    if request.period not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period. Must be one of: {valid_periods}"
        )

    # 验证复权类型
    valid_adjust_types = ["none", "forward", "backward"]
    if request.adjust_type not in valid_adjust_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid adjust_type. Must be one of: {valid_adjust_types}"
        )

    try:
        provider = await get_amazingdata_provider()

        # 调用SDK查询K线
        result = await provider.query_kline(
            code_list=request.code_list,
            begin_date=request.begin_date,
            end_date=request.end_date,
            period=request.period,
            adjust_type=request.adjust_type,
            is_local=request.is_local,
            local_path=request.local_path
        )

        # 处理结果
        if result is None:
            return format_response(
                success=False,
                error="No data found for the specified parameters",
                code_list=request.code_list
            )

        # 格式化响应
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
            date_range=f"{request.begin_date}-{request.end_date}",
            period=request.period,
            adjust_type=request.adjust_type,
            query_type="kline"
        )
    except Exception as e:
        return handle_api_error("query_kline", e)


@router.post("/batch-query-kline", summary="批量查询K线")
async def batch_query_kline(requests: List[QueryKlineRequest]):
    """
    批量查询多个股票的K线数据

    Args:
        requests: K线查询请求列表

    Returns:
        批量K线数据
    """
    results = []
    errors = []

    try:
        provider = await get_amazingdata_provider()

        for idx, request in enumerate(requests):
            try:
                # 验证日期范围
                if not validate_date_range(request.begin_date, request.end_date):
                    errors.append({
                        "index": idx,
                        "codes": request.code_list,
                        "error": "Invalid date range"
                    })
                    continue

                # 查询K线
                result = await provider.query_kline(
                    code_list=request.code_list,
                    begin_date=request.begin_date,
                    end_date=request.end_date,
                    period=request.period,
                    adjust_type=request.adjust_type,
                    is_local=request.is_local,
                    local_path=request.local_path
                )

                results.append({
                    "index": idx,
                    "codes": request.code_list,
                    "data": dataframe_to_dict(result),
                    "period": request.period,
                    "adjust_type": request.adjust_type
                })

            except Exception as e:
                errors.append({
                    "index": idx,
                    "codes": request.code_list,
                    "error": str(e)
                })

        # 返回批量结果
        return format_response(
            success=len(errors) == 0,
            data={
                "results": results,
                "errors": errors,
                "total": len(requests),
                "success_count": len(results),
                "error_count": len(errors)
            }
        )

    except Exception as e:
        return handle_api_error("batch_query_kline", e)