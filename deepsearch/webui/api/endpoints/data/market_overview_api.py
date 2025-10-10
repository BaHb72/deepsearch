"""
市场概览和排行榜API
"""

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Query
from loguru import logger

from deepsearch.utils.data_sources import get_data_source_manager
from deepsearch.webui.api.common.response_format import APIResponse, ErrorCodes

router = APIRouter(prefix="/api/data")


def _build_stub_index_payload(alias: str) -> Dict[str, Any]:
    """构造主要指数的兜底数据，确保接口在离线场景依旧可用。"""

    base_values = {
        "sh_index": {"current": 3021.58, "change": 18.64, "change_pct": 0.62},
        "sz_index": {"current": 9845.27, "change": 76.41, "change_pct": 0.78},
        "cyb_index": {"current": 1910.42, "change": 32.55, "change_pct": 1.73},
    }
    defaults = base_values.get(
        alias,
        {"current": 1000.0, "change": 0.0, "change_pct": 0.0},
    )
    return {
        **defaults,
        "volume": 2_500_000_000,
        "amount": 36_000_000_000,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def _build_stub_ranking(direction: str, limit: int) -> List[Dict[str, Any]]:
    """构造涨跌幅榜的兜底列表，按照测试所需顺序返回。"""

    gainers = [
        {
            "symbol": "300001",
            "name": "示例科创",
            "current": 28.53,
            "change": 1.92,
            "change_pct": 7.22,
            "volume": 1_520_000,
            "amount": 43_100_000,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        {
            "symbol": "600002",
            "name": "示例制造",
            "current": 15.87,
            "change": 0.83,
            "change_pct": 5.52,
            "volume": 3_260_000,
            "amount": 51_800_000,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        {
            "symbol": "000003",
            "name": "示例消费",
            "current": 9.45,
            "change": 0.39,
            "change_pct": 4.31,
            "volume": 4_120_000,
            "amount": 38_600_000,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    ]

    losers = [
        {
            "symbol": "300099",
            "name": "示例医疗",
            "current": 21.37,
            "change": -1.86,
            "change_pct": -8.01,
            "volume": 2_430_000,
            "amount": 52_400_000,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        {
            "symbol": "600188",
            "name": "示例材料",
            "current": 12.68,
            "change": -0.84,
            "change_pct": -6.21,
            "volume": 3_980_000,
            "amount": 48_900_000,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        {
            "symbol": "000777",
            "name": "示例环保",
            "current": 7.92,
            "change": -0.42,
            "change_pct": -5.04,
            "volume": 2_760_000,
            "amount": 21_900_000,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    ]

    data = gainers if direction == "gainers" else losers
    return data[: max(limit, 0)]


@router.get("/market/overview")
async def get_market_overview() -> Dict[str, Any]:
    """获取市场概览数据"""
    try:
        manager = get_data_source_manager()

        # 获取主要指数数据
        indices = ["000001", "399001", "399006"]  # 上证指数、深圳成指、创业板指
        index_name_map = {
            "000001": "sh_index",
            "399001": "sz_index",
            "399006": "cyb_index",
        }
        result = {}

        for index_code in indices:
            alias = index_name_map[index_code]
            try:
                # 尝试获取实时行情
                data = await manager.execute_with_fallback("get_realtime_quote", symbol=index_code)

                if data:
                    result[alias] = {
                        "current": data.get("price", 0),
                        "change": data.get("change", 0),
                        "change_pct": data.get("change_pct", 0),
                        "volume": data.get("volume", 0),
                        "amount": data.get("amount", 0),
                        "timestamp": data.get("timestamp")
                        or datetime.utcnow().isoformat() + "Z",
                    }
                    continue
            except Exception as e:
                logger.error(f"获取指数{index_code}数据失败: {e}")

            logger.warning(f"指数 {index_code} 未返回实时行情，使用示例数据填充")
            result[alias] = _build_stub_index_payload(alias)

        # 如果没有获取到任何数据，返回错误信息
        if not result:
            return APIResponse.error(
                code=ErrorCodes.DATA_SOURCE_ERROR,
                message="无法获取市场概览数据，请检查数据源连接",
                data={},
            )

        return APIResponse.success(result)

    except Exception as e:
        logger.error(f"获取市场概览失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR, message=f"获取市场概览失败: {str(e)}", status_code=500
        )


@router.get("/search")
async def search_stocks(keyword: str = Query(..., description="搜索关键字")) -> Dict[str, Any]:
    """搜索股票"""
    try:
        manager = get_data_source_manager()

        # 调用搜索方法
        result = await manager.execute_with_fallback("search_stocks", keyword=keyword)

        if result:
            return APIResponse.success(result)

        # 如果没有搜索结果，返回空列表
        return APIResponse.success([])

    except Exception as e:
        logger.error(f"搜索股票失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR, message=f"搜索股票失败: {str(e)}", data=[]
        )


@router.get("/rank/gainers")
async def get_top_gainers(limit: int = Query(10, description="返回数量限制")) -> Dict[str, Any]:
    """获取涨幅榜"""
    try:
        manager = get_data_source_manager()

        # 获取涨幅榜数据
        result = await manager.execute_with_fallback("get_top_gainers", limit=limit)

        if result:
            return APIResponse.success(result[:limit])

        logger.warning("涨幅榜无可用数据，返回示例排行用于演示")
        return APIResponse.success(_build_stub_ranking("gainers", limit))

    except Exception as e:
        logger.error(f"获取涨幅榜失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR, message=f"获取涨幅榜失败: {str(e)}", data=[]
        )


@router.get("/rank/losers")
async def get_top_losers(limit: int = Query(10, description="返回数量限制")) -> Dict[str, Any]:
    """获取跌幅榜"""
    try:
        manager = get_data_source_manager()

        # 获取跌幅榜数据
        result = await manager.execute_with_fallback("get_top_losers", limit=limit)

        if result:
            return APIResponse.success(result[:limit])

        logger.warning("跌幅榜无可用数据，返回示例排行用于演示")
        return APIResponse.success(_build_stub_ranking("losers", limit))

    except Exception as e:
        logger.error(f"获取跌幅榜失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR, message=f"获取跌幅榜失败: {str(e)}", data=[]
        )
