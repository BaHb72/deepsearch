"""
AmazingData ETF数据API模块
提供ETF申赎数据等接口

接口列表:
- 4.11.1 ETF每日最新申赎数据 (get_etf_pcf)
- 4.11.2 ETF基金份额 (get_fund_share)
- 4.11.3 ETF每日收盘IOPV (get_fund_iopv)
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .base import (
    DEFAULT_LOCAL_PATH,
    JSONDict,
    dataframe_to_dict,
    format_response,
    get_amazingdata_provider,
)

router = APIRouter(tags=["AmazingData-ETF数据"])


# ================== 请求模型 ==================


class EtfPcfRequest(BaseModel):
    """ETF申赎数据请求"""

    code_list: List[str] = Field(
        ...,
        description="ETF代码列表，如 510300.SH, 159919.SZ 等",
        examples=[["510300.SH", "159919.SZ"]],
    )


# ================== API接口 ==================


@router.post("/pcf", summary="获取ETF每日申赎数据")
async def get_etf_pcf(request: EtfPcfRequest) -> JSONDict:
    """
    3.5.11.1 ETF每日最新申赎数据
    获取指定ETF的申赎和成分股数据（沪深交易所的ETF）

    返回数据结构：
    - etf_pcf_info: ETF申赎基本信息（DataFrame格式）
      - index为ETF代码
    - etf_pcf_constituent: ETF成分股数据（字典格式）
      - key: ETF代码
      - value: 成分股DataFrame
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_etf_pcf(code_list=request.code_list)

        # 处理返回结果
        if result is None:
            return format_response(
                success=True,
                data={"etf_pcf_info": None, "etf_pcf_constituent": {}},
                code_count=len(request.code_list),
            )

        # 如果返回的是元组 (etf_pcf_info, etf_pcf_constituent)
        if isinstance(result, tuple) and len(result) == 2:
            etf_pcf_info, etf_pcf_constituent = result

            # 转换成分股字典
            constituent_data: Dict[str, Any] = {}
            if isinstance(etf_pcf_constituent, dict):
                for etf_code, df in etf_pcf_constituent.items():
                    constituent_data[etf_code] = dataframe_to_dict(df)

            return format_response(
                success=True,
                data={
                    "etf_pcf_info": dataframe_to_dict(etf_pcf_info),
                    "etf_pcf_constituent": constituent_data,
                },
                code_count=len(request.code_list),
            )

        # 其他情况，直接返回转换后的数据
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ================== 新增请求模型 ==================


class FundShareRequest(BaseModel):
    """ETF基金份额请求"""

    code_list: List[str] = Field(
        ...,
        description="ETF代码列表",
        examples=[["510300.SH", "159919.SZ"]],
    )
    local_path: str = Field(
        default=DEFAULT_LOCAL_PATH,
        description="本地存储路径",
    )
    is_local: bool = Field(
        default=True,
        description="是否使用本地缓存，True优先读本地，False强制从服务端获取",
    )
    begin_date: Optional[int] = Field(
        default=None,
        description="开始日期，格式YYYYMMDD",
        examples=[20240101],
    )
    end_date: Optional[int] = Field(
        default=None,
        description="结束日期，格式YYYYMMDD",
        examples=[20241231],
    )


class FundIopvRequest(BaseModel):
    """ETF收盘IOPV请求"""

    code_list: List[str] = Field(
        ...,
        description="ETF代码列表",
        examples=[["510300.SH", "159919.SZ"]],
    )
    local_path: str = Field(
        default=DEFAULT_LOCAL_PATH,
        description="本地存储路径",
    )
    is_local: bool = Field(
        default=True,
        description="是否使用本地缓存",
    )
    begin_date: Optional[int] = Field(
        default=None,
        description="开始日期，格式YYYYMMDD",
        examples=[20240101],
    )
    end_date: Optional[int] = Field(
        default=None,
        description="结束日期，格式YYYYMMDD",
        examples=[20241231],
    )


# ================== 新增API接口 ==================


@router.post("/fund-share", summary="获取ETF基金份额")
async def get_fund_share(request: FundShareRequest) -> JSONDict:
    """
    4.11.2 ETF基金份额

    获取指定ETF列表的基金份额数据

    返回字段:
    - FUND_SHARE: 基金份额(万份)
    - TOTAL_SHARE: 基金总份额(万份)
    - FLOAT_SHARE: 流通份额(万份)
    - CHANGE_DATE: 变动日期
    - CHANGE_REASON: 份额变动原因
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_fund_share(
            code_list=request.code_list,
            local_path=request.local_path,
            is_local=request.is_local,
            begin_date=request.begin_date,
            end_date=request.end_date,
        )

        return format_response(
            success=True,
            data=result,
            code_count=len(request.code_list),
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/fund-iopv", summary="获取ETF每日收盘IOPV")
async def get_fund_iopv(request: FundIopvRequest) -> JSONDict:
    """
    4.11.3 ETF每日收盘IOPV

    获取指定ETF列表的每日收盘IOPV数据

    返回字段:
    - MARKET_CODE: 市场代码
    - PRICE_DATE: 日期
    - IOPV_NAV: IOPV收盘净值
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_fund_iopv(
            code_list=request.code_list,
            local_path=request.local_path,
            is_local=request.is_local,
            begin_date=request.begin_date,
            end_date=request.end_date,
        )

        return format_response(
            success=True,
            data=result,
            code_count=len(request.code_list),
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
