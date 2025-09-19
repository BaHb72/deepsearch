"""
AmazingData 财务数据API模块
包含财务报表、业绩预告等财务数据接口
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from loguru import logger

from .base import (
    get_amazingdata_provider,
    dataframe_to_dict,
    handle_api_error,
    format_response
)

# 创建路由器
router = APIRouter(tags=["AmazingData-财务数据"])


# ================== 请求模型 ==================

class FinancialReportRequest(BaseModel):
    """财务报表请求基类"""
    code_list: List[str] = Field(..., description="股票代码列表")
    report_date: Optional[int] = Field(None, description="报告期，如20230331")
    report_type: str = Field("quarter", description="报表类型：quarter(季报)/year(年报)")
    is_local: bool = Field(False, description="是否使用本地存储")
    local_path: Optional[str] = Field(None, description="本地存储路径")


class ProfitNoticeRequest(BaseModel):
    """业绩预告请求"""
    code_list: List[str] = Field(..., description="股票代码列表")
    start_date: Optional[int] = Field(None, description="开始日期")
    end_date: Optional[int] = Field(None, description="结束日期")
    is_local: bool = Field(False, description="是否使用本地存储")
    local_path: Optional[str] = Field(None, description="本地存储路径")


# ================== API接口 ==================

@router.post("/balance-sheet", summary="获取资产负债表")
async def get_balance_sheet(request: FinancialReportRequest):
    """
    获取资产负债表数据

    Args:
        request: 财务报表请求

    Returns:
        资产负债表数据
    """
    try:
        provider = await get_amazingdata_provider()

        # 调用SDK获取资产负债表
        result = await provider.get_balance_sheet(
            code_list=request.code_list,
            report_date=request.report_date,
            report_type=request.report_type,
            is_local=request.is_local,
            local_path=request.local_path
        )

        # 格式化响应
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
            report_date=request.report_date,
            report_type=request.report_type,
            statement_type="balance_sheet"
        )
    except Exception as e:
        return handle_api_error("get_balance_sheet", e)


@router.post("/cash-flow", summary="获取现金流量表")
async def get_cash_flow(request: FinancialReportRequest):
    """
    获取现金流量表数据

    Args:
        request: 财务报表请求

    Returns:
        现金流量表数据
    """
    try:
        provider = await get_amazingdata_provider()

        # 调用SDK获取现金流量表
        result = await provider.get_cash_flow(
            code_list=request.code_list,
            report_date=request.report_date,
            report_type=request.report_type,
            is_local=request.is_local,
            local_path=request.local_path
        )

        # 格式化响应
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
            report_date=request.report_date,
            report_type=request.report_type,
            statement_type="cash_flow"
        )
    except Exception as e:
        return handle_api_error("get_cash_flow", e)


@router.post("/income", summary="获取利润表")
async def get_income(request: FinancialReportRequest):
    """
    获取利润表数据

    Args:
        request: 财务报表请求

    Returns:
        利润表数据
    """
    try:
        provider = await get_amazingdata_provider()

        # 调用SDK获取利润表
        result = await provider.get_income(
            code_list=request.code_list,
            report_date=request.report_date,
            report_type=request.report_type,
            is_local=request.is_local,
            local_path=request.local_path
        )

        # 格式化响应
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
            report_date=request.report_date,
            report_type=request.report_type,
            statement_type="income"
        )
    except Exception as e:
        return handle_api_error("get_income", e)


@router.post("/profit-express", summary="获取业绩快报")
async def get_profit_express(request: ProfitNoticeRequest):
    """
    获取业绩快报数据

    Args:
        request: 业绩预告请求

    Returns:
        业绩快报数据
    """
    try:
        provider = await get_amazingdata_provider()

        # 调用SDK获取业绩快报
        result = await provider.get_profit_express(
            code_list=request.code_list,
            start_date=request.start_date,
            end_date=request.end_date,
            is_local=request.is_local,
            local_path=request.local_path
        )

        # 格式化响应
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
            date_range=f"{request.start_date}-{request.end_date}" if request.start_date else None,
            report_type="profit_express"
        )
    except Exception as e:
        return handle_api_error("get_profit_express", e)


@router.post("/profit-notice", summary="获取业绩预告")
async def get_profit_notice(request: ProfitNoticeRequest):
    """
    获取业绩预告数据

    Args:
        request: 业绩预告请求

    Returns:
        业绩预告数据
    """
    try:
        provider = await get_amazingdata_provider()

        # 调用SDK获取业绩预告
        result = await provider.get_profit_notice(
            code_list=request.code_list,
            start_date=request.start_date,
            end_date=request.end_date,
            is_local=request.is_local,
            local_path=request.local_path
        )

        # 格式化响应
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
            date_range=f"{request.start_date}-{request.end_date}" if request.start_date else None,
            report_type="profit_notice"
        )
    except Exception as e:
        return handle_api_error("get_profit_notice", e)


@router.post("/financial-summary", summary="获取财务摘要")
async def get_financial_summary(code: str):
    """
    获取单个股票的财务摘要信息

    Args:
        code: 股票代码

    Returns:
        财务摘要数据
    """
    try:
        provider = await get_amazingdata_provider()
        summary = {}

        # 获取最新的财务报表
        try:
            balance = await provider.get_balance_sheet(
                code_list=[code],
                report_type="quarter"
            )
            if balance is not None and not balance.empty:
                summary["balance_sheet"] = {
                    "total_assets": float(balance.iloc[0].get("total_assets", 0)),
                    "total_liabilities": float(balance.iloc[0].get("total_liab", 0)),
                    "total_equity": float(balance.iloc[0].get("total_hldr_eqy", 0)),
                    "report_date": str(balance.iloc[0].get("report_date", ""))
                }
        except:
            summary["balance_sheet"] = None

        try:
            income = await provider.get_income(
                code_list=[code],
                report_type="quarter"
            )
            if income is not None and not income.empty:
                summary["income"] = {
                    "revenue": float(income.iloc[0].get("revenue", 0)),
                    "net_profit": float(income.iloc[0].get("net_profit", 0)),
                    "operating_profit": float(income.iloc[0].get("operate_profit", 0)),
                    "report_date": str(income.iloc[0].get("report_date", ""))
                }
        except:
            summary["income"] = None

        try:
            cash_flow = await provider.get_cash_flow(
                code_list=[code],
                report_type="quarter"
            )
            if cash_flow is not None and not cash_flow.empty:
                summary["cash_flow"] = {
                    "operating_cash_flow": float(cash_flow.iloc[0].get("n_cashflow_act", 0)),
                    "investing_cash_flow": float(cash_flow.iloc[0].get("n_cashflow_inv", 0)),
                    "financing_cash_flow": float(cash_flow.iloc[0].get("n_cashflow_fnc", 0)),
                    "report_date": str(cash_flow.iloc[0].get("report_date", ""))
                }
        except:
            summary["cash_flow"] = None

        # 计算财务指标
        if summary.get("balance_sheet") and summary.get("income"):
            bs = summary["balance_sheet"]
            inc = summary["income"]

            # ROE = 净利润 / 净资产
            if bs["total_equity"] > 0:
                summary["indicators"] = {
                    "roe": inc["net_profit"] / bs["total_equity"] * 100,
                    "asset_liability_ratio": bs["total_liabilities"] / bs["total_assets"] * 100,
                    "net_profit_margin": inc["net_profit"] / inc["revenue"] * 100 if inc["revenue"] > 0 else 0
                }

        return format_response(
            success=True,
            data=summary,
            code=code
        )

    except Exception as e:
        return handle_api_error("get_financial_summary", e)