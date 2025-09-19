"""
AmazingData 基础数据API模块
包含证券信息、交易日历、复权因子等基础数据接口
"""

from fastapi import APIRouter, HTTPException, Query
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
router = APIRouter(tags=["AmazingData-基础数据"])


# ================== 请求模型 ==================

class CodeListRequest(BaseModel):
    """代码列表请求"""
    security_type: str = Field("EXTRA_STOCK_A", description="证券类型")


class StockBasicRequest(BaseModel):
    """股票基础信息请求"""
    code_list: List[str] = Field(..., description="股票代码列表")
    local_path: Optional[str] = Field(None, description="本地存储路径")
    is_local: bool = Field(False, description="是否使用本地存储")


class FactorRequest(BaseModel):
    """复权因子请求"""
    code_list: List[str] = Field(..., description="代码列表")
    begin_date: int = Field(..., description="开始日期")
    end_date: int = Field(..., description="结束日期")
    local_path: Optional[str] = Field(None, description="本地存储路径")
    is_local: bool = Field(False, description="是否使用本地存储")


class HistCodeListRequest(BaseModel):
    """历史代码列表请求"""
    security_type: str = Field("EXTRA_STOCK_A_SH_SZ", description="证券类型")
    start_date: int = Field(..., description="开始日期")
    end_date: int = Field(..., description="结束日期")
    local_path: Optional[str] = Field(None, description="本地存储路径")


# ================== API接口 ==================

@router.get("/code-info", summary="获取每日最新证券信息")
async def get_code_info(
    security_type: str = Query("EXTRA_STOCK_A", description="证券类型")
):
    """
    获取每日最新的证券信息

    Args:
        security_type: 证券类型，如EXTRA_STOCK_A

    Returns:
        证券信息列表
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_code_info(security_type)
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            security_type=security_type
        )
    except Exception as e:
        return format_response(
            success=False,
            error=str(e),
            security_type=security_type
        )


@router.get("/calendar", summary="获取交易日历")
async def get_calendar(
    begin_date: int = Query(..., description="开始日期，如20200101"),
    end_date: int = Query(..., description="结束日期，如20251231")
):
    """
    获取指定日期范围的交易日历

    Args:
        begin_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)

    Returns:
        交易日历数据
    """
    if not validate_date_range(begin_date, end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_calendar(begin_date, end_date)
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            begin_date=begin_date,
            end_date=end_date
        )
    except Exception as e:
        return format_response(
            success=False,
            error=str(e),
            begin_date=begin_date,
            end_date=end_date
        )


@router.post("/stock-basic", summary="获取股票基础信息")
async def get_stock_basic(request: StockBasicRequest):
    """
    获取股票基础信息

    Args:
        request: 股票基础信息请求

    Returns:
        股票基础信息数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_stock_basic(
            code_list=request.code_list,
            is_local=request.is_local,
            local_path=request.local_path
        )
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list)
        )
    except Exception as e:
        return format_response(
            success=False,
            error=str(e),
            code_list=request.code_list
        )


@router.post("/backward-factor", summary="获取后复权因子")
async def get_backward_factor(request: FactorRequest):
    """
    获取后复权因子数据

    Args:
        request: 复权因子请求

    Returns:
        后复权因子数据
    """
    if not validate_date_range(request.begin_date, request.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_backward_factor(
            code_list=request.code_list,
            begin_date=request.begin_date,
            end_date=request.end_date,
            is_local=request.is_local,
            local_path=request.local_path
        )
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
            date_range=f"{request.begin_date}-{request.end_date}"
        )
    except Exception as e:
        return format_response(
            success=False,
            error=str(e),
            code_list=request.code_list
        )


@router.post("/adj-factor", summary="获取复权因子")
async def get_adj_factor(request: FactorRequest):
    """
    获取复权因子数据

    Args:
        request: 复权因子请求

    Returns:
        复权因子数据
    """
    if not validate_date_range(request.begin_date, request.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_adj_factor(
            code_list=request.code_list,
            begin_date=request.begin_date,
            end_date=request.end_date,
            is_local=request.is_local,
            local_path=request.local_path
        )
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
            date_range=f"{request.begin_date}-{request.end_date}"
        )
    except Exception as e:
        return format_response(
            success=False,
            error=str(e),
            code_list=request.code_list
        )


@router.post("/history-stock-status", summary="获取历史证券状态")
async def get_history_stock_status(request: FactorRequest):
    """
    获取历史证券状态（停牌、ST等）

    Args:
        request: 历史状态请求

    Returns:
        历史证券状态数据
    """
    if not validate_date_range(request.begin_date, request.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_history_stock_status(
            code_list=request.code_list,
            begin_date=request.begin_date,
            end_date=request.end_date,
            is_local=request.is_local,
            local_path=request.local_path
        )
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
            date_range=f"{request.begin_date}-{request.end_date}"
        )
    except Exception as e:
        return format_response(
            success=False,
            error=str(e),
            code_list=request.code_list
        )


@router.post("/hist-code-list", summary="获取历史代码列表")
async def get_hist_code_list(request: HistCodeListRequest):
    """
    获取历史代码列表

    Args:
        request: 历史代码列表请求

    Returns:
        历史代码列表数据
    """
    if not validate_date_range(request.start_date, request.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_hist_code_list(
            security_type=request.security_type,
            start_date=request.start_date,
            end_date=request.end_date,
            local_path=request.local_path
        )
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            security_type=request.security_type,
            date_range=f"{request.start_date}-{request.end_date}"
        )
    except Exception as e:
        return format_response(
            success=False,
            error=str(e),
            security_type=request.security_type
        )


@router.get("/code-list", summary="获取每日最新代码列表")
async def get_code_list(
    security_type: str = Query("EXTRA_STOCK_A", description="证券类型")
):
    """
    获取每日最新的代码列表

    Args:
        security_type: 证券类型

    Returns:
        代码列表数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_code_list(security_type)
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            security_type=security_type
        )
    except Exception as e:
        return format_response(
            success=False,
            error=str(e),
            security_type=security_type
        )


@router.get("/future-code-list", summary="获取期货代码列表")
async def get_future_code_list():
    """
    获取期货代码列表

    Returns:
        期货代码列表数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_future_code_list()
        return format_response(
            success=True,
            data=dataframe_to_dict(result)
        )
    except Exception as e:
        return format_response(
            success=False,
            error=str(e)
        )


@router.get("/bj-code-mapping", summary="获取北交所代码映射")
async def get_bj_code_mapping():
    """
    获取北交所代码映射关系

    Returns:
        北交所代码映射数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_bj_code_mapping()
        return format_response(
            success=True,
            data=dataframe_to_dict(result)
        )
    except Exception as e:
        return format_response(
            success=False,
            error=str(e)
        )