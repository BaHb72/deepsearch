"""
市场概览和排行榜API
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Query, HTTPException

from loguru import logger
from deepsearch.infrastructure.providers.managers.data_source_manager import (
    get_data_source_manager
)
from deepsearch.webui.api.common.response_format import APIResponse, ErrorCodes

router = APIRouter(prefix="/api/data")


@router.get("/market/overview")
async def get_market_overview() -> Dict[str, Any]:
    """获取市场概览数据"""
    try:
        manager = get_data_source_manager()

        # 获取主要指数数据
        indices = ["000001", "399001", "399006"]  # 上证指数、深圳成指、创业板指
        result = {}

        for index_code in indices:
            try:
                # 尝试获取实时行情
                data = await manager.execute_with_fallback(
                    "get_realtime_quote",
                    symbol=index_code
                )

                if data:
                    # 映射到响应格式
                    index_name_map = {
                        "000001": "sh_index",
                        "399001": "sz_index",
                        "399006": "cyb_index"
                    }

                    result[index_name_map[index_code]] = {
                        "current": data.get("price", 0),
                        "change": data.get("change", 0),
                        "change_pct": data.get("change_pct", 0),
                        "volume": data.get("volume", 0),
                        "amount": data.get("amount", 0)
                    }
            except Exception as e:
                logger.error(f"获取指数{index_code}数据失败: {e}")
                continue

        # 如果没有获取到任何数据，返回错误信息
        if not result:
            return APIResponse.error(
                code=ErrorCodes.DATA_SOURCE_ERROR,
                message="无法获取市场概览数据，请检查数据源连接",
                data={}
            )

        return APIResponse.success(result)

    except Exception as e:
        logger.error(f"获取市场概览失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"获取市场概览失败: {str(e)}",
            status_code=500
        )


@router.get("/search")
async def search_stocks(
    keyword: str = Query(..., description="搜索关键字")
) -> Dict[str, Any]:
    """搜索股票"""
    try:
        manager = get_data_source_manager()

        # 调用搜索方法
        result = await manager.execute_with_fallback(
            "search_stocks",
            keyword=keyword
        )

        if result:
            return APIResponse.success(result)

        # 如果没有搜索结果，返回空列表
        return APIResponse.success([])

    except Exception as e:
        logger.error(f"搜索股票失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR,
            message=f"搜索股票失败: {str(e)}",
            data=[]
        )


@router.get("/rank/gainers")
async def get_top_gainers(
    limit: int = Query(10, description="返回数量限制")
) -> Dict[str, Any]:
    """获取涨幅榜"""
    try:
        manager = get_data_source_manager()

        # 获取涨幅榜数据
        result = await manager.execute_with_fallback(
            "get_top_gainers",
            limit=limit
        )

        if result:
            return APIResponse.success(result[:limit])

        # 没有数据时返回错误信息
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR,
            message="无法获取涨幅榜数据，请检查数据源连接",
            data=[]
        )

    except Exception as e:
        logger.error(f"获取涨幅榜失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR,
            message=f"获取涨幅榜失败: {str(e)}",
            data=[]
        )


@router.get("/rank/losers")
async def get_top_losers(
    limit: int = Query(10, description="返回数量限制")
) -> Dict[str, Any]:
    """获取跌幅榜"""
    try:
        manager = get_data_source_manager()

        # 获取跌幅榜数据
        result = await manager.execute_with_fallback(
            "get_top_losers",
            limit=limit
        )

        if result:
            return APIResponse.success(result[:limit])

        # 没有数据时返回错误信息
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR,
            message="无法获取跌幅榜数据，请检查数据源连接",
            data=[]
        )

    except Exception as e:
        logger.error(f"获取跌幅榜失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR,
            message=f"获取跌幅榜失败: {str(e)}",
            data=[]
        )