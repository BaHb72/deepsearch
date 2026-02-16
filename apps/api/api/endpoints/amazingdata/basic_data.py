"""
AmazingData 核心基础数据 API
提供证券基础信息、交易日历、历史代码等查询接口
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .base import (
    DEFAULT_LOCAL_PATH,
    JSONDict,
    dataframe_to_dict,
    ensure_dataframe,
    filter_dataframe_by_dates,
    format_response,
    get_amazingdata_provider,
    normalize_date_int,
    validate_date_range,
)

router = APIRouter(tags=["AmazingData-基础数据"])


class FactorRequest(BaseModel):
    """复权因子请求"""

    code_list: List[str] = Field(..., description="证券代码列表")
    begin_date: int = Field(..., description="起始日期，格式 YYYYMMDD")
    end_date: int = Field(..., description="结束日期，格式 YYYYMMDD")
    local_path: Optional[str] = Field(None, description="本地缓存路径，默认使用系统路径")
    is_local: bool = Field(True, description="是否优先读取本地缓存，默认 True")


class HistCodeListRequest(BaseModel):
    """历史代码列表请求"""

    security_type: str = Field("EXTRA_STOCK_A_SH_SZ", description="证券类型")
    start_date: int = Field(..., description="起始日期，格式 YYYYMMDD")
    end_date: int = Field(..., description="结束日期，格式 YYYYMMDD")
    local_path: Optional[str] = Field(None, description="本地缓存路径，默认使用系统路径")


@router.get("/code-info", summary="获取每日证券信息")
async def get_code_info(
    security_type: str = Query("EXTRA_STOCK_A", description="证券类型，默认沪深 A 股")
) -> JSONDict:
    """获取当前交易日的全部证券基础信息"""
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_code_info(security_type)
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            security_type=security_type,
        )
    except Exception as exc:  # pragma: no cover - FastAPI 会统一处理异常
        return format_response(success=False, error=str(exc), security_type=security_type)


@router.get("/calendar", summary="获取交易日历")
async def get_calendar(
    market: str = Query("SH", description="市场标识，SH 或 SZ"),
    data_type: str = Query("str", description="返回类型：str 或 datetime"),
    begin_date: Optional[int] = Query(None, description="起始日期 YYYYMMDD，可选"),
    end_date: Optional[int] = Query(None, description="结束日期 YYYYMMDD，可选"),
) -> JSONDict:
    """查询指定市场的交易日列表，可选本地过滤日期区间"""
    if begin_date and end_date and not validate_date_range(begin_date, end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_calendar(market=market)  # Actor 只接受 market 参数
        filtered = result
        if result is not None and (begin_date is not None or end_date is not None):
            start = begin_date if begin_date is not None else end_date
            end = end_date if end_date is not None else begin_date
            if start is not None and end is not None:
                filtered = [
                    value
                    for value in result
                    if (normalized := normalize_date_int(value)) is not None
                    and start <= normalized <= end
                ]
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            market=market,
            data_type=data_type,
            begin_date=begin_date,
            end_date=end_date,
        )
    except Exception as exc:  # pragma: no cover
        return format_response(
            success=False,
            error=str(exc),
            market=market,
            data_type=data_type,
            begin_date=begin_date,
            end_date=end_date,
        )


@router.post("/backward-factor", summary="获取后复权因子")
async def get_backward_factor(request: FactorRequest) -> JSONDict:
    """下载并按日期过滤后复权因子"""
    if not validate_date_range(request.begin_date, request.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    local_path = request.local_path or DEFAULT_LOCAL_PATH

    try:
        provider = await get_amazingdata_provider()
        raw = await provider.get_backward_factor(
            request.code_list,
            local_path,
            request.is_local,
        )
        filtered_df = ensure_dataframe(raw)
        if filtered_df is not None:
            filtered_df = filter_dataframe_by_dates(
                filtered_df,
                request.begin_date,
                request.end_date,
            )
        payload_source = filtered_df if filtered_df is not None else raw
        return format_response(
            success=True,
            data=dataframe_to_dict(payload_source),
            code_count=len(request.code_list),
            date_range=f"{request.begin_date}-{request.end_date}",
            local_path=local_path,
        )
    except Exception as exc:  # pragma: no cover
        return format_response(success=False, error=str(exc), code_list=request.code_list)


@router.post("/history-stock-status", summary="获取历史证券状态")
async def get_history_stock_status(request: FactorRequest) -> JSONDict:
    """获取并按日期过滤历史停复牌、ST 等状态"""
    if not validate_date_range(request.begin_date, request.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    local_path = request.local_path or DEFAULT_LOCAL_PATH

    try:
        provider = await get_amazingdata_provider()
        raw = await provider.get_history_stock_status(
            request.code_list,
            local_path,
            request.is_local,
        )
        filtered_df = ensure_dataframe(raw)
        if filtered_df is not None:
            filtered_df = filter_dataframe_by_dates(
                filtered_df,
                request.begin_date,
                request.end_date,
            )
        payload_source = filtered_df if filtered_df is not None else raw
        return format_response(
            success=True,
            data=dataframe_to_dict(payload_source),
            code_count=len(request.code_list),
            date_range=f"{request.begin_date}-{request.end_date}",
            local_path=local_path,
        )
    except Exception as exc:  # pragma: no cover
        return format_response(success=False, error=str(exc), code_list=request.code_list)


@router.post("/hist-code-list", summary="获取历史代码列表")
async def get_hist_code_list(request: HistCodeListRequest) -> JSONDict:
    """查询历史代码清单"""
    if not validate_date_range(request.start_date, request.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    local_path = request.local_path or DEFAULT_LOCAL_PATH

    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_hist_code_list(
            security_type=request.security_type,
            start_date=request.start_date,
            end_date=request.end_date,
            local_path=local_path,
        )
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            security_type=request.security_type,
            date_range=f"{request.start_date}-{request.end_date}",
            local_path=local_path,
        )
    except Exception as exc:  # pragma: no cover
        return format_response(success=False, error=str(exc), security_type=request.security_type)


@router.get("/code-list", summary="获取当日代码列表")
async def get_code_list(
    security_type: str = Query("EXTRA_STOCK_A", description="证券类型")
) -> JSONDict:
    """获取指定市场的当日代码列表"""
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_code_list(security_type)
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            security_type=security_type,
        )
    except Exception as exc:  # pragma: no cover
        return format_response(success=False, error=str(exc), security_type=security_type)


@router.get("/bj-code-mapping", summary="获取北交所代码映射")
async def get_bj_code_mapping() -> JSONDict:
    """查询北交所旧新代码映射关系"""
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_bj_code_mapping()
        return format_response(success=True, data=dataframe_to_dict(result))
    except Exception as exc:  # pragma: no cover
        return format_response(success=False, error=str(exc))
