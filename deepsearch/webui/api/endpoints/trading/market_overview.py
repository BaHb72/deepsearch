"""
市场总貌和交易所统计数据API
"""

import asyncio
from typing import Dict, TypedDict, cast

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from deepsearch.webui.api.types import JSONDict, JSONValue

router = APIRouter(prefix="/api/market-overview", tags=["市场总貌"])


class MarketResponse(TypedDict, total=False):
    success: bool
    data: JSONValue
    error: str
    source: str
    symbol: str
    total: int
    market: str



class MarketDataProvider:
    """市场数据提供者"""

    def __init__(self):
        self._cache: Dict[str, MarketResponse] = {}
        self._cache_ttl = 60  # 60秒缓存

    async def get_sse_summary(self) -> MarketResponse:
        """获取上海证券交易所市场总貌"""
        try:
            import akshare as ak

            df = await asyncio.get_event_loop().run_in_executor(None, ak.stock_sse_summary)
            if df is not None and not df.empty:
                return {"success": True, "data": df.to_dict("records"), "source": "SSE"}
            return {"success": False, "error": "No data"}
        except Exception as e:
            logger.error(f"获取上交所数据失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_szse_summary(self, date: str) -> MarketResponse:
        """获取深圳证券交易所市场总貌"""
        try:
            import akshare as ak

            df = await asyncio.get_event_loop().run_in_executor(None, ak.stock_szse_summary, date)
            if df is not None and not df.empty:
                return {"success": True, "data": df.to_dict("records"), "source": "SZSE"}
            return {"success": False, "error": "No data"}
        except Exception as e:
            logger.error(f"获取深交所数据失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_szse_area_summary(self, date: str) -> MarketResponse:
        """获取深交所地区交易排序"""
        try:
            import akshare as ak

            df = await asyncio.get_event_loop().run_in_executor(
                None, ak.stock_szse_area_summary, date
            )
            if df is not None and not df.empty:
                return {"success": True, "data": df.to_dict("records"), "source": "SZSE"}
            return {"success": False, "error": "No data"}
        except Exception as e:
            logger.error(f"获取地区交易数据失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_szse_sector_summary(self, symbol: str, date: str) -> MarketResponse:
        """获取深交所行业成交数据"""
        try:
            import akshare as ak

            df = await asyncio.get_event_loop().run_in_executor(
                None, ak.stock_szse_sector_summary, symbol, date
            )
            if df is not None and not df.empty:
                return {"success": True, "data": df.to_dict("records"), "source": "SZSE"}
            return {"success": False, "error": "No data"}
        except Exception as e:
            logger.error(f"获取行业成交数据失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_sse_deal_daily(self, date: str) -> MarketResponse:
        """获取上交所每日概况"""
        try:
            import akshare as ak

            df = await asyncio.get_event_loop().run_in_executor(None, ak.stock_sse_deal_daily, date)
            if df is not None and not df.empty:
                return {"success": True, "data": df.to_dict("records"), "source": "SSE"}
            return {"success": False, "error": "No data"}
        except Exception as e:
            logger.error(f"获取上交所每日概况失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_individual_info(self, symbol: str) -> MarketResponse:
        """获取个股信息"""
        try:
            import akshare as ak

            # 东财个股信息
            df_em = await asyncio.get_event_loop().run_in_executor(
                None, ak.stock_individual_info_em, symbol
            )

            data_payload: JSONDict = {}

            if df_em is not None and not df_em.empty:
                data_payload["eastmoney"] = cast(JSONValue, df_em.to_dict("records"))

            # 尝试获取雪球数据
            try:
                # 格式化symbol为雪球格式
                xq_symbol = f"SH{symbol}" if symbol.startswith("6") else f"SZ{symbol}"
                df_xq = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_individual_basic_info_xq, xq_symbol
                )
                if df_xq is not None and not df_xq.empty:
                    data_payload["xueqiu"] = cast(JSONValue, df_xq.to_dict("records"))
            except Exception as exc:
                logger.opt(exception=exc).debug("获取市场概览时遇到可忽略的异常")

            return {
                "success": True,
                "symbol": symbol,
                "data": data_payload,
            }
        except Exception as e:
            logger.error(f"获取个股信息失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_bid_ask(self, symbol: str) -> MarketResponse:
        """获取盘口数据"""
        try:
            import akshare as ak

            df = await asyncio.get_event_loop().run_in_executor(None, ak.stock_bid_ask_em, symbol)
            if df is not None and not df.empty:
                return {"success": True, "data": df.to_dict("records"), "symbol": symbol}
            return {"success": False, "error": "No data"}
        except Exception as e:
            logger.error(f"获取盘口数据失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_spot_em(self, market: str = "all") -> MarketResponse:
        """获取实时行情数据"""
        try:
            import akshare as ak

            # 根据市场选择对应的函数
            func_map = {
                "all": ak.stock_zh_a_spot_em,
                "sh": ak.stock_sh_a_spot_em,
                "sz": ak.stock_sz_a_spot_em,
                "bj": ak.stock_bj_a_spot_em,
                "cy": ak.stock_cy_a_spot_em,
                "kc": ak.stock_kc_a_spot_em,
                "new": ak.stock_new_a_spot_em,
            }

            func = func_map.get(market, ak.stock_zh_a_spot_em)
            df = await asyncio.get_event_loop().run_in_executor(None, func)

            if df is not None and not df.empty:
                # 限制返回数量避免数据过大
                data = df.head(100).to_dict("records")
                return {"success": True, "data": data, "total": len(df), "market": market}
            return {"success": False, "error": "No data"}
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return {"success": False, "error": str(e)}


# 全局实例
provider = MarketDataProvider()


@router.get("/sse-summary")
async def get_sse_summary():
    """获取上海证券交易所市场总貌"""
    result = await provider.get_sse_summary()
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error"))


@router.get("/szse-summary")
async def get_szse_summary(date: str = Query(..., description="日期，格式：20240619")):
    """获取深圳证券交易所市场总貌"""
    result = await provider.get_szse_summary(date)
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error"))


@router.get("/szse-area")
async def get_szse_area(date: str = Query(..., description="年月，格式：202412")):
    """获取深交所地区交易排序"""
    result = await provider.get_szse_area_summary(date)
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error"))


@router.get("/szse-sector")
async def get_szse_sector(
    symbol: str = Query("当月", description="当月/当年"),
    date: str = Query(..., description="年月，格式：202501"),
):
    """获取深交所行业成交数据"""
    result = await provider.get_szse_sector_summary(symbol, date)
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error"))


@router.get("/sse-daily")
async def get_sse_daily(date: str = Query(..., description="日期，格式：20250221")):
    """获取上交所每日概况"""
    result = await provider.get_sse_deal_daily(date)
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error"))


@router.get("/stock/{symbol}/info")
async def get_stock_info(symbol: str):
    """获取个股详细信息"""
    result = await provider.get_individual_info(symbol)
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error"))


@router.get("/stock/{symbol}/bid-ask")
async def get_stock_bid_ask(symbol: str):
    """获取个股盘口数据"""
    result = await provider.get_bid_ask(symbol)
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error"))


@router.get("/spot")
async def get_spot_data(market: str = Query("all", description="市场类型: all/sh/sz/bj/cy/kc/new")):
    """
    获取实时行情数据

    市场类型：
    - all: 沪深京A股
    - sh: 沪A股
    - sz: 深A股
    - bj: 京A股
    - cy: 创业板
    - kc: 科创板
    - new: 新股
    """
    result = await provider.get_spot_em(market)
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result.get("error"))
