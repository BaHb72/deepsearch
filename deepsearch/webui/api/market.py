"""
市场数据 API
提供市场概览、板块行情、异动监控等接口
"""
from typing import List

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from deepsearch.data_providers.akshare_proxy_provider import AkShareProxyProvider
from deepsearch.services.market_service import MarketService

router = APIRouter(prefix="/api/market", tags=["市场数据"])

# 全局市场服务实例
market_service = None


def get_market_service() -> MarketService:
    """获取市场服务实例"""
    global market_service
    if market_service is None:
        # 初始化数据提供者
        data_provider = AkShareProxyProvider()
        # 初始化市场服务
        market_service = MarketService(data_provider)
    return market_service


class MarketOverviewResponse(BaseModel):
    """市场概览响应"""
    indices: List[dict]  # 指数数据
    breadth: dict  # 市场宽度
    capital: dict  # 资金流向
    timestamp: str  # 时间戳
    stale: bool  # 是否为缓存数据


class SectorResponse(BaseModel):
    """板块数据响应"""
    code: str
    name: str
    change_pct: float
    amount: float
    leader: dict


class AnomalyResponse(BaseModel):
    """异动数据响应"""
    symbol: str
    name: str
    price: float
    change_pct: float
    amount: float
    reason: str
    timestamp: str
    extra: dict


@router.get("/overview", response_model=MarketOverviewResponse)
async def get_market_overview():
    """
    获取市场概览数据
    
    包括：
    - 主要指数（上证、深证、创业板、北证）
    - 市场宽度（涨跌家数、涨停跌停数）
    - 资金流向（北向资金、成交额等）
    """
    try:
        service = get_market_service()
        data = await service.get_market_overview()
        return data
    except Exception as e:
        logger.error(f"获取市场概览失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sectors", response_model=List[SectorResponse])
async def get_sectors(
        type: str = Query("industry", description="板块类型: industry(行业) / concept(概念)"),
        limit: int = Query(20, description="返回数量", ge=1, le=100),
        sort: str = Query("change_pct", description="排序字段: change_pct / amount / volume")
):
    """
    获取板块排行数据
    
    参数：
    - type: 板块类型（industry=行业板块, concept=概念板块）
    - limit: 返回数量限制
    - sort: 排序字段（change_pct=涨跌幅, amount=成交额, volume=成交量）
    """
    try:
        service = get_market_service()
        data = await service.get_sectors(
            sector_type=type,
            limit=limit,
            sort_by=sort
        )
        return data
    except Exception as e:
        logger.error(f"获取板块数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomalies", response_model=List[AnomalyResponse])
async def get_anomalies(
        kind: str = Query("all", description="异动类型: all / limit_up / limit_down / price_surge / volume_spike"),
        min_change: float = Query(0, description="最小涨跌幅过滤（%）"),
        min_amount: float = Query(0, description="最小成交额过滤（元）")
):
    """
    获取异动股票数据
    
    参数：
    - kind: 异动类型
        - all: 全部异动
        - limit_up: 涨停
        - limit_down: 跌停
        - price_surge: 急速拉升
        - volume_spike: 放量异动
    - min_change: 最小涨跌幅过滤
    - min_amount: 最小成交额过滤
    """
    try:
        service = get_market_service()
        data = await service.get_anomalies(
            kind=kind,
            min_change=min_change,
            min_amount=min_amount
        )
        return data
    except Exception as e:
        logger.error(f"获取异动数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{symbol}/intraday")
async def get_stock_intraday(
        symbol: str,
        period: int = Query(1, description="时间周期（分钟）", ge=1, le=60),
        limit: int = Query(240, description="数据点数量", ge=1, le=1000)
):
    """
    获取个股分时数据
    
    参数：
    - symbol: 股票代码（如：000001）
    - period: 时间周期（1=1分钟线, 5=5分钟线, 等）
    - limit: 返回的数据点数量
    """
    try:
        service = get_market_service()
        data = await service.get_stock_intraday(
            symbol=symbol,
            period=period,
            limit=limit
        )
        return {
            "symbol": symbol,
            "period": period,
            "data": data
        }
    except Exception as e:
        logger.error(f"获取分时数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_market_stats():
    """
    获取市场服务统计信息
    
    包括：
    - 总请求数
    - 缓存命中率
    - API错误数
    - 最后更新时间
    """
    try:
        service = get_market_service()
        stats = service.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_market_data(
        category: str = Query("all", description="刷新类别: all / overview / sectors / anomalies")
):
    """
    强制刷新市场数据（清除缓存）
    
    参数：
    - category: 要刷新的数据类别
    """
    try:
        service = get_market_service()

        # 清除指定类别的缓存
        if category == "all":
            service._cache.clear()
            message = "已清除所有市场数据缓存"
        else:
            # 清除特定类别的缓存
            keys_to_remove = [k for k in service._cache.keys() if k.startswith(f"{category}:")]
            for key in keys_to_remove:
                del service._cache[key]
            message = f"已清除 {category} 数据缓存"

        logger.info(message)
        return {"success": True, "message": message}

    except Exception as e:
        logger.error(f"刷新市场数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
