"""
AmazingData 历史行情 API 模块
覆盖历史快照与 K 线查询接口
"""

from collections.abc import Mapping
from typing import Dict, List, Optional

import pandas as pd
from core.infrastructure.providers.implementations.amazingdata import SnapshotAlignPolicy
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .base import (
    JSONDict,
    dataframe_to_dict,
    filter_dataframe_by_dates,
    format_response,
    get_amazingdata_provider,
    validate_date_range,
)

router = APIRouter(tags=["AmazingData-历史数据"])


class QuerySnapshotRequest(BaseModel):
    """历史快照查询参数"""

    code_list: List[str] = Field(..., description="证券代码列表")
    begin_date: int = Field(..., description="开始日期 YYYYMMDD")
    end_date: int = Field(..., description="结束日期 YYYYMMDD")
    align_policy: SnapshotAlignPolicy = Field(
        default=SnapshotAlignPolicy.NEAREST_PREV,
        description="对齐策略：nearest_prev/strict/passthrough",
    )


class QueryKlineRequest(BaseModel):
    """历史 K 线查询参数"""

    code_list: List[str] = Field(..., description="证券代码列表")
    begin_date: int = Field(..., description="起始日期 YYYYMMDD")
    end_date: int = Field(..., description="结束日期 YYYYMMDD")
    period: str = Field(
        "daily",
        description="K 线周期：1min/5min/15min/30min/60min/daily/weekly/monthly",
    )


def _filter_history_mapping(
    data: Mapping[str, Optional[pd.DataFrame]] | None, begin_date: int, end_date: int
) -> dict[str, pd.DataFrame]:
    """对返回的代码->DataFrame 映射执行日期过滤"""
    if data is None:
        return {}
    filtered: dict[str, pd.DataFrame] = {}
    for code, value in data.items():
        if isinstance(value, pd.DataFrame):
            narrowed = filter_dataframe_by_dates(value, begin_date, end_date)
            if isinstance(narrowed, pd.DataFrame):
                filtered[code] = narrowed
            else:
                filtered[code] = value
    return filtered


@router.post("/query-snapshot", summary="查询历史快照")
async def query_snapshot(request: QuerySnapshotRequest) -> JSONDict:
    """批量查询历史逐日快照信息"""
    if not validate_date_range(request.begin_date, request.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    try:
        provider = await get_amazingdata_provider()
        raw = await provider.query_snapshot(
            code_list=request.code_list,
            begin_date=request.begin_date,
            end_date=request.end_date,
            align_policy=request.align_policy,
        )
        filtered = _filter_history_mapping(raw, request.begin_date, request.end_date)
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            code_count=len(request.code_list),
            date_range=f"{request.begin_date}-{request.end_date}",
            query_type="snapshot",
        )
    except Exception as exc:  # pragma: no cover
        return format_response(success=False, error=str(exc), code_list=request.code_list)


@router.post("/query-kline", summary="查询历史 K 线")
async def query_kline(request: QueryKlineRequest) -> JSONDict:
    """批量查询历史 K 线数据"""
    if not validate_date_range(request.begin_date, request.end_date):
        raise HTTPException(status_code=400, detail="Invalid date range")

    valid_periods = {
        "1min",
        "5min",
        "15min",
        "30min",
        "60min",
        "daily",
        "weekly",
        "monthly",
    }
    if request.period not in valid_periods:
        raise HTTPException(
            status_code=400, detail=f"Invalid period. Must be one of: {sorted(valid_periods)}"
        )

    try:
        provider = await get_amazingdata_provider()
        raw = await provider.query_kline(
            code_list=request.code_list,
            begin_date=request.begin_date,
            end_date=request.end_date,
            period=request.period,
        )
        if raw is None:
            return format_response(
                success=False,
                error="No data found for the specified parameters",
                code_list=request.code_list,
            )

        filtered = _filter_history_mapping(raw, request.begin_date, request.end_date)
        return format_response(
            success=True,
            data=dataframe_to_dict(filtered),
            code_count=len(request.code_list),
            date_range=f"{request.begin_date}-{request.end_date}",
            period=request.period,
            query_type="kline",
        )
    except Exception as exc:  # pragma: no cover
        return format_response(success=False, error=str(exc), code_list=request.code_list)


@router.post("/batch-query-kline", summary="批量查询 K 线")
async def batch_query_kline(requests: List[QueryKlineRequest]) -> JSONDict:
    """批量查询多组参数的 K 线数据"""
    results: List[Dict[str, object]] = []
    errors: List[Dict[str, object]] = []

    try:
        provider = await get_amazingdata_provider()

        for idx, request in enumerate(requests):
            if not validate_date_range(request.begin_date, request.end_date):
                errors.append(
                    {"index": idx, "codes": request.code_list, "error": "Invalid date range"}
                )
                continue

            valid_periods = {
                "1min",
                "5min",
                "15min",
                "30min",
                "60min",
                "daily",
                "weekly",
                "monthly",
            }
            if request.period not in valid_periods:
                errors.append(
                    {
                        "index": idx,
                        "codes": request.code_list,
                        "error": f"Invalid period. Must be one of: {sorted(valid_periods)}",
                    }
                )
                continue

            try:
                raw = await provider.query_kline(
                    code_list=request.code_list,
                    begin_date=request.begin_date,
                    end_date=request.end_date,
                    period=request.period,
                )
                filtered = _filter_history_mapping(raw, request.begin_date, request.end_date)
                results.append(
                    {
                        "index": idx,
                        "codes": request.code_list,
                        "data": dataframe_to_dict(filtered),
                        "period": request.period,
                    }
                )
            except Exception as exc:  # pragma: no cover
                errors.append({"index": idx, "codes": request.code_list, "error": str(exc)})

        return format_response(
            success=len(errors) == 0,
            data={
                "results": results,
                "errors": errors,
                "total": len(requests),
                "success_count": len(results),
                "error_count": len(errors),
            },
        )
    except Exception as exc:  # pragma: no cover
        return format_response(success=False, error=str(exc))
