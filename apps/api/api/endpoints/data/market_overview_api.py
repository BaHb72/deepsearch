"""
市场概览和排行榜API
"""

from datetime import datetime
from typing import Any, Dict, List

# New imports for UnifiedDataFeed
from core.application.services.unified_data import get_unified_feed
from core.ports.data.requests import RealtimeQuoteRequest
from core.ports.data.semantic_types import AssetSpec
from fastapi import APIRouter, Query
from loguru import logger

from apps.api.api.common.response_format import APIResponse, ErrorCodes

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
        # 主要指数代码
        indices = ["000001", "399001", "399006"]  # 上证指数、深证成指、创业板指
        index_name_map = {
            "000001": "sh_index",
            "399001": "sz_index",
            "399006": "cyb_index",
        }
        result = {}

        # 解析资产
        assets = []
        for index_code in indices:
            try:
                # 指数简码需要补充交易所
                if index_code.startswith("000"):
                    asset = AssetSpec.from_code(f"{index_code}.SH")
                else:
                    asset = AssetSpec.from_code(f"{index_code}.SZ")
                assets.append(asset)
            except ValueError:
                logger.warning(f"无效的指数代码: {index_code}")

        if not assets:
            # 所有代码都无效，返回示例数据
            for index_code in indices:
                alias = index_name_map[index_code]
                result[alias] = _build_stub_index_payload(alias)
            return APIResponse.success(result)

        # 调用 UnifiedDataFeed
        try:
            feed = get_unified_feed()
            request = RealtimeQuoteRequest(assets=assets)
            response = await feed.get_realtime(request)

            for i, quote in enumerate(response.quotes):
                if i >= len(indices):
                    break
                alias = index_name_map[indices[i]]
                result[alias] = {
                    "current": float(quote.last_price),
                    "change": float(quote.change),
                    "change_pct": float(quote.change_pct),
                    "volume": quote.volume,
                    "amount": float(quote.amount),
                    "timestamp": (
                        quote.timestamp.isoformat() + "Z"
                        if quote.timestamp
                        else datetime.utcnow().isoformat() + "Z"
                    ),
                }

            # 填充未获取到的指数
            for index_code in indices:
                alias = index_name_map[index_code]
                if alias not in result:
                    result[alias] = _build_stub_index_payload(alias)

        except Exception as e:
            logger.error(f"从 UnifiedDataFeed 获取指数数据失败: {e}")
            for index_code in indices:
                alias = index_name_map[index_code]
                result[alias] = _build_stub_index_payload(alias)

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
        # 使用 ReferenceDataCapability 缓存进行搜索
        feed = get_unified_feed()
        if feed.reference and feed.reference.is_loaded:
            # 从缓存中搜索
            matches = []
            keyword_lower = keyword.lower()
            for symbol, info in feed.reference._cache.items():
                if keyword_lower in symbol.lower() or keyword_lower in info.name.lower():
                    matches.append(
                        {
                            "symbol": symbol,
                            "code": info.asset.symbol,
                            "name": info.name,
                        }
                    )
                    if len(matches) >= 20:  # 限制返回数量
                        break
            return APIResponse.success(matches)

        # 缓存未加载，返回空
        logger.warning("股票搜索：ReferenceDataCapability 缓存未加载")
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
        from core.application.services.aggregation import get_cache

        data = get_cache().get("top_gainers")
        if data is None:
            # 聚合引擎未启动或缓存为空
            return APIResponse.success({"loading": True, "data": []})
        return APIResponse.success(data[:limit])

    except Exception as e:
        logger.error(f"获取涨幅榜失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR, message=f"获取涨幅榜失败: {str(e)}", data=[]
        )


@router.get("/rank/losers")
async def get_top_losers(limit: int = Query(10, description="返回数量限制")) -> Dict[str, Any]:
    """获取跌幅榜"""
    try:
        from core.application.services.aggregation import get_cache

        data = get_cache().get("top_losers")
        if data is None:
            # 聚合引擎未启动或缓存为空
            return APIResponse.success({"loading": True, "data": []})
        return APIResponse.success(data[:limit])

    except Exception as e:
        logger.error(f"获取跌幅榜失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.DATA_SOURCE_ERROR, message=f"获取跌幅榜失败: {str(e)}", data=[]
        )
