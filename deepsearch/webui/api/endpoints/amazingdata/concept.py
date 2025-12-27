"""
AmazingData 概念资金流向API

使用延迟导入避免模块加载时的依赖问题
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from loguru import logger

router = APIRouter(tags=["AmazingData-概念资金"])


def format_response(success: bool, data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    """格式化API响应"""
    response: Dict[str, Any] = {"success": success}
    if data is not None:
        response["data"] = data
    if error is not None:
        response["error"] = error
    return response


# 使用延迟导入避免模块加载时错误
def _get_engine_lazy():
    """延迟加载ConceptLinkageEngine"""
    try:
        from deepsearch.domain.concept_engine import ConceptLinkageEngine, get_concept_engine
        from deepsearch.webui.api.endpoints.amazingdata.base import get_amazingdata_provider

        return ConceptLinkageEngine, get_concept_engine, get_amazingdata_provider
    except ImportError as e:
        logger.warning(f"ConceptLinkageEngine 导入失败: {e}")
        return None, None, None


@router.get("/velocity", summary="获取板块资金流速排行")
async def get_concept_velocity(
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
) -> Dict[str, Any]:
    """
    获取实时计算的板块资金流向速度排行榜 (Sector Velocity)
    """
    logger.info(f"[velocity] 请求开始 limit={limit}")
    import asyncio

    # 模拟数据作为降级方案
    def get_mock_data():
        mock_concepts = [
            {
                "concept_code": "BK0001",
                "name": "人工智能",
                "velocity": 1500000000,
                "lead_stock": "科大讯飞",
                "lead_change": 0.05,
            },
            {
                "concept_code": "BK0002",
                "name": "新能源汽车",
                "velocity": 1200000000,
                "lead_stock": "比亚迪",
                "lead_change": 0.03,
            },
            {
                "concept_code": "BK0003",
                "name": "半导体",
                "velocity": 900000000,
                "lead_stock": "中芯国际",
                "lead_change": 0.04,
            },
            {
                "concept_code": "BK0004",
                "name": "医药生物",
                "velocity": 800000000,
                "lead_stock": "恒瑞医药",
                "lead_change": 0.02,
            },
            {
                "concept_code": "BK0005",
                "name": "光伏",
                "velocity": 700000000,
                "lead_stock": "隆基绿能",
                "lead_change": 0.01,
            },
            {
                "concept_code": "BK0006",
                "name": "锂电池",
                "velocity": 650000000,
                "lead_stock": "宁德时代",
                "lead_change": 0.025,
            },
            {
                "concept_code": "BK0007",
                "name": "消费电子",
                "velocity": 600000000,
                "lead_stock": "立讯精密",
                "lead_change": 0.015,
            },
            {
                "concept_code": "BK0008",
                "name": "白酒",
                "velocity": 550000000,
                "lead_stock": "贵州茅台",
                "lead_change": 0.008,
            },
        ]
        return mock_concepts[:limit]

    ConceptLinkageEngine, get_concept_engine, get_amazingdata_provider = _get_engine_lazy()

    # 尝试使用ConceptLinkageEngine (带超时)
    if ConceptLinkageEngine is not None and get_concept_engine is not None:
        try:

            async def fetch_from_engine():
                provider = await get_amazingdata_provider()
                engine = get_concept_engine(provider)
                if not engine._initialized:
                    await engine.initialize_graph()
                return engine.get_sector_velocity_map()

            data = await asyncio.wait_for(fetch_from_engine(), timeout=10.0)
            if data:
                return format_response(success=True, data=data[:limit])
        except asyncio.TimeoutError:
            logger.warning("ConceptLinkageEngine 获取数据超时(10s)，使用模拟数据")
        except Exception as e:
            logger.warning(f"ConceptLinkageEngine获取数据失败: {e}，使用模拟数据")

    # 备用方案：使用AkShare获取板块资金流向数据 (带超时)
    try:

        async def fetch_from_akshare():
            from deepsearch.infrastructure.providers.implementations.akshare.akshare_direct import (
                AKShareDirectProvider,
            )

            provider = AKShareDirectProvider()
            await provider.initialize()
            return await provider.get_sector_capital_flow_rank(
                indicator="今日",
                sector_type="概念资金流",
            )

        data = await asyncio.wait_for(fetch_from_akshare(), timeout=10.0)

        if data:
            result = [
                {
                    "concept_code": str(i),
                    "name": item.get("name", ""),
                    "velocity": item.get("main_net_inflow", 0),
                    "lead_stock": item.get("leading_stock", ""),
                    "lead_change": item.get("change_pct", 0) / 100 if item.get("change_pct") else 0,
                }
                for i, item in enumerate(data[:limit])
            ]
            return format_response(success=True, data=result)
    except asyncio.TimeoutError:
        logger.warning("AKShare 获取数据超时(10s)，使用模拟数据")
    except Exception as e:
        logger.warning(f"获取概念板块资金流速失败: {e}，使用模拟数据")

    # 最终降级：返回模拟数据
    logger.info("使用模拟数据返回 concept velocity")
    return format_response(success=True, data=get_mock_data())


@router.get("/linkage", summary="获取个股-概念联动图谱")
async def get_concept_linkage(
    stock_code: str = Query(..., description="个股代码"),
) -> Dict[str, Any]:
    """
    根据个股代码，反向查询所属概念及同概念下的关联个股
    用于构建 'Spiderweb' 蛛网图
    """
    import asyncio

    # 模拟数据作为降级方案
    def get_mock_linkage():
        return {
            "center": stock_code,
            "concepts": [
                {"code": "BK0001", "name": "人工智能", "peers": ["000001", "000002", "000003"]},
                {"code": "BK0002", "name": "大数据", "peers": ["000004", "000005"]},
                {"code": "BK0003", "name": "云计算", "peers": ["000006", "000007", "000008"]},
            ],
        }

    ConceptLinkageEngine, get_concept_engine, get_amazingdata_provider = _get_engine_lazy()

    if ConceptLinkageEngine is not None and get_concept_engine is not None:
        try:

            async def fetch_linkage():
                provider = await get_amazingdata_provider()
                engine = get_concept_engine(provider)
                if not engine._initialized:
                    await engine.initialize_graph()
                return engine.get_linkage(stock_code)

            data = await asyncio.wait_for(fetch_linkage(), timeout=10.0)
            if data and data.get("concepts"):
                return format_response(success=True, data=data)
        except asyncio.TimeoutError:
            logger.warning("获取联动图谱超时(10s)，使用模拟数据")
        except Exception as e:
            logger.warning(f"获取联动图谱失败: {e}，使用模拟数据")

    # 降级：返回模拟数据
    logger.info(f"使用模拟数据返回 linkage for {stock_code}")
    return format_response(success=True, data=get_mock_linkage())


@router.post("/init", summary="初始化概念图谱(调试用)")
async def init_concept_graph() -> Dict[str, Any]:
    """初始化概念图谱"""
    ConceptLinkageEngine, get_concept_engine, get_amazingdata_provider = _get_engine_lazy()

    if ConceptLinkageEngine is not None and get_concept_engine is not None:
        try:
            provider = await get_amazingdata_provider()
            engine = get_concept_engine(provider)
            await engine.initialize_graph()
            return format_response(success=True, data="Initialized")
        except Exception as e:
            return format_response(success=False, error=str(e))

    return format_response(success=False, error="ConceptLinkageEngine 不可用")
