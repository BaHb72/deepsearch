"""
AmazingData 财务数据API模块
包含财务报表、业绩预告等财务数据接口
"""

from typing import Optional

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel, Field

from .base import (
    DEFAULT_LOCAL_PATH,
    JSONDict,
    dataframe_to_dict,
    ensure_dataframe,
    filter_dataframe_by_dates,
    filter_dataframe_by_value,
    format_response,
    get_amazingdata_provider,
    handle_api_error,
)

# 创建路由器
router = APIRouter(tags=["AmazingData-财务数据"])


# ================== 请求模型 ==================


class FinancialReportRequest(BaseModel):
    """财务报表请求基类"""

    code_list: list[str] = Field(..., description="股票代码列表")
    report_date: Optional[int] = Field(None, description="报告期，如20230331")
    report_type: str = Field("quarter", description="报表类型：quarter(季报)/year(年报)")
    is_local: bool = Field(True, description="是否使用本地存储")
    local_path: Optional[str] = Field(DEFAULT_LOCAL_PATH, description="本地存储路径")


class ProfitNoticeRequest(BaseModel):
    """业绩预告请求"""

    code_list: list[str] = Field(..., description="股票代码列表")
    start_date: Optional[int] = Field(None, description="开始日期")
    end_date: Optional[int] = Field(None, description="结束日期")
    is_local: bool = Field(True, description="是否使用本地存储")
    local_path: Optional[str] = Field(DEFAULT_LOCAL_PATH, description="本地存储路径")


# ================== API接口 ==================


@router.post("/balance-sheet", summary="获取资产负债表")
async def get_balance_sheet(request: FinancialReportRequest) -> JSONDict:
    """
    获取资产负债表数据

    Args:
        request: 财务报表请求

    Returns:
        资产负债表数据
    """
    import asyncio

    try:
        provider = await get_amazingdata_provider()
        local_path = request.local_path or DEFAULT_LOCAL_PATH

        # 添加 30s 超时保护
        try:
            raw_result = await asyncio.wait_for(
                provider.get_balance_sheet(
                    code_list=request.code_list,
                    local_path=local_path,
                    is_local=request.is_local,
                ),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            return format_response(
                success=False,
                data=None,
                error="获取资产负债表超时 (30s)",
                code_count=len(request.code_list),
            )

        filtered_df = ensure_dataframe(raw_result)
        if filtered_df is not None and request.report_date is not None:
            filtered_df = filter_dataframe_by_dates(
                filtered_df,
                request.report_date,
                request.report_date,
                columns=("report_date", "REPORT_DATE", "ann_date", "ANN_DATE"),
            )
        if filtered_df is not None:
            filtered_df = filter_dataframe_by_value(
                filtered_df,
                request.report_type,
                columns=("report_type", "REPORT_TYPE", "type", "TYPE"),
            )

        payload_source: object = filtered_df if filtered_df is not None else raw_result
        payload = dataframe_to_dict(payload_source)

        return format_response(
            success=True,
            data=payload,
            code_count=len(request.code_list),
            report_date=request.report_date,
            report_type=request.report_type,
            statement_type="balance_sheet",
        )
    except Exception as e:

        return handle_api_error("get_balance_sheet", e)


@router.post("/cash-flow", summary="获取现金流量表")
async def get_cash_flow(request: FinancialReportRequest) -> JSONDict:
    """
    获取现金流量表数据

    Args:
        request: 财务报表请求

    Returns:
        现金流量表数据
    """
    try:
        provider = await get_amazingdata_provider()
        local_path = request.local_path or DEFAULT_LOCAL_PATH

        raw_result = await provider.get_cash_flow(
            code_list=request.code_list,
            local_path=local_path,
            is_local=request.is_local,
        )
        filtered_df = ensure_dataframe(raw_result)
        if filtered_df is not None and request.report_date is not None:
            filtered_df = filter_dataframe_by_dates(
                filtered_df,
                request.report_date,
                request.report_date,
                columns=("report_date", "REPORT_DATE", "ann_date", "ANN_DATE"),
            )
        if filtered_df is not None:
            filtered_df = filter_dataframe_by_value(
                filtered_df,
                request.report_type,
                columns=("report_type", "REPORT_TYPE", "type", "TYPE"),
            )

        payload_source: object = filtered_df if filtered_df is not None else raw_result
        payload = dataframe_to_dict(payload_source)

        return format_response(
            success=True,
            data=payload,
            code_count=len(request.code_list),
            report_date=request.report_date,
            report_type=request.report_type,
            statement_type="cash_flow",
        )
    except Exception as e:
        return handle_api_error("get_cash_flow", e)


@router.post("/income", summary="获取利润表")
async def get_income(request: FinancialReportRequest) -> JSONDict:
    """
    获取利润表数据

    Args:
        request: 财务报表请求

    Returns:
        利润表数据
    """
    try:
        provider = await get_amazingdata_provider()
        local_path = request.local_path or DEFAULT_LOCAL_PATH

        raw_result = await provider.get_income(
            code_list=request.code_list,
            local_path=local_path,
            is_local=request.is_local,
        )
        # DEBUG: 记录raw_result类型用于排查序列化问题
        import logging

        logging.getLogger(__name__).info(
            f"[DEBUG] get_income raw_result type: {type(raw_result).__name__}"
        )
        filtered_df = ensure_dataframe(raw_result)
        if filtered_df is not None and request.report_date is not None:
            filtered_df = filter_dataframe_by_dates(
                filtered_df,
                request.report_date,
                request.report_date,
                columns=("report_date", "REPORT_DATE", "ann_date", "ANN_DATE"),
            )
        if filtered_df is not None:
            filtered_df = filter_dataframe_by_value(
                filtered_df,
                request.report_type,
                columns=("report_type", "REPORT_TYPE", "type", "TYPE"),
            )

        # 确保payload_source是已处理的数据，如果filtered_df为None则使用raw_result
        payload_source: object = filtered_df if filtered_df is not None else raw_result
        # 强制确保所有DataFrame都被转换为可序列化格式
        if isinstance(payload_source, pd.DataFrame):
            payload = dataframe_to_dict(payload_source)
        else:
            payload = dataframe_to_dict(payload_source)

        # DEBUG: 记录payload类型和内容结构
        import logging as _log

        _log.getLogger(__name__).info(f"[DEBUG] payload type: {type(payload).__name__}")
        if isinstance(payload, dict):
            for k, v in payload.items():
                _log.getLogger(__name__).info(f"[DEBUG] payload[{k}] type: {type(v).__name__}")

        return format_response(
            success=True,
            data=payload,
            code_count=len(request.code_list),
            report_date=request.report_date,
            report_type=request.report_type,
            statement_type="income",
        )
    except Exception as e:
        return handle_api_error("get_income", e)


@router.post("/profit-express", summary="获取业绩快报")
async def get_profit_express(request: ProfitNoticeRequest) -> JSONDict:
    """
    获取业绩快报数据

    Args:
        request: 业绩预告请求

    Returns:
        业绩快报数据
    """
    try:
        provider = await get_amazingdata_provider()
        local_path = request.local_path or DEFAULT_LOCAL_PATH

        raw_result = await provider.get_profit_express(
            code_list=request.code_list,
            local_path=local_path,
            is_local=request.is_local,
        )
        filtered_df = ensure_dataframe(raw_result)
        if filtered_df is not None:
            if request.start_date and request.end_date:
                filtered_df = filter_dataframe_by_dates(
                    filtered_df,
                    request.start_date,
                    request.end_date,
                    columns=(
                        "notice_date",
                        "NOTICE_DATE",
                        "report_date",
                        "REPORT_DATE",
                        "ann_date",
                        "ANN_DATE",
                    ),
                )
            elif request.start_date:
                filtered_df = filter_dataframe_by_dates(
                    filtered_df,
                    request.start_date,
                    request.start_date,
                    columns=(
                        "notice_date",
                        "NOTICE_DATE",
                        "report_date",
                        "REPORT_DATE",
                        "ann_date",
                        "ANN_DATE",
                    ),
                )
            elif request.end_date:
                filtered_df = filter_dataframe_by_dates(
                    filtered_df,
                    request.end_date,
                    request.end_date,
                    columns=(
                        "notice_date",
                        "NOTICE_DATE",
                        "report_date",
                        "REPORT_DATE",
                        "ann_date",
                        "ANN_DATE",
                    ),
                )

        payload_source = filtered_df if filtered_df is not None else raw_result
        return format_response(
            success=True,
            data=dataframe_to_dict(payload_source),
            code_count=len(request.code_list),
            date_range=f"{request.start_date}-{request.end_date}" if request.start_date else None,
            report_type="profit_express",
        )
    except Exception as e:
        return handle_api_error("get_profit_express", e)


@router.post("/profit-notice", summary="获取业绩预告")
async def get_profit_notice(request: ProfitNoticeRequest) -> JSONDict:
    """
    获取业绩预告数据

    Args:
        request: 业绩预告请求

    Returns:
        业绩预告数据
    """
    try:
        provider = await get_amazingdata_provider()
        local_path = request.local_path or DEFAULT_LOCAL_PATH

        raw_result = await provider.get_profit_notice(
            code_list=request.code_list,
            local_path=local_path,
            is_local=request.is_local,
        )
        filtered_df = ensure_dataframe(raw_result)
        if filtered_df is not None:
            if request.start_date and request.end_date:
                filtered_df = filter_dataframe_by_dates(
                    filtered_df,
                    request.start_date,
                    request.end_date,
                    columns=(
                        "notice_date",
                        "NOTICE_DATE",
                        "report_date",
                        "REPORT_DATE",
                        "ann_date",
                        "ANN_DATE",
                    ),
                )
            elif request.start_date:
                filtered_df = filter_dataframe_by_dates(
                    filtered_df,
                    request.start_date,
                    request.start_date,
                    columns=(
                        "notice_date",
                        "NOTICE_DATE",
                        "report_date",
                        "REPORT_DATE",
                        "ann_date",
                        "ANN_DATE",
                    ),
                )
            elif request.end_date:
                filtered_df = filter_dataframe_by_dates(
                    filtered_df,
                    request.end_date,
                    request.end_date,
                    columns=(
                        "notice_date",
                        "NOTICE_DATE",
                        "report_date",
                        "REPORT_DATE",
                        "ann_date",
                        "ANN_DATE",
                    ),
                )

        payload_source = filtered_df if filtered_df is not None else raw_result

        return format_response(
            success=True,
            data=dataframe_to_dict(payload_source),
            code_count=len(request.code_list),
            date_range=f"{request.start_date}-{request.end_date}" if request.start_date else None,
            report_type="profit_notice",
        )
    except Exception as e:
        return handle_api_error("get_profit_notice", e)


@router.post("/financial-summary", summary="获取财务摘要")
async def get_financial_summary(code: str) -> JSONDict:
    """
    获取单只股票的财务摘要信息

    Args:
        code: 股票代码

    Returns:
        财务摘要数据
    """
    try:
        provider = await get_amazingdata_provider()
        summary: dict[str, object | None] = {}
        local_path = DEFAULT_LOCAL_PATH

        try:
            balance_raw = await provider.get_balance_sheet(
                code_list=[code],
                local_path=local_path,
                is_local=True,
            )
            balance = ensure_dataframe(balance_raw)
            if balance is not None:
                balance = filter_dataframe_by_value(
                    balance,
                    "quarter",
                    columns=("report_type", "REPORT_TYPE", "type", "TYPE"),
                )
            if isinstance(balance, pd.DataFrame) and not balance.empty:
                balance_row = balance.iloc[0]
                summary["balance_sheet"] = {
                    "total_assets": float(balance_row.get("total_assets", 0)),
                    "total_liabilities": float(balance_row.get("total_liab", 0)),
                    "total_equity": float(balance_row.get("total_hldr_eqy", 0)),
                    "report_date": str(balance_row.get("report_date", "")),
                }
            else:
                summary["balance_sheet"] = None
        except Exception:
            summary["balance_sheet"] = None

        try:
            income_raw = await provider.get_income(
                code_list=[code],
                local_path=local_path,
                is_local=True,
            )
            income = ensure_dataframe(income_raw)
            if income is not None:
                income = filter_dataframe_by_value(
                    income,
                    "quarter",
                    columns=("report_type", "REPORT_TYPE", "type", "TYPE"),
                )
            if isinstance(income, pd.DataFrame) and not income.empty:
                income_row = income.iloc[0]
                summary["income"] = {
                    "revenue": float(income_row.get("revenue", 0)),
                    "net_profit": float(income_row.get("net_profit", 0)),
                    "operating_profit": float(income_row.get("operate_profit", 0)),
                    "report_date": str(income_row.get("report_date", "")),
                }
            else:
                summary["income"] = None
        except Exception:
            summary["income"] = None

        try:
            cash_flow_raw = await provider.get_cash_flow(
                code_list=[code],
                local_path=local_path,
                is_local=True,
            )
            cash_flow = ensure_dataframe(cash_flow_raw)
            if cash_flow is not None:
                cash_flow = filter_dataframe_by_value(
                    cash_flow,
                    "quarter",
                    columns=("report_type", "REPORT_TYPE", "type", "TYPE"),
                )
            if isinstance(cash_flow, pd.DataFrame) and not cash_flow.empty:
                cash_row = cash_flow.iloc[0]
                summary["cash_flow"] = {
                    "operating_cash_flow": float(cash_row.get("n_cashflow_act", 0)),
                    "investing_cash_flow": float(cash_row.get("n_cashflow_inv", 0)),
                    "financing_cash_flow": float(cash_row.get("n_cashflow_fnc", 0)),
                    "report_date": str(cash_row.get("report_date", "")),
                }
            else:
                summary["cash_flow"] = None
        except Exception:
            summary["cash_flow"] = None

        balance_data = summary.get("balance_sheet")
        income_data = summary.get("income")

        if isinstance(balance_data, dict) and isinstance(income_data, dict):
            total_equity = float(balance_data.get("total_equity", 0))
            total_assets = float(balance_data.get("total_assets", 0))
            total_liabilities = float(balance_data.get("total_liabilities", 0))
            net_profit = float(income_data.get("net_profit", 0))
            revenue = float(income_data.get("revenue", 0))

            if total_equity > 0:
                summary["indicators"] = {
                    "roe": net_profit / total_equity * 100,
                    "asset_liability_ratio": (
                        total_liabilities / total_assets * 100 if total_assets else 0
                    ),
                    "net_profit_margin": (net_profit / revenue * 100 if revenue else 0),
                }

        return format_response(success=True, data=summary, code=code)

    except Exception as e:
        return handle_api_error("get_financial_summary", e)
