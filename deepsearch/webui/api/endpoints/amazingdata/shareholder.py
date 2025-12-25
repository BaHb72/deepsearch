"""
AmazingData 股东及权益相关接口
修正调用签名并添加本地过滤能力
"""

from typing import Optional

import pandas as pd
from fastapi import APIRouter, Body, HTTPException

from .base import (
    JSONDict,
    dataframe_to_dict,
    filter_dataframe_by_dates,
    filter_dataframe_by_value,
    format_response,
    get_amazingdata_provider,
    normalize_date_int,
)

router = APIRouter(tags=["AmazingData-股权数据"])


_DATE_COLUMNS_GENERAL = (
    "report_date",
    "REPORT_DATE",
    "ann_date",
    "ANN_DATE",
    "notice_date",
    "NOTICE_DATE",
    "change_date",
    "CHANGE_DATE",
    "date",
    "DATE",
)
_YEAR_COLUMNS = ("year", "YEAR", "report_year", "REPORT_YEAR", "dividend_year", "DIVIDEND_YEAR")
_REPORT_TYPE_COLUMNS = ("report_type", "REPORT_TYPE", "type", "TYPE")


def _apply_date_filter(data: Optional[pd.DataFrame], start: Optional[str], end: Optional[str]) -> Optional[pd.DataFrame]:
    if data is None or data.empty:
        return data
    start_int = normalize_date_int(start) if start else None
    end_int = normalize_date_int(end) if end else None
    if start_int is None and end_int is None:
        return data
    if start_int is not None and end_int is not None and start_int > end_int:
        raise HTTPException(status_code=400, detail="Invalid date range")
    effective_start = start_int or end_int
    effective_end = end_int or start_int
    if effective_start is None or effective_end is None:
        return data
    narrowed = filter_dataframe_by_dates(data, effective_start, effective_end, columns=_DATE_COLUMNS_GENERAL)
    if isinstance(narrowed, pd.DataFrame):
        return narrowed
    return data


@router.post("/share-holder", summary="获取十大股东")
async def get_share_holder(
    code: str = Body(..., description="证券代码，例如 SH.600000"),
    report_date: Optional[str] = Body(None, description="报告日期 YYYY-MM-DD，可选"),
    top_n: int = Body(10, description="返回前 N 位股东，默认 10"),
) -> JSONDict:
    """
    3.5.7.1 股东户数
    获取股东户数和前十大股东数据
    """
    try:
        provider = await get_amazingdata_provider()
        raw = await provider.get_share_holder([code])
        filtered = raw
        if isinstance(filtered, pd.DataFrame):
            filtered = _apply_date_filter(filtered, report_date, report_date)
            if top_n > 0 and isinstance(filtered, pd.DataFrame):
                filtered = filtered.head(top_n)
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            code=code,
            report_date=report_date,
            top_n=top_n,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/holder-num", summary="获取股东户数")
async def get_holder_num(
    code: str = Body(..., description="证券代码，例如 SH.600000"),
    start_date: Optional[str] = Body(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Body(None, description="结束日期 YYYY-MM-DD"),
) -> JSONDict:
    """查询股东户数变动情况"""
    try:
        provider = await get_amazingdata_provider()
        raw = await provider.get_holder_num([code])
        filtered = raw
        if isinstance(filtered, pd.DataFrame):
            filtered = _apply_date_filter(filtered, start_date, end_date)
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            code=code,
            start_date=start_date,
            end_date=end_date,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/equity-structure", summary="获取股权结构")
async def get_equity_structure(
    code: str = Body(..., description="证券代码，例如 SH.600000"),
    report_date: Optional[str] = Body(None, description="报告日期 YYYY-MM-DD，可选"),
) -> JSONDict:
    """查询公司股权结构信息"""
    try:
        provider = await get_amazingdata_provider()
        raw = await provider.get_equity_structure([code])
        filtered = raw
        if isinstance(filtered, pd.DataFrame):
            filtered = _apply_date_filter(filtered, report_date, report_date)
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            code=code,
            report_date=report_date,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/equity-pledge-freeze", summary="获取股权质押/冻结")
async def get_equity_pledge_freeze(
    code: str = Body(..., description="证券代码，例如 SH.600000"),
    start_date: Optional[str] = Body(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Body(None, description="结束日期 YYYY-MM-DD"),
) -> JSONDict:
    """查询股权质押及冻结情况"""
    try:
        provider = await get_amazingdata_provider()
        raw = await provider.get_equity_pledge_freeze([code])
        filtered = raw
        if isinstance(filtered, pd.DataFrame):
            filtered = _apply_date_filter(filtered, start_date, end_date)
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            code=code,
            start_date=start_date,
            end_date=end_date,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/equity-restricted", summary="获取限售解禁")
async def get_equity_restricted(
    code: str = Body(..., description="证券代码，例如 SH.600000"),
    start_date: Optional[str] = Body(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Body(None, description="结束日期 YYYY-MM-DD"),
) -> JSONDict:
    """查询限售股解禁计划"""
    try:
        provider = await get_amazingdata_provider()
        raw = await provider.get_equity_restricted([code])
        filtered = raw
        if isinstance(filtered, pd.DataFrame):
            filtered = _apply_date_filter(filtered, start_date, end_date)
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            code=code,
            start_date=start_date,
            end_date=end_date,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/dividend", summary="获取分红送股信息")
async def get_dividend(
    code: str = Body(..., description="证券代码，例如 SH.600000"),
    year: Optional[int] = Body(None, description="分红年度，可选"),
    report_type: Optional[str] = Body(None, description="报告类型，年报/半报/季报等，可选"),
) -> JSONDict:
    """查询分红送转方案"""
    try:
        provider = await get_amazingdata_provider()
        raw = await provider.get_dividend([code])
        filtered = raw
        if isinstance(filtered, pd.DataFrame):
            if year is not None:
                filtered = filter_dataframe_by_value(filtered, str(year), columns=_YEAR_COLUMNS)
            if report_type:
                filtered = filter_dataframe_by_value(filtered, report_type, columns=_REPORT_TYPE_COLUMNS)
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            code=code,
            year=year,
            report_type=report_type,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/right-issue", summary="获取配股信息")
async def get_right_issue(
    code: str = Body(..., description="证券代码，例如 SH.600000"),
    start_date: Optional[str] = Body(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Body(None, description="结束日期 YYYY-MM-DD"),
) -> JSONDict:
    """查询配股发行方案"""
    try:
        provider = await get_amazingdata_provider()
        raw = await provider.get_right_issue([code])
        filtered = raw
        if isinstance(filtered, pd.DataFrame):
            filtered = _apply_date_filter(filtered, start_date, end_date)
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            code=code,
            start_date=start_date,
            end_date=end_date,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
