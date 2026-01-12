"""
AmazingData 融资融券与龙虎榜数据接口
修正调用签名以匹配 provider，并补充本地过滤逻辑
"""

from typing import List, Optional, Sequence, cast

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from .base import (
    JSONDict,
    dataframe_to_dict,
    filter_dataframe_by_dates,
    filter_dataframe_by_value,
    format_response,
    get_amazingdata_provider,
    normalize_date_int,
)

router = APIRouter(tags=["AmazingData-融资融券"])


_DATE_COLUMNS_MARGIN = ("trade_date", "TRADE_DATE", "date", "DATE")
_DATE_COLUMNS_LONGHU = ("trade_date", "TRADE_DATE", "date", "DATE", "tradeDate")
_CODE_COLUMNS = ("code", "CODE", "symbol", "SYMBOL")
_MARKET_COLUMNS = ("market", "MARKET", "exchange", "EXCHANGE")
_REASON_COLUMNS = ("reason", "REASON", "desc", "DESC")


def _apply_date_filter(
    data: Optional[pd.DataFrame], start: Optional[str], end: Optional[str], columns
) -> Optional[pd.DataFrame]:
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
    narrowed = filter_dataframe_by_dates(data, effective_start, effective_end, columns=columns)
    if isinstance(narrowed, pd.DataFrame):
        return narrowed
    return data


def _apply_column_selection(
    data: Optional[pd.DataFrame], columns: Optional[Sequence[str]]
) -> Optional[pd.DataFrame]:
    if data is None or data.empty or not columns:
        return data
    valid = [column for column in columns if column in data.columns]
    if not valid:
        return data
    return cast(pd.DataFrame, data.loc[:, valid])


@router.get("/margin-summary", summary="获取融资融券汇总")
async def get_margin_summary(
    code: Optional[str] = Query(None, description="证券代码，示例 SH.600000"),
    start_date: Optional[str] = Query(None, description="起始日期，格式 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式 YYYY-MM-DD"),
    market: Optional[str] = Query(None, description="市场类型，SH/SZ/ALL"),
) -> JSONDict:
    """查询融资融券总体情况，并支持本地过滤"""
    try:
        provider = await get_amazingdata_provider()
        raw = await provider.get_margin_summary()
        filtered = raw
        if isinstance(filtered, pd.DataFrame):
            filtered = _apply_date_filter(filtered, start_date, end_date, _DATE_COLUMNS_MARGIN)
            if code:
                filtered = filter_dataframe_by_value(filtered, code, columns=_CODE_COLUMNS)
            if market:
                filtered = filter_dataframe_by_value(filtered, market, columns=_MARKET_COLUMNS)
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            filters={
                "code": code,
                "start_date": start_date,
                "end_date": end_date,
                "market": market,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/margin-detail", summary="获取融资融券明细")
async def get_margin_detail(
    code: str = Query(..., description="证券代码，例如 SH.600000"),
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    fields: Optional[List[str]] = Query(None, description="需要保留的列名列表"),
) -> JSONDict:
    """查询指定证券的融资融券明细，支持日期过滤和列过滤"""
    try:
        provider = await get_amazingdata_provider()
        raw = await provider.get_margin_detail([code])
        filtered = raw
        if isinstance(filtered, pd.DataFrame):
            filtered = _apply_date_filter(filtered, start_date, end_date, _DATE_COLUMNS_MARGIN)
            filtered = _apply_column_selection(filtered, fields)
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            code=code,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/long-hu-bang", summary="获取龙虎榜数据")
async def get_long_hu_bang(
    code: Optional[str] = Query(None, description="证券代码，示例 SH.600000"),
    date: Optional[str] = Query(None, description="交易日期 YYYY-MM-DD，可选"),
    reason: Optional[str] = Query(None, description="上榜原因，可选"),
    limit: int = Query(100, description="返回记录上限"),
) -> JSONDict:
    """查询龙虎榜信息，并允许按日期、原因等条件过滤"""
    if code is None:
        raise HTTPException(status_code=400, detail="code is required for long_hu_bang query")

    try:
        provider = await get_amazingdata_provider()
        raw = await provider.get_long_hu_bang([code])
        filtered = raw
        if isinstance(filtered, pd.DataFrame):
            filtered = _apply_date_filter(filtered, date, date, _DATE_COLUMNS_LONGHU)
            if reason:
                filtered = filter_dataframe_by_value(filtered, reason, columns=_REASON_COLUMNS)
            if limit > 0 and isinstance(filtered, pd.DataFrame):
                filtered = filtered.head(limit)
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            code=code,
            date=date,
            reason=reason,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/block-trading", summary="获取大宗交易数据")
async def get_block_trading(
    code: Optional[str] = Query(None, description="证券代码，示例 SH.600000"),
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(100, description="返回记录上限"),
) -> JSONDict:
    """
    获取大宗交易数据

    查询指定证券的大宗交易记录，支持日期过滤
    """
    try:
        logger.error("[block-trading] *** ENDPOINT HIT ***")
        provider = await get_amazingdata_provider()
        logger.error(f"[block-trading] Provider type: {type(provider).__name__}")
        logger.error(
            f"[block-trading] has get_block_trading: {hasattr(provider, 'get_block_trading')}"
        )
        logger.warning(f"[block-trading] Provider type: {type(provider).__name__}")
        # 如果指定了code则按单个代码查询，否则查询全市场
        code_list = [code] if code else []
        logger.error(
            f"[block-trading] Calling provider.get_block_trading with code_list={code_list}"
        )
        raw = await provider.get_block_trading(code_list)
        logger.warning(f"[block-trading] Result type: {type(raw).__name__}, is None: {raw is None}")
        if isinstance(raw, pd.DataFrame):
            logger.warning(f"[block-trading] DataFrame: empty={raw.empty}, shape={raw.shape}")
        filtered = raw
        if isinstance(filtered, pd.DataFrame):
            filtered = _apply_date_filter(filtered, start_date, end_date, _DATE_COLUMNS_MARGIN)
            if limit > 0 and isinstance(filtered, pd.DataFrame):
                filtered = filtered.head(limit)
        # DEBUG: 在format_response前打印
        data_result = dataframe_to_dict(filtered)
        logger.warning(
            f"[block-trading] BEFORE RESPONSE: data_result is None: {data_result is None}, type: {type(data_result).__name__}"
        )
        return format_response(
            success=True,
            data=data_result,
            code=code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
