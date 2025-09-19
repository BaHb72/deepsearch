# encoding:utf-8
"""
AmazingData Web API 封装
将35个AmazingData SDK接口封装为RESTful API

Author: DeepSearch Team
Version: 1.0.0
Date: 2025-09-18
"""

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, date
from pydantic import BaseModel, Field
from loguru import logger
import pandas as pd
import json

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_extended import AmazingDataExtended
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_realtime import AmazingDataRealtime
from deepsearch.webui.api.providers import DataProviderFactory, DataSourceType


# 创建路由器
router = APIRouter(prefix="/api/amazingdata", tags=["AmazingData"])


# ================== 请求模型定义 ==================

class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    host: str = Field(..., description="服务器地址")
    port: int = Field(..., description="服务器端口")


class UpdatePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., description="新密码")


class CodeListRequest(BaseModel):
    """代码列表请求"""
    security_type: str = Field("EXTRA_STOCK_A", description="证券类型")


class StockListRequest(BaseModel):
    """股票列表请求"""
    code_list: List[str] = Field(..., description="股票代码列表")
    local_path: Optional[str] = Field("D://AmazingData_local_data//", description="本地存储路径")
    is_local: bool = Field(True, description="是否使用本地存储")


class HistCodeListRequest(BaseModel):
    """历史代码列表请求"""
    security_type: str = Field("EXTRA_STOCK_A_SH_SZ", description="证券类型")
    start_date: int = Field(..., description="开始日期，如20130101")
    end_date: int = Field(..., description="结束日期，如20250101")
    local_path: str = Field("D://AmazingData_local_data//", description="本地存储路径")


class KlineRequest(BaseModel):
    """K线查询请求"""
    code_list: List[str] = Field(..., description="代码列表")
    begin_date: int = Field(..., description="开始日期")
    end_date: int = Field(..., description="结束日期")
    period: Optional[str] = Field(None, description="K线周期")


class SubscriptionRequest(BaseModel):
    """订阅请求"""
    code_list: List[str] = Field(..., description="代码列表")
    period: Optional[str] = Field(None, description="订阅周期")


# ================== 辅助函数 ==================

async def get_amazingdata_provider() -> AmazingDataExtended:
    """获取AmazingData提供者实例"""
    try:
        provider = await DataProviderFactory.get_provider(DataSourceType.AMAZINGDATA)
        if not isinstance(provider, AmazingDataExtended):
            # 如果不是扩展版本，尝试创建扩展版本
            from deepsearch.config import get_config
            config = get_config()
            amazingdata_config = config.data_sources.amazingdata.model_dump()
            provider = AmazingDataExtended(amazingdata_config)
            await provider.initialize()
        return provider
    except Exception as e:
        logger.error(f"获取AmazingData提供者失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get AmazingData provider: {e}")


def dataframe_to_dict(df: Optional[pd.DataFrame]) -> Optional[Dict]:
    """将DataFrame转换为字典"""
    if df is None:
        return None
    try:
        # 转换为JSON可序列化的格式
        return json.loads(df.to_json(orient='records', date_format='iso'))
    except Exception as e:
        logger.error(f"DataFrame转换失败: {e}")
        return None


# ================== 1. 账户管理接口 ==================

@router.post("/login", summary="登录接口")
async def login(request: LoginRequest):
    """
    3.5.1.1 登录
    登录到AmazingData系统
    """
    try:
        # 创建配置
        config = {
            'username': request.username,
            'password': request.password,
            'host': request.host,
            'port': request.port
        }

        # 创建提供者并登录
        provider = AmazingDataExtended(config)
        success = await provider.initialize()

        if success:
            # 保存到Factory
            DataProviderFactory._instances[DataSourceType.AMAZINGDATA] = provider
            return {"status": "success", "message": "登录成功"}
        else:
            raise HTTPException(status_code=401, detail="登录失败")

    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout", summary="登出接口")
async def logout():
    """
    3.5.1.2 登出
    登出AmazingData系统
    """
    try:
        provider = await get_amazingdata_provider()
        await provider.stop()
        return {"status": "success", "message": "登出成功"}
    except Exception as e:
        logger.error(f"登出失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-password", summary="修改密码")
async def update_password(request: UpdatePasswordRequest):
    """
    3.5.1.3 修改密码
    修改账户密码
    """
    try:
        provider = await get_amazingdata_provider()
        success = await provider.update_password(request.old_password, request.new_password)

        if success:
            return {"status": "success", "message": "密码修改成功"}
        else:
            raise HTTPException(status_code=400, detail="密码修改失败")

    except Exception as e:
        logger.error(f"修改密码失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 2. 基础数据接口 ==================

@router.get("/code-info", summary="获取每日最新证券信息")
async def get_code_info(
    security_type: str = Query("EXTRA_STOCK_A", description="证券类型")
):
    """
    3.5.2.1 每日最新证券信息
    获取每日最新证券信息，包括证券简称、昨收价、涨跌停价等
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_code_info(security_type)
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "count": len(result) if result is not None else 0
        }
    except Exception as e:
        logger.error(f"获取证券信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calendar", summary="获取交易日历")
async def get_calendar(
    data_type: str = Query("str", description="返回类型"),
    market: str = Query("SH", description="市场")
):
    """
    3.5.2.7 交易日历
    获取交易所的交易日历
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_calendar(data_type, market)
        return {
            "status": "success",
            "data": result,
            "count": len(result) if result else 0
        }
    except Exception as e:
        logger.error(f"获取交易日历失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stock-basic", summary="获取股票基础信息")
async def get_stock_basic(request: List[str] = Body(..., description="股票代码列表")):
    """
    3.5.2.8 证券基础信息
    获取指定股票的基础信息
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_stock_basic(request)
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "count": len(result) if result is not None else 0
        }
    except Exception as e:
        logger.error(f"获取股票基础信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backward-factor", summary="获取后复权因子")
async def get_backward_factor(request: StockListRequest):
    """
    3.5.2.4 复权因子（后复权因子）
    获取复权因子数据并本地存储
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_backward_factor(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "后复权因子获取成功"
        }
    except Exception as e:
        logger.error(f"获取后复权因子失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/adj-factor", summary="获取单次复权因子")
async def get_adj_factor(request: StockListRequest):
    """
    3.5.2.5 复权因子（单次复权因子）
    获取复权因子数据并本地存储
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_adj_factor(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "单次复权因子获取成功"
        }
    except Exception as e:
        logger.error(f"获取单次复权因子失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history-stock-status", summary="获取历史证券状态")
async def get_history_stock_status(request: StockListRequest):
    """
    3.5.2.9 历史证券信息
    获取历史证券状态，包括停牌、ST、除权除息等信息
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_history_stock_status(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "历史证券状态获取成功"
        }
    except Exception as e:
        logger.error(f"获取历史证券状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hist-code-list", summary="获取历史代码列表")
async def get_hist_code_list(request: HistCodeListRequest):
    """
    3.5.2.6 历史代码列表
    获取历史代码列表
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_hist_code_list(
            request.security_type,
            request.start_date,
            request.end_date,
            request.local_path
        )
        return {
            "status": "success",
            "data": result,
            "count": len(result) if result else 0
        }
    except Exception as e:
        logger.error(f"获取历史代码列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/code-list", summary="获取每日最新代码列表")
async def get_code_list(
    security_type: str = Query("EXTRA_STOCK_A", description="证券类型")
):
    """
    3.5.2.2 每日最新代码列表
    获取最新的每日代码列表
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_code_list(security_type)
        return {
            "status": "success",
            "data": result,
            "count": len(result) if result else 0
        }
    except Exception as e:
        logger.error(f"获取代码列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/future-code-list", summary="获取期货代码列表")
async def get_future_code_list(
    security_type: str = Query("EXTRA__FUTURE", description="证券类型")
):
    """
    3.5.2.3 每日最新代码（期货特殊接口）
    获取最新的期货代码列表
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_future_code_list(security_type)
        return {
            "status": "success",
            "data": result,
            "count": len(result) if result else 0
        }
    except Exception as e:
        logger.error(f"获取期货代码列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bj-code-mapping", summary="获取北交所代码映射")
async def get_bj_code_mapping():
    """
    3.5.2.10 北交所代码新旧代码映射表
    获取北交所代码的新旧代码映射关系
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_bj_code_mapping()
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "北交所代码映射获取成功"
        }
    except Exception as e:
        logger.error(f"获取北交所代码映射失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 3. 历史行情接口 ==================

@router.post("/query-snapshot", summary="查询历史快照")
async def query_snapshot(request: KlineRequest):
    """
    3.5.4.1 历史快照
    查询历史快照数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.query_snapshot(
            request.code_list,
            request.begin_date,
            request.end_date
        )

        # 转换结果
        if result:
            formatted_result = {}
            for code, df in result.items():
                formatted_result[code] = dataframe_to_dict(df)
            return {
                "status": "success",
                "data": formatted_result,
                "count": len(result)
            }
        else:
            return {
                "status": "success",
                "data": None,
                "count": 0
            }
    except Exception as e:
        logger.error(f"查询历史快照失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query-kline", summary="查询历史K线")
async def query_kline(request: KlineRequest):
    """
    3.5.4.2 历史K线
    查询历史K线数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.query_kline(
            request.code_list,
            request.begin_date,
            request.end_date,
            request.period
        )

        # 转换结果
        if result:
            formatted_result = {}
            for code, df in result.items():
                formatted_result[code] = dataframe_to_dict(df)
            return {
                "status": "success",
                "data": formatted_result,
                "count": len(result)
            }
        else:
            return {
                "status": "success",
                "data": None,
                "count": 0
            }
    except Exception as e:
        logger.error(f"查询历史K线失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 4. 财务数据接口 ==================

@router.post("/balance-sheet", summary="获取资产负债表")
async def get_balance_sheet(request: StockListRequest):
    """
    3.5.5.1 资产负债表
    获取指定股票的资产负债表数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_balance_sheet(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "资产负债表获取成功"
        }
    except Exception as e:
        logger.error(f"获取资产负债表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cash-flow", summary="获取现金流量表")
async def get_cash_flow(request: StockListRequest):
    """
    3.5.5.2 现金流量表
    获取指定股票的现金流量表数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_cash_flow(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "现金流量表获取成功"
        }
    except Exception as e:
        logger.error(f"获取现金流量表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/income", summary="获取利润表")
async def get_income(request: StockListRequest):
    """
    3.5.5.3 利润表
    获取指定股票的利润表数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_income(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "利润表获取成功"
        }
    except Exception as e:
        logger.error(f"获取利润表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profit-express", summary="获取业绩快报")
async def get_profit_express(request: StockListRequest):
    """
    3.5.5.4 业绩快报
    获取指定股票的业绩快报数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_profit_express(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "业绩快报获取成功"
        }
    except Exception as e:
        logger.error(f"获取业绩快报失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profit-notice", summary="获取业绩预告")
async def get_profit_notice(request: StockListRequest):
    """
    3.5.5.5 业绩预告
    获取指定股票的业绩预告数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_profit_notice(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "业绩预告获取成功"
        }
    except Exception as e:
        logger.error(f"获取业绩预告失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 5. 股东股本数据接口 ==================

@router.post("/share-holder", summary="获取十大股东数据")
async def get_share_holder(request: StockListRequest):
    """
    3.5.6.1 十大股东数据
    获取指定股票的十大股东数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_share_holder(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "十大股东数据获取成功"
        }
    except Exception as e:
        logger.error(f"获取十大股东数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/holder-num", summary="获取股东人数")
async def get_holder_num(request: StockListRequest):
    """
    3.5.6.2 股东人数
    获取指定股票的股东人数数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_holder_num(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "股东人数数据获取成功"
        }
    except Exception as e:
        logger.error(f"获取股东人数失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/equity-structure", summary="获取股本结构")
async def get_equity_structure(request: StockListRequest):
    """
    3.5.6.3 股本结构
    获取指定股票的股本结构数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_equity_structure(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "股本结构数据获取成功"
        }
    except Exception as e:
        logger.error(f"获取股本结构失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/equity-pledge-freeze", summary="获取股权质押/冻结")
async def get_equity_pledge_freeze(request: StockListRequest):
    """
    3.5.6.4 股权质押/冻结
    获取指定股票的股权质押/冻结数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_equity_pledge_freeze(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "股权质押/冻结数据获取成功"
        }
    except Exception as e:
        logger.error(f"获取股权质押/冻结失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/equity-restricted", summary="获取限售股解禁")
async def get_equity_restricted(request: StockListRequest):
    """
    3.5.6.5 限售股解禁
    获取指定股票的限售股解禁数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_equity_restricted(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "限售股解禁数据获取成功"
        }
    except Exception as e:
        logger.error(f"获取限售股解禁失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 6. 股东权益数据接口 ==================

@router.post("/dividend", summary="获取分红数据")
async def get_dividend(request: StockListRequest):
    """
    3.5.7.1 分红数据
    获取指定股票的分红数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_dividend(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "分红数据获取成功"
        }
    except Exception as e:
        logger.error(f"获取分红数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/right-issue", summary="获取配股数据")
async def get_right_issue(request: StockListRequest):
    """
    3.5.7.2 配股数据
    获取指定股票的配股数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_right_issue(
            request.code_list,
            request.local_path,
            request.is_local
        )
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "配股数据获取成功"
        }
    except Exception as e:
        logger.error(f"获取配股数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 7. 融资融券接口 ==================

@router.get("/margin-summary", summary="获取融资融券汇总")
async def get_margin_summary():
    """
    3.5.8.1 融资融券交易汇总
    获取融资融券交易汇总数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_margin_summary()
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "融资融券汇总数据获取成功"
        }
    except Exception as e:
        logger.error(f"获取融资融券汇总失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/margin-detail", summary="获取融资融券明细")
async def get_margin_detail(
    code_list: List[str] = Body(..., description="股票代码列表")
):
    """
    3.5.8.2 融资融券标的明细
    获取指定股票的融资融券明细数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_margin_detail(code_list)
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "融资融券明细数据获取成功"
        }
    except Exception as e:
        logger.error(f"获取融资融券明细失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 8. 市场异动数据接口 ==================

@router.post("/long-hu-bang", summary="获取龙虎榜数据")
async def get_long_hu_bang(
    code_list: List[str] = Body(..., description="股票代码列表")
):
    """
    3.5.9.1 龙虎榜
    获取指定股票的龙虎榜数据
    """
    try:
        provider = await get_amazingdata_provider()
        result = await provider.get_long_hu_bang(code_list)
        return {
            "status": "success",
            "data": dataframe_to_dict(result),
            "message": "龙虎榜数据获取成功"
        }
    except Exception as e:
        logger.error(f"获取龙虎榜数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== 9. 实时行情订阅接口 ==================

# 保存订阅管理器
_realtime_manager = None


@router.post("/subscribe/index", summary="订阅指数实时快照")
async def subscribe_index(request: SubscriptionRequest):
    """
    3.5.3.1 指数实时快照
    订阅指数实时快照数据
    """
    global _realtime_manager
    try:
        provider = await get_amazingdata_provider()
        if not _realtime_manager:
            _realtime_manager = AmazingDataRealtime(provider)

        success = await _realtime_manager.onSnapshotindex(request.code_list)
        if success:
            return {"status": "success", "message": f"成功订阅{len(request.code_list)}个指数"}
        else:
            raise HTTPException(status_code=400, detail="订阅失败")
    except Exception as e:
        logger.error(f"订阅指数快照失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe/stock", summary="订阅股票实时快照")
async def subscribe_stock(request: SubscriptionRequest):
    """
    3.5.3.2 股票实时快照
    订阅股票level-1行情数据
    """
    global _realtime_manager
    try:
        provider = await get_amazingdata_provider()
        if not _realtime_manager:
            _realtime_manager = AmazingDataRealtime(provider)

        success = await _realtime_manager.onSnapshot(request.code_list)
        if success:
            return {"status": "success", "message": f"成功订阅{len(request.code_list)}个股票"}
        else:
            raise HTTPException(status_code=400, detail="订阅失败")
    except Exception as e:
        logger.error(f"订阅股票快照失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe/future", summary="订阅期货实时快照")
async def subscribe_future(request: SubscriptionRequest):
    """
    3.5.3.3 期货实时快照
    订阅期货level-1行情数据
    """
    global _realtime_manager
    try:
        provider = await get_amazingdata_provider()
        if not _realtime_manager:
            _realtime_manager = AmazingDataRealtime(provider)

        success = await _realtime_manager.onSnapshotfuture(request.code_list)
        if success:
            return {"status": "success", "message": f"成功订阅{len(request.code_list)}个期货"}
        else:
            raise HTTPException(status_code=400, detail="订阅失败")
    except Exception as e:
        logger.error(f"订阅期货快照失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe/etf", summary="订阅ETF实时快照")
async def subscribe_etf(request: SubscriptionRequest):
    """
    3.5.3.4 ETF实时快照
    订阅ETF level-1行情数据
    """
    global _realtime_manager
    try:
        provider = await get_amazingdata_provider()
        if not _realtime_manager:
            _realtime_manager = AmazingDataRealtime(provider)

        success = await _realtime_manager.onSnapshotetf(request.code_list)
        if success:
            return {"status": "success", "message": f"成功订阅{len(request.code_list)}个ETF"}
        else:
            raise HTTPException(status_code=400, detail="订阅失败")
    except Exception as e:
        logger.error(f"订阅ETF快照失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe/kzz", summary="订阅可转债实时快照")
async def subscribe_kzz(request: SubscriptionRequest):
    """
    3.5.3.5 可转债实时快照
    订阅可转债level-1行情数据
    """
    global _realtime_manager
    try:
        provider = await get_amazingdata_provider()
        if not _realtime_manager:
            _realtime_manager = AmazingDataRealtime(provider)

        success = await _realtime_manager.onSnapshotkzz(request.code_list)
        if success:
            return {"status": "success", "message": f"成功订阅{len(request.code_list)}个可转债"}
        else:
            raise HTTPException(status_code=400, detail="订阅失败")
    except Exception as e:
        logger.error(f"订阅可转债快照失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe/hkt", summary="订阅港股通实时快照")
async def subscribe_hkt(request: SubscriptionRequest):
    """
    3.5.3.6 港股通实时快照
    订阅港股通行情数据
    """
    global _realtime_manager
    try:
        provider = await get_amazingdata_provider()
        if not _realtime_manager:
            _realtime_manager = AmazingDataRealtime(provider)

        success = await _realtime_manager.onSnapshothkt(request.code_list)
        if success:
            return {"status": "success", "message": f"成功订阅{len(request.code_list)}个港股通"}
        else:
            raise HTTPException(status_code=400, detail="订阅失败")
    except Exception as e:
        logger.error(f"订阅港股通快照失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe/kline", summary="订阅实时K线")
async def subscribe_kline(request: SubscriptionRequest):
    """
    3.5.3.7 实时K线
    订阅K线数据
    """
    global _realtime_manager
    try:
        provider = await get_amazingdata_provider()
        if not _realtime_manager:
            _realtime_manager = AmazingDataRealtime(provider)

        success = await _realtime_manager.OnKLine(request.code_list, request.period)
        if success:
            return {"status": "success", "message": f"成功订阅{len(request.code_list)}个K线"}
        else:
            raise HTTPException(status_code=400, detail="订阅失败")
    except Exception as e:
        logger.error(f"订阅K线失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unsubscribe", summary="停止所有订阅")
async def unsubscribe():
    """停止所有订阅"""
    global _realtime_manager
    try:
        if _realtime_manager:
            await _realtime_manager.stop_subscription()
            return {"status": "success", "message": "已停止所有订阅"}
        else:
            return {"status": "success", "message": "没有活动的订阅"}
    except Exception as e:
        logger.error(f"停止订阅失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscription-status", summary="获取订阅状态")
async def get_subscription_status():
    """获取订阅状态"""
    global _realtime_manager
    if _realtime_manager:
        status = _realtime_manager.get_subscription_status()
        return {"status": "success", "data": status}
    else:
        return {"status": "success", "data": {"active": False, "subscriptions": [], "subscription_count": 0}}