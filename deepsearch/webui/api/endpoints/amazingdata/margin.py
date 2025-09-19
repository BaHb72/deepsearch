"""
AmazingData 融资融券和龙虎榜数据接口
包含融资融券汇总、明细和龙虎榜数据
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from .base import get_provider, handle_amazingdata_error, create_response

router = APIRouter()


@router.get("/margin-summary", summary="获取融资融券汇总数据")
async def get_margin_summary(
    code: Optional[str] = Query(None, description="证券代码，如SH.600000，不填则返回市场汇总"),
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    market: Optional[str] = Query(None, description="市场类型：SH/SZ/ALL")
):
    """
    获取融资融券汇总数据

    Parameters:
        code: 证券代码（可选）
        start_date: 开始日期
        end_date: 结束日期
        market: 市场类型

    Returns:
        融资融券汇总数据，包含：
        - 日期
        - 融资余额
        - 融券余额
        - 融资买入额
        - 融券卖出量
        - 融资融券余额
    """
    try:
        provider = await get_provider()

        # 构建参数
        params = {}
        if code:
            params['code'] = code
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        if market:
            params['market'] = market

        # 调用SDK接口
        result = await handle_amazingdata_error(
            provider.get_margin_summary(**params)
        )

        return create_response(
            data=result,
            message="获取融资融券汇总数据成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取融资融券汇总数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/margin-detail", summary="获取融资融券明细数据")
async def get_margin_detail(
    code: str = Query(..., description="证券代码，如SH.600000"),
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    fields: Optional[List[str]] = Query(None, description="需要返回的字段列表")
):
    """
    获取单个证券的融资融券明细数据

    Parameters:
        code: 证券代码（必填）
        start_date: 开始日期
        end_date: 结束日期
        fields: 需要返回的字段列表

    Returns:
        融资融券明细数据，包含：
        - 日期
        - 证券代码
        - 证券名称
        - 融资余额
        - 融资买入额
        - 融资偿还额
        - 融券余量
        - 融券卖出量
        - 融券偿还量
        - 融资融券余额
        - 融资融券余额差值
        - 融资融券余额占流通市值比
    """
    try:
        provider = await get_provider()

        # 构建参数
        params = {'code': code}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        if fields:
            params['fields'] = fields

        # 调用SDK接口
        result = await handle_amazingdata_error(
            provider.get_margin_detail(**params)
        )

        return create_response(
            data=result,
            message=f"获取{code}融资融券明细数据成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取融资融券明细数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/long-hu-bang", summary="获取龙虎榜数据")
async def get_long_hu_bang(
    date: Optional[str] = Query(None, description="日期，格式：YYYY-MM-DD，不填则返回最新"),
    code: Optional[str] = Query(None, description="证券代码，如SH.600000"),
    reason: Optional[str] = Query(None, description="上榜原因类型"),
    limit: int = Query(100, description="返回数据条数限制")
):
    """
    获取龙虎榜数据

    Parameters:
        date: 查询日期（可选）
        code: 证券代码（可选）
        reason: 上榜原因（可选）
        limit: 返回数据条数

    Returns:
        龙虎榜数据，包含：
        - 日期
        - 证券代码
        - 证券名称
        - 收盘价
        - 涨跌幅
        - 成交额
        - 上榜原因
        - 买入营业部
        - 买入金额
        - 卖出营业部
        - 卖出金额
        - 净买入金额
        - 买入前五占比
        - 卖出前五占比
    """
    try:
        provider = await get_provider()

        # 构建参数
        params = {'limit': limit}
        if date:
            params['date'] = date
        if code:
            params['code'] = code
        if reason:
            params['reason'] = reason

        # 调用SDK接口
        result = await handle_amazingdata_error(
            provider.get_long_hu_bang(**params)
        )

        # 处理返回数据
        if isinstance(result, dict):
            # 如果返回的是字典，可能包含多个部分
            response_data = {
                'summary': result.get('summary', []),
                'details': result.get('details', []),
                'statistics': result.get('statistics', {})
            }
        else:
            # 如果返回的是DataFrame或列表
            response_data = result

        return create_response(
            data=response_data,
            message="获取龙虎榜数据成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取龙虎榜数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))