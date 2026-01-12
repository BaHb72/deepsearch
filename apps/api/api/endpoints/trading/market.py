"""
市场数据 API
提供市场概览、板块行情、异动监控等接口
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from apps.api.api.providers import get_market_service

router = APIRouter(prefix="/api/trading/market", tags=["�г�����"])

# 数据源状态缓存
_data_source_status_cache = {
    "data": None,
    "timestamp": 0,
    "ttl": 60,  # 增加到60秒缓存，减少查询频率
}


class MarketOverviewResponse(BaseModel):
    """�г�������Ӧ"""

    indices: List[dict]  # ָ������
    breadth: dict  # �г�����
    capital: dict  # �ʽ�����
    total_market_cap: float = 0.0
    total_volume: float = 0.0
    market_sentiment: str = "unknown"
    timestamp: str  # ʱ���
    stale: bool  # �Ƿ�Ϊ��������
    data_source: str = "unknown"  # ����Դ


class SectorResponse(BaseModel):
    """板块数据响应"""

    code: str
    name: str
    change_pct: float
    amount: float
    leader: dict
    advancers: int = 0  # 上涨家数
    decliners: int = 0  # 下跌家数


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


class DataSourceStatus(BaseModel):
    """数据源状态响应"""

    source: str  # 当前数据源
    mode: str  # 模式: workers/direct/cache
    worker_url: str = ""  # Worker URL(如果使用)
    healthy: bool = True  # 是否健康
    latency: float = 0  # 平均延迟
    statistics: dict = {}  # 统计信息


class MarketActivityResponse(BaseModel):
    """赚钱效应分析响应"""

    rise: int  # 上涨家数
    fall: int  # 下跌家数
    flat: int  # 平盘家数
    limit_up: int  # 涨停家数
    limit_down: int  # 跌停家数
    real_limit_up: int  # 真实涨停（非一字）
    real_limit_down: int  # 真实跌停（非一字）
    st_limit_up: int  # ST涨停
    st_limit_down: int  # ST跌停
    halt: int  # 停牌家数
    activity_rate: str  # 活跃度
    rise_ratio: str  # 涨跌比
    statistics_time: str  # 统计时间
    timestamp: str  # 更新时间


class StockChangeItem(BaseModel):
    """盘口异动项"""

    time: str  # 时间
    symbol: str  # 代码
    name: str  # 名称
    sector: str  # 板块
    info: str  # 相关信息
    change_type: str  # 异动类型


class ZTPoolItem(BaseModel):
    """涨停股池项"""

    rank: int  # 排名
    symbol: str  # 代码
    name: str  # 名称
    change_pct: float  # 涨跌幅
    price: float  # 最新价
    amount: int  # 成交额
    turnover_rate: float  # 换手率
    seal_funds: int  # 封板资金
    first_seal_time: str  # 首次封板时间
    last_seal_time: str  # 最后封板时间
    open_times: int  # 炸板次数
    zt_stats: str  # 涨停统计
    continuous_days: int  # 连板数
    industry: str  # 所属行业


@router.get("/overview", response_model=MarketOverviewResponse)
async def get_market_overview(service=Depends(get_market_service)):
    """
    获取市场概览数据

    包括：
    - 主要指数（上证、深证、创业板、北证）
    - 市场宽度（涨跌家数、涨停跌停数）
    - 资金流向（北向资金、成交额等）
    """
    try:
        data = await service.get_market_overview()

        # 获取数据源信息
        if hasattr(service, "data_provider") and service.data_provider:
            provider = service.data_provider
            # 获取最近成功的Worker或模式
            if hasattr(provider, "_last_successful_worker") and provider._last_successful_worker:
                data["data_source"] = f"workers:{provider._last_successful_worker}"
            elif hasattr(provider, "worker_urls") and provider.worker_urls:
                # 检查是否有健康的Worker
                healthy_workers = [
                    url for url in provider.worker_urls if provider.worker_health.get(url, False)
                ]
                if healthy_workers:
                    data["data_source"] = f"workers:{healthy_workers[0]}"
                else:
                    data["data_source"] = "direct:akshare"
            else:
                data["data_source"] = "unknown"

        return data
    except Exception as e:
        logger.error(f"获取市场概览失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sectors", response_model=List[SectorResponse])
async def get_sectors(
    type: str = Query(
        "industry", description="板块类型: industry(行业) / concept(概念) / region(地域)"
    ),
    limit: int = Query(20, description="返回数量", ge=1, le=100),
    sort: str = Query("change_pct", description="排序字段: change_pct / amount / volume"),
    level: str = Query(
        "sw1",
        description="行业分级(仅industry时有效): sw1(申万一级) / sw2(申万二级) / sw3(申万三级)",
    ),
    service=Depends(get_market_service),
):
    """
    获取板块排行数据

    参数：
    - type: 板块类型（industry=行业板块, concept=概念板块, region=地域板块）
    - limit: 返回数量限制
    - sort: 排序字段（change_pct=涨跌幅, amount=成交额, volume=成交量）
    - level: 行业板块的分级（仅当type=industry时有效）
    """
    try:
        data = await service.get_sectors(
            sector_type=type, limit=limit, sort_by=sort, level=level if type == "industry" else None
        )
        return data
    except Exception as e:
        logger.error(f"获取板块数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/concept-ths/list")
async def get_ths_concept_list(service=Depends(get_market_service)):
    """
    获取同花顺概念板块列表
    """
    try:
        # 使用直连方式获取同花顺数据
        from core.infrastructure.providers.implementations.akshare.ths_direct import (
            get_ths_provider,
        )

        provider = get_ths_provider()
        result = await provider.get_concept_list()
        if result["success"]:
            return {"data": result["data"], "_data_source": result["source"]}
        else:
            logger.error(f"获取失败: {result.get('error')}")
            # 尝试使用代理方式作为后备
            from core.infrastructure.providers.implementations.akshare.akshare import (
                AkShareProxyProvider,
            )

            proxy_provider = AkShareProxyProvider()
            return await proxy_provider.call_api("stock_board_concept_name_ths", {})
    except Exception as e:
        logger.error(f"获取同花顺概念板块列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/concept-ths/{concept}/index")
async def get_ths_concept_index(
    concept: str,
    start_date: str = Query("20240101", description="开始日期(YYYYMMDD)"),
    end_date: str = Query("20241231", description="结束日期(YYYYMMDD)"),
    service=Depends(get_market_service),
):
    """
    获取同花顺概念板块指数历史数据

    参数：
    - concept: 概念名称（如：阿里巴巴概念）
    - start_date: 开始日期
    - end_date: 结束日期
    """
    try:
        from core.infrastructure.providers.implementations.akshare.ths_direct import (
            get_ths_provider,
        )

        provider = get_ths_provider()
        result = await provider.get_concept_index(concept, start_date, end_date)
        if result["success"]:
            return {"data": result["data"], "_data_source": result["source"]}
        else:
            logger.error(f"获取失败: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to get data"))
    except Exception as e:
        logger.error(f"获取同花顺概念板块指数失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/concept-ths/{concept}/info")
async def get_ths_concept_info(concept: str, service=Depends(get_market_service)):
    """
    获取同花顺概念板块简介

    参数：
    - concept: 概念名称（如：阿里巴巴概念）
    """
    try:
        from core.infrastructure.providers.implementations.akshare.ths_direct import (
            get_ths_provider,
        )

        provider = get_ths_provider()
        result = await provider.get_concept_info(concept)
        if result["success"]:
            return {"data": result["data"], "_data_source": result["source"]}
        else:
            logger.error(f"获取失败: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to get data"))
    except Exception as e:
        logger.error(f"获取同花顺概念板块简介失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/concept-ths/{concept}/constituents")
async def get_ths_concept_constituents(concept: str, service=Depends(get_market_service)):
    """
    获取同花顺概念板块成份股

    参数：
    - concept: 概念名称（如：阿里巴巴概念）
    """
    try:
        from core.infrastructure.providers.implementations.akshare.ths_direct import (
            get_ths_provider,
        )

        provider = get_ths_provider()
        result = await provider.get_concept_constituents(concept)
        if result["success"]:
            return {"data": result["data"], "_data_source": result["source"]}
        else:
            logger.error(f"获取失败: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to get data"))
    except Exception as e:
        logger.error(f"获取同花顺概念板块成份股失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomalies", response_model=List[AnomalyResponse])
async def get_anomalies(
    kind: str = Query(
        "all", description="异动类型: all / limit_up / limit_down / price_surge / volume_spike"
    ),
    min_change: float = Query(0, description="最小涨跌幅过滤（%）"),
    min_amount: float = Query(0, description="最小成交额过滤（元）"),
    service=Depends(get_market_service),
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
        data = await service.get_anomalies(kind=kind, min_change=min_change, min_amount=min_amount)
        return data
    except Exception as e:
        logger.error(f"获取异动数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{symbol}/intraday")
async def get_stock_intraday(
    symbol: str,
    period: int = Query(1, description="时间周期（分钟）", ge=1, le=60),
    limit: int = Query(240, description="数据点数量", ge=1, le=1000),
    service=Depends(get_market_service),
):
    """
    获取个股分时数据

    参数：
    - symbol: 股票代码（如：000001）
    - period: 时间周期（1=1分钟线, 5=5分钟线, 等）
    - limit: 返回的数据点数量
    """
    try:
        data = await service.get_stock_intraday(symbol=symbol, period=period, limit=limit)
        return {"symbol": symbol, "period": period, "data": data}
    except Exception as e:
        logger.error(f"获取分时数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data-source", response_model=DataSourceStatus)
async def get_data_source_status(service=Depends(get_market_service)):
    """
    获取当前数据源状态

    返回：
    - 当前数据源类型（Workers代理/直连/缓存）
    - Worker节点信息（如果使用代理）
    - 健康状态和性能统计
    """
    import time

    # 检查缓存
    current_time = time.time()
    if (
        _data_source_status_cache["data"]
        and (current_time - _data_source_status_cache["timestamp"])
        < _data_source_status_cache["ttl"]
    ):
        logger.debug("使用缓存的数据源状态")
        return _data_source_status_cache["data"]

    # 简化处理 - 直接返回默认状态，避免超时
    # 因为当前service可能没有初始化或者provider为空
    default_status = DataSourceStatus(
        source="direct:akshare",
        mode="direct",
        worker_url="",
        healthy=True,
        latency=0,
        statistics={"note": "Using default status to avoid timeout"},
    )

    # 缓存默认结果
    _data_source_status_cache["data"] = default_status
    _data_source_status_cache["timestamp"] = current_time

    return default_status


@router.get("/stats")
async def get_market_stats(service=Depends(get_market_service)):
    """
    获取市场服务统计信息

    包括：
    - 总请求数
    - 缓存命中率
    - API错误数
    - 最后更新时间
    """
    try:
        stats = service.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activity", response_model=MarketActivityResponse)
async def get_market_activity(service=Depends(get_market_service)):
    """
    获取赚钱效应分析数据

    返回：
    - 涨跌家数统计
    - 涨停跌停统计
    - 市场活跃度
    - 涨跌比
    """
    try:
        # 检查service是否有get_market_activity方法
        if hasattr(service, "get_market_activity"):
            data = await service.get_market_activity()
        else:
            # 如果没有，尝试创建AkShareDirectService
            # from core.application.services.market.akshare_direct_service import AkShareDirectService
            # akshare_service = AkShareDirectService()
            # data = await akshare_service.get_market_activity()
            data = {"error": "Service not available"}

        return data
    except Exception as e:
        logger.error(f"获取赚钱效应数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock-changes", response_model=List[StockChangeItem])
async def get_stock_changes(
    change_type: str = Query("大笔买入", description="异动类型"),
    service=Depends(get_market_service),
):
    """
    获取盘口异动数据

    参数：
    - change_type: 异动类型，可选：
        - 买入信号：'火箭发射', '快速反弹', '大笔买入', '封涨停板', '打开跌停板', '有大买盘', '竞价上涨', '高开5日线', '向上缺口', '60日新高', '60日大幅上涨'
        - 卖出信号：'加速下跌', '高台跳水', '大笔卖出', '封跌停板', '打开涨停板', '有大卖盘', '竞价下跌', '低开5日线', '向下缺口', '60日新低', '60日大幅下跌'
    """
    try:
        # 检查service是否有get_stock_changes方法
        if hasattr(service, "get_stock_changes"):
            data = await service.get_stock_changes(change_type)
        else:
            # 如果没有，尝试创建AkShareDirectService
            # from core.application.services.market.akshare_direct_service import AkShareDirectService
            # akshare_service = AkShareDirectService()
            # data = await akshare_service.get_stock_changes(change_type)
            data = {"error": "Service not available"}

        return data
    except Exception as e:
        logger.error(f"获取盘口异动数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/zt-pool", response_model=List[ZTPoolItem])
async def get_zt_pool(
    date: Optional[str] = Query(None, description="日期，格式：20241231"),
    service=Depends(get_market_service),
):
    """
    获取涨停股池数据

    参数：
    - date: 日期，格式为 YYYYMMDD，默认为今天
    """
    try:
        # 检查service是否有get_zt_pool方法
        if hasattr(service, "get_zt_pool"):
            data = await service.get_zt_pool(date)
        else:
            # 如果没有，尝试创建AkShareDirectService
            # from core.application.services.market.akshare_direct_service import AkShareDirectService
            # akshare_service = AkShareDirectService()
            # data = await akshare_service.get_zt_pool(date)
            data = {"error": "Service not available"}

        return data
    except Exception as e:
        logger.error(f"获取涨停股池失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_market_data(
    category: str = Query(
        "all", description="刷新类别: all / overview / sectors / anomalies / activity"
    ),
    service=Depends(get_market_service),
):
    """
    强制刷新市场数据（清除缓存）

    参数：
    - category: 要刷新的数据类别
    """
    try:

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


@router.get("/top-gainers")
async def get_top_gainers(
    limit: int = Query(10, ge=1, le=100), service=Depends(get_market_service)
):
    """涨幅榜（前N名）"""
    try:
        result = await service.get_top_gainers(limit=limit)
        return result or []
    except Exception as e:
        logger.error(f"获取涨幅榜失败: {e}")
        # 在依赖不可用或实现缺失时，返回空列表以保持端点稳定性
        return []


@router.get("/top-losers")
async def get_top_losers(limit: int = Query(10, ge=1, le=100), service=Depends(get_market_service)):
    """跌幅榜（前N名）"""
    try:
        result = await service.get_top_losers(limit=limit)
        return result or []
    except Exception as e:
        logger.error(f"获取跌幅榜失败: {e}")
        # 在依赖不可用或实现缺失时，返回空列表以保持端点稳定性
        return []


# 概念板块资金流速缓存和单例 provider
_concept_velocity_cache: dict = {"data": None, "timestamp": 0}
_CACHE_TTL = 60  # 缓存60秒
_akshare_provider = None


async def _get_akshare_provider():
    """获取共享的 AKShare provider 实例"""
    global _akshare_provider
    if _akshare_provider is None:
        from core.infrastructure.providers.implementations.akshare.akshare_direct import (
            AKShareDirectProvider,
        )

        _akshare_provider = AKShareDirectProvider()
        await _akshare_provider.initialize()
    return _akshare_provider


@router.get("/concept-velocity", summary="获取板块资金流速排行")
async def get_concept_velocity(
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
):
    """
    获取实时计算的板块资金流向速度排行榜 (Sector Velocity)
    用于ConceptMonitor页面
    """
    import asyncio
    import time

    # 检查缓存
    current_time = time.time()
    if (
        _concept_velocity_cache["data"]
        and (current_time - _concept_velocity_cache["timestamp"]) < _CACHE_TTL
    ):
        cached_data = _concept_velocity_cache["data"][:limit]
        return {"success": True, "data": cached_data, "cached": True}

    try:
        provider = await _get_akshare_provider()

        # 使用更快的 get_concept_sectors API，添加超时控制
        try:
            data = await asyncio.wait_for(provider.get_concept_sectors(), timeout=10.0)  # 10秒超时
        except asyncio.TimeoutError:
            logger.warning("获取概念板块列表超时")
            # 如果有缓存数据，返回缓存
            if _concept_velocity_cache["data"]:
                return {
                    "success": True,
                    "data": _concept_velocity_cache["data"][:limit],
                    "cached": True,
                }
            return {"success": False, "error": "请求超时，请稍后重试"}

        if data:
            # 转换为前端期望的格式
            result = [
                {
                    "concept_code": item.get("code", str(i)),
                    "name": item.get("name", ""),
                    "velocity": item.get("change_pct", 0),  # 用涨跌幅作为"velocity"指标
                    "lead_stock": item.get("leading_stock", ""),
                    "lead_change": (
                        item.get("leading_stock_change_pct", 0) / 100
                        if item.get("leading_stock_change_pct")
                        else 0
                    ),
                }
                for i, item in enumerate(data[:200])  # 最多缓存200条
            ]
            # 更新缓存
            _concept_velocity_cache["data"] = result
            _concept_velocity_cache["timestamp"] = current_time
            return {"success": True, "data": result[:limit]}

        return {"success": False, "error": "无数据"}

    except Exception as e:
        logger.error(f"获取概念板块资金流速失败: {e}")
        # 如果有缓存数据，返回缓存
        if _concept_velocity_cache["data"]:
            return {
                "success": True,
                "data": _concept_velocity_cache["data"][:limit],
                "cached": True,
            }
        return {"success": False, "error": str(e)}
