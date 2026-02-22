"""
AmazingData 概念资金流向API

使用延迟导入避免模块加载时的依赖问题
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
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
        from core.domain.concept_engine import ConceptLinkageEngine, get_concept_engine

        from apps.api.api.endpoints.amazingdata.base import get_amazingdata_provider

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

            data = await asyncio.wait_for(fetch_from_engine(), timeout=180.0)
            if data:
                return format_response(success=True, data=data[:limit])
        except asyncio.TimeoutError:
            logger.error("ConceptLinkageEngine 获取数据超时(180s)")
            raise HTTPException(
                status_code=503,
                detail="数据服务暂时不可用，请稍后重试或先调用 /init 初始化",
            )
        except Exception as e:
            logger.error(f"ConceptLinkageEngine 获取数据失败: {e}")
            raise HTTPException(status_code=503, detail=f"数据获取失败: {e}")

    # 备用方案：使用AkShare获取板块资金流向数据 (带超时)
    try:

        async def fetch_from_akshare():
            from core.infrastructure.providers.implementations.akshare.akshare_direct import (
                AKShareDirectProvider,
            )

            provider = AKShareDirectProvider()
            await provider.initialize()
            return await provider.get_sector_capital_flow_rank(
                indicator="今日",
                sector_type="概念资金流",
            )

        data = await asyncio.wait_for(fetch_from_akshare(), timeout=30.0)

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
        raise HTTPException(status_code=503, detail="AKShare 返回空结果")
    except asyncio.TimeoutError:
        logger.error("AKShare 获取数据超时(30s)")
        raise HTTPException(
            status_code=503,
            detail="AKShare 数据服务暂时不可用，请稍后重试",
        )
    except Exception as e:
        logger.error(f"获取概念板块资金流速失败: {e}")
        raise HTTPException(status_code=503, detail=f"数据获取失败: {e}")


@router.get("/linkage", summary="获取个股-概念联动图谱")
async def get_concept_linkage(
    stock_code: str = Query(..., description="个股代码"),
) -> Dict[str, Any]:
    """
    根据个股代码，反向查询所属概念及同概念下的关联个股
    用于构建 'Spiderweb' 蛛网图
    """
    import asyncio

    ConceptLinkageEngine, get_concept_engine, get_amazingdata_provider = _get_engine_lazy()

    if ConceptLinkageEngine is None or get_concept_engine is None:
        raise HTTPException(status_code=503, detail="ConceptLinkageEngine 不可用")

    try:

        async def fetch_linkage():
            provider = await get_amazingdata_provider()
            engine = get_concept_engine(provider)
            if not engine._initialized:
                await engine.initialize_graph()
            return engine.get_linkage(stock_code)

        data = await asyncio.wait_for(fetch_linkage(), timeout=180.0)
        if data and data.get("concepts"):
            return format_response(success=True, data=data)

        raise HTTPException(
            status_code=404,
            detail=f"未找到股票 {stock_code} 的概念联动数据",
        )
    except asyncio.TimeoutError:
        logger.error(f"获取联动图谱超时(180s)，stock_code={stock_code}")
        raise HTTPException(
            status_code=503,
            detail="数据服务暂时不可用，请稍后重试或先调用 /init 初始化",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取联动图谱失败: {e}")
        raise HTTPException(status_code=503, detail=f"数据获取失败: {e}")


@router.post("/init", summary="初始化概念图谱")
async def init_concept_graph() -> Dict[str, Any]:
    """
    预初始化概念图谱，建议在系统启动后调用一次。
    首次初始化可能需要 2-3 分钟（包含 SDK 登录）。
    """
    import asyncio

    ConceptLinkageEngine, get_concept_engine, get_amazingdata_provider = _get_engine_lazy()

    if ConceptLinkageEngine is None or get_concept_engine is None:
        raise HTTPException(status_code=503, detail="ConceptLinkageEngine 不可用")

    try:
        provider = await get_amazingdata_provider()
        engine = get_concept_engine(provider)
        await asyncio.wait_for(engine.initialize_graph(), timeout=300.0)
        return format_response(success=True, data="图谱初始化完成")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="初始化超时(5分钟)，请检查网络连接")
    except Exception as e:
        logger.error(f"概念图谱初始化失败: {e}")
        raise HTTPException(status_code=503, detail=f"初始化失败: {e}")
