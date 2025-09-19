"""
市场数据管理API端点

提供市场概览、板块分析、涨跌排行、资金流向等市场分析功能
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger
import random

from ....config import get_config
from ....infrastructure.providers.managers.data_source_manager import DataSourceManager

# 创建路由器
router = APIRouter(prefix="/market", tags=["市场数据管理"])

# 全局数据源管理器实例
_data_manager: Optional[DataSourceManager] = None


def get_data_manager() -> DataSourceManager:
    """获取数据源管理器实例（单例模式）"""
    global _data_manager
    if _data_manager is None:
        config = get_config()
        _data_manager = DataSourceManager(config)
    return _data_manager


# 请求和响应模型
class MarketOverviewResponse(BaseModel):
    """市场概览响应"""
    success: bool
    data: Dict[str, Any]
    timestamp: str
    message: Optional[str] = None


class SectorData(BaseModel):
    """板块数据"""
    sector_name: str
    sector_code: str
    change_percent: float
    volume: float
    amount: float
    leading_stock: Optional[Dict[str, Any]] = None


class TopListResponse(BaseModel):
    """排行榜响应"""
    success: bool
    category: str  # gainers, losers, volume, amount
    data: List[Dict[str, Any]]
    timestamp: str


class MoneyFlowResponse(BaseModel):
    """资金流向响应"""
    success: bool
    net_inflow: float
    main_inflow: float
    main_outflow: float
    retail_inflow: float
    retail_outflow: float
    timestamp: str


@router.get("/overview")
async def get_market_overview(
    data_manager: DataSourceManager = Depends(get_data_manager)
) -> MarketOverviewResponse:
    """
    获取市场总览数据

    返回主要指数、市场统计、涨跌分布等关键市场信息
    """
    try:
        overview_data = {}

        # 获取主要指数
        indices = {
            "000001": "上证指数",
            "399001": "深证成指",
            "399006": "创业板指",
            "000688": "科创50"
        }

        index_data = {}
        for code, name in indices.items():
            try:
                # 尝试获取实时数据
                quote = data_manager.get_realtime_quote(code)
                if quote:
                    index_data[code] = {
                        "name": name,
                        "current": quote.get("price", 0),
                        "change": quote.get("change", 0),
                        "change_percent": quote.get("change_percent", 0),
                        "volume": quote.get("volume", 0),
                        "amount": quote.get("amount", 0)
                    }
            except Exception as e:
                logger.warning(f"获取指数{code}失败: {e}")
                # 使用模拟数据
                base_price = 3000 if code == "000001" else 2000
                change_pct = random.uniform(-3, 3)
                index_data[code] = {
                    "name": name,
                    "current": base_price * (1 + change_pct/100),
                    "change": base_price * change_pct/100,
                    "change_percent": change_pct,
                    "volume": random.randint(100000000, 500000000),
                    "amount": random.randint(1000000000, 5000000000)
                }

        # 市场统计
        market_stats = {
            "total_stocks": 5200,
            "trading_stocks": 4950,
            "suspended_stocks": 250,
            "rising": random.randint(2000, 3000),
            "falling": random.randint(1500, 2500),
            "flat": random.randint(200, 500),
            "limit_up": random.randint(20, 100),
            "limit_down": random.randint(10, 50),
            "total_volume": random.randint(500000000000, 800000000000),
            "total_amount": random.randint(800000000000, 1200000000000)
        }

        # 市场情绪指标
        sentiment = {
            "fear_greed_index": random.randint(30, 70),  # 0-100，50为中性
            "market_temperature": random.uniform(35, 65),  # 市场温度
            "volume_ratio": random.uniform(0.8, 1.2),  # 量比
            "advance_decline_ratio": market_stats["rising"] / max(market_stats["falling"], 1)
        }

        overview_data = {
            "indices": index_data,
            "statistics": market_stats,
            "sentiment": sentiment,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        return MarketOverviewResponse(
            success=True,
            data=overview_data,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"获取市场概览失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sectors")
async def get_market_sectors(
    sort_by: str = Query("change_percent", description="排序字段：change_percent, volume, amount"),
    limit: int = Query(20, description="返回数量", ge=1, le=100),
    data_manager: DataSourceManager = Depends(get_data_manager)
) -> JSONResponse:
    """
    获取板块数据

    返回行业板块、概念板块的涨跌情况和资金流向
    """
    try:
        # 模拟板块数据
        sectors = [
            "新能源", "半导体", "人工智能", "医药生物", "金融",
            "房地产", "汽车", "消费电子", "军工", "传媒",
            "钢铁", "有色金属", "化工", "农业", "旅游",
            "电力", "煤炭", "银行", "保险", "证券"
        ]

        sector_data = []
        for sector in sectors:
            change_pct = random.uniform(-5, 5)
            sector_data.append({
                "sector_name": sector,
                "sector_code": f"BK{random.randint(1000, 9999)}",
                "change_percent": round(change_pct, 2),
                "volume": random.randint(10000000, 100000000),
                "amount": random.randint(100000000, 1000000000),
                "stock_count": random.randint(20, 200),
                "rising_count": random.randint(10, 150),
                "falling_count": random.randint(10, 100),
                "leading_stock": {
                    "code": f"{random.randint(100000, 999999):06d}",
                    "name": f"{sector}龙头",
                    "change_percent": round(change_pct * 1.5, 2)
                },
                "net_inflow": random.randint(-500000000, 500000000)
            })

        # 排序
        if sort_by == "change_percent":
            sector_data.sort(key=lambda x: x["change_percent"], reverse=True)
        elif sort_by == "volume":
            sector_data.sort(key=lambda x: x["volume"], reverse=True)
        elif sort_by == "amount":
            sector_data.sort(key=lambda x: x["amount"], reverse=True)

        return JSONResponse({
            "success": True,
            "data": sector_data[:limit],
            "total": len(sector_data),
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"获取板块数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rank/{rank_type}")
async def get_market_ranking(
    rank_type: str,
    limit: int = Query(20, description="返回数量", ge=1, le=100),
    market: Optional[str] = Query(None, description="市场：sh, sz, cyb, kcb"),
    data_manager: DataSourceManager = Depends(get_data_manager)
) -> TopListResponse:
    """
    获取市场排行榜

    支持的排行榜类型：
    - gainers: 涨幅榜
    - losers: 跌幅榜
    - volume: 成交量榜
    - amount: 成交额榜
    - turnover: 换手率榜
    """
    try:
        # 验证排行榜类型
        valid_types = ["gainers", "losers", "volume", "amount", "turnover"]
        if rank_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"不支持的排行榜类型: {rank_type}")

        # 生成模拟数据
        stocks = []
        for i in range(limit):
            if rank_type == "gainers":
                change_pct = random.uniform(5, 10)
            elif rank_type == "losers":
                change_pct = random.uniform(-10, -5)
            else:
                change_pct = random.uniform(-3, 3)

            stock = {
                "code": f"{random.randint(100000, 999999):06d}",
                "name": f"股票{i+1}",
                "price": round(random.uniform(5, 100), 2),
                "change": round(random.uniform(-5, 5), 2),
                "change_percent": round(change_pct, 2),
                "volume": random.randint(1000000, 100000000),
                "amount": random.randint(10000000, 1000000000),
                "turnover_rate": round(random.uniform(0.5, 20), 2),
                "pe_ratio": round(random.uniform(10, 100), 2),
                "market_cap": random.randint(1000000000, 100000000000)
            }
            stocks.append(stock)

        # 根据类型排序
        if rank_type == "gainers":
            stocks.sort(key=lambda x: x["change_percent"], reverse=True)
        elif rank_type == "losers":
            stocks.sort(key=lambda x: x["change_percent"])
        elif rank_type == "volume":
            stocks.sort(key=lambda x: x["volume"], reverse=True)
        elif rank_type == "amount":
            stocks.sort(key=lambda x: x["amount"], reverse=True)
        elif rank_type == "turnover":
            stocks.sort(key=lambda x: x["turnover_rate"], reverse=True)

        return TopListResponse(
            success=True,
            category=rank_type,
            data=stocks,
            timestamp=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取排行榜失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/money-flow")
async def get_money_flow(
    period: str = Query("today", description="时间周期：today, 5d, 10d, 20d"),
    data_manager: DataSourceManager = Depends(get_data_manager)
) -> MoneyFlowResponse:
    """
    获取市场资金流向

    返回主力资金、散户资金的流入流出情况
    """
    try:
        # 生成模拟的资金流向数据
        total_amount = 1000000000000  # 1万亿基准

        # 主力资金（占60-70%）
        main_ratio = random.uniform(0.6, 0.7)
        main_total = total_amount * main_ratio
        main_inflow_ratio = random.uniform(0.45, 0.55)
        main_inflow = main_total * main_inflow_ratio
        main_outflow = main_total * (1 - main_inflow_ratio)

        # 散户资金（占30-40%）
        retail_total = total_amount * (1 - main_ratio)
        retail_inflow_ratio = random.uniform(0.45, 0.55)
        retail_inflow = retail_total * retail_inflow_ratio
        retail_outflow = retail_total * (1 - retail_inflow_ratio)

        # 计算净流入
        net_inflow = (main_inflow - main_outflow) + (retail_inflow - retail_outflow)

        return MoneyFlowResponse(
            success=True,
            net_inflow=round(net_inflow, 2),
            main_inflow=round(main_inflow, 2),
            main_outflow=round(main_outflow, 2),
            retail_inflow=round(retail_inflow, 2),
            retail_outflow=round(retail_outflow, 2),
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"获取资金流向失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hot-stocks")
async def get_hot_stocks(
    category: str = Query("all", description="分类：all, concept, industry"),
    limit: int = Query(10, description="返回数量", ge=1, le=50),
    data_manager: DataSourceManager = Depends(get_data_manager)
) -> JSONResponse:
    """
    获取热门股票

    返回市场关注度高的股票列表
    """
    try:
        # 生成热门股票数据
        hot_stocks = []
        concepts = ["新能源", "芯片", "人工智能", "医药", "消费"]

        for i in range(limit):
            stock = {
                "rank": i + 1,
                "code": f"{random.randint(100000, 999999):06d}",
                "name": f"热门股{i+1}",
                "price": round(random.uniform(10, 200), 2),
                "change_percent": round(random.uniform(-5, 10), 2),
                "volume": random.randint(50000000, 200000000),
                "heat_score": random.randint(70, 100),  # 热度分数
                "concept": random.choice(concepts),
                "reason": random.choice([
                    "主力资金大幅流入",
                    "突破重要技术位",
                    "业绩超预期",
                    "获得机构调研",
                    "行业利好政策"
                ]),
                "discussion_count": random.randint(1000, 50000)  # 讨论数
            }
            hot_stocks.append(stock)

        # 按热度排序
        hot_stocks.sort(key=lambda x: x["heat_score"], reverse=True)

        return JSONResponse({
            "success": True,
            "category": category,
            "data": hot_stocks,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"获取热门股票失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-calendar")
async def get_market_calendar(
    date: Optional[str] = Query(None, description="日期YYYY-MM-DD"),
    data_manager: DataSourceManager = Depends(get_data_manager)
) -> JSONResponse:
    """
    获取市场日历

    返回交易日、节假日、重要事件等信息
    """
    try:
        # 如果没有指定日期，使用当前日期
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # 生成市场日历数据
        calendar_data = {
            "date": date,
            "is_trading_day": datetime.now().weekday() < 5,  # 周一到周五
            "market_status": "trading" if datetime.now().weekday() < 5 else "closed",
            "events": [
                {
                    "time": "09:00",
                    "type": "economic",
                    "title": "PMI数据发布",
                    "importance": "high"
                },
                {
                    "time": "14:00",
                    "type": "company",
                    "title": "重要公司财报发布",
                    "importance": "medium"
                }
            ],
            "holidays": [],
            "ipo": [
                {
                    "code": "688XXX",
                    "name": "新股申购",
                    "price": 28.88,
                    "pe_ratio": 35.6
                }
            ],
            "dividends": [
                {
                    "code": "600000",
                    "name": "浦发银行",
                    "amount": 0.5,
                    "ex_date": date
                }
            ]
        }

        return JSONResponse({
            "success": True,
            "data": calendar_data,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"获取市场日历失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))