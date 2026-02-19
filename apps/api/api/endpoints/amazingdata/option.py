"""
AmazingData 期权数据API模块
提供期权基本资料、标准合约属性、月合约变动等接口

接口列表:
- 3.5.10.1 期权基本资料 (get_option_basic_info)
- 3.5.10.2 期权标准合约属性 (get_option_std_ctr_specs)
- 3.5.10.3 期权月合约属性变动 (get_option_mon_ctr_specs)
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .base import (
    DEFAULT_LOCAL_PATH,
    JSONDict,
    dataframe_to_dict,
    format_response,
    get_amazingdata_provider,
)

router = APIRouter(tags=["AmazingData-期权数据"])


# ================== 请求模型 ==================


class OptionBasicRequest(BaseModel):
    """期权基本资料请求"""

    code_list: List[str] = Field(..., description="ETF期权代码列表")
    local_path: Optional[str] = Field(DEFAULT_LOCAL_PATH, description="本地存储路径")
    is_local: bool = Field(True, description="是否使用本地缓存")


class OptionStdCtrRequest(BaseModel):
    """期权标准合约属性请求"""

    code_list: List[str] = Field(
        ...,
        description="ETF代码列表，如 159919.SZ, 510300.SH 等",
        examples=[["159919.SZ", "510300.SH", "510050.SH"]],
    )
    local_path: Optional[str] = Field(DEFAULT_LOCAL_PATH, description="本地存储路径")
    is_local: bool = Field(True, description="是否使用本地缓存")


class OptionMonCtrRequest(BaseModel):
    """期权月合约属性变动请求"""

    code_list: List[str] = Field(..., description="ETF期权代码列表")
    local_path: Optional[str] = Field(DEFAULT_LOCAL_PATH, description="本地存储路径")
    is_local: bool = Field(True, description="是否使用本地缓存")


# ================== API接口 ==================


@router.post("/basic-info", summary="获取期权基本资料")
async def get_option_basic_info(request: OptionBasicRequest) -> JSONDict:
    """
    3.5.10.1 期权基本资料
    获取指定期权的基本资料（沪深交易所的ETF期权）

    返回字段：
    - CONTRACT_FULL_NAME: 合约全称
    - CONTRACT_TYPE: 合约类别 (C=认购, P=认沽)
    - DELIVERY_MONTH: 交割月份
    - EXPIRY_DATE: 到期日
    - EXERCISE_PRICE: 行权价格
    - EXERCISE_END_DATE: 最后行权日
    - START_TRADE_DATE: 开始交易日
    - LISTING_REF_PRICE: 挂牌基准价
    - LAST_TRADE_DATE: 最后交易日
    - EXCHANGE_CODE: 合约交易所代码
    - DELIVERY_DATE: 最后交割日
    - CONTRACT_UNIT: 合约单位
    - IS_TRADE: 是否交易
    - EXCHANGE_SHORT_NAME: 合约交易所简称
    - CONTRACT_ADJUST_FLAG: 合约调整标志
    - MARKET_CODE: 合约代码
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_option_basic_info(
            code_list=request.code_list,
            local_path=request.local_path or DEFAULT_LOCAL_PATH,
            is_local=request.is_local,
        )
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/std-ctr-specs", summary="获取期权标准合约属性")
async def get_option_std_ctr_specs(request: OptionStdCtrRequest) -> JSONDict:
    """
    3.5.10.2 期权标准合约属性
    获取指定期权标准合约属性（沪深交易所的ETF期权）

    支持的ETF代码：
    - 深交所: 159919.SZ, 159915.SZ, 159922.SZ, 159901.SZ
    - 上交所: 510300.SH, 588000.SH, 588080.SH, 510050.SH, 510500.SH

    返回字段：
    - EXERCISE_DATE: 期权行权日
    - CONTRACT_UNIT: 合约单位
    - LAST_TRADING_DATE: 最后交易日
    - POSITION_LIMIT: 头寸限制
    - DELIST_DATE: 退市日期
    - EXERCISE_METHOD: 行权方式
    - DELIVERY_METHOD: 交割方式
    - EXCHANGE_NAME: 交易所名称
    - CONTRACT_VALUE: 合约价值
    - IS_SIMULATION: 是否仿真合约
    - OPTION_STRIKE_PRICE: 期权行权价
    - LISTED_DATE: 上市日期
    - OPTION_NAME: 期权名称
    - OPTION_TYPE: 期权类型
    - CONTRACT_MULTIPLIER: 合约乘数
    ... 等更多字段
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_option_std_ctr_specs(
            code_list=request.code_list,
            local_path=request.local_path or DEFAULT_LOCAL_PATH,
            is_local=request.is_local,
        )
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/mon-ctr-specs", summary="获取期权月合约属性变动")
async def get_option_mon_ctr_specs(request: OptionMonCtrRequest) -> JSONDict:
    """
    3.5.10.3 期权月合约属性变动
    获取指定期权月合约属性变动（沪深交易所的ETF期权）

    返回字段：
    - CODE_OLD: 原交易代码
    - CHANGE_DATE: 调整日期
    - MARKET_CODE: 市场代码
    - NAME_NEW: 新合约简称
    - EXERCISE_PRICE_NEW: 新行权价(元)
    - NAME_OLD: 原合约简称
    - CODE_NEW: 新交易代码
    - EXERCISE_PRICE_OLD: 原行权价(元)
    - UNIT_OLD: 原合约单位(股)
    - UNIT_NEW: 新合约单位(股)
    - CHANGE_REASON: 调整原因
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_option_mon_ctr_specs(
            code_list=request.code_list,
            local_path=request.local_path or DEFAULT_LOCAL_PATH,
            is_local=request.is_local,
        )
        return format_response(
            success=True,
            data=dataframe_to_dict(result),
            code_count=len(request.code_list),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
