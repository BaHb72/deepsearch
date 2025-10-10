"""
统一数据API

提供单一入口访问所有数据源
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from deepsearch.utils.data_sources import DataSourceType, get_data_source_manager
from deepsearch.webui.api.common.response_format import success_response
from deepsearch.webui.api.utils import sanitize_for_json

router = APIRouter(prefix="/api/data", tags=["unified_data"])


@router.get("/stock/hist")
async def get_stock_history(
    symbol: str = Query(..., description="股票代码"),
    period: str = Query("daily", description="周期：daily, weekly, monthly, 5, 15, 30, 60"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    adjust: str = Query("", description="复权类型：qfq前复权, hfq后复权"),
    source: Optional[str] = Query(None, description="指定数据源：qmt, cloudflare, direct_api"),
):
    """
    获取股票历史K线数据

    自动选择最优数据源，支持故障切换
    """
    try:
        # 解析数据源类型
        preferred_source = None
        if source:
            try:
                preferred_source = DataSourceType(source.lower())
            except ValueError:
                logger.warning(f"无效的数据源类型: {source}")

        # 获取管理器
        manager = get_data_source_manager()

        # 获取数据
        result = await manager.get_stock_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            preferred_source=preferred_source,
        )

        # 清理 NaN 值
        return success_response(sanitize_for_json(result))

    except Exception as e:
        logger.error(f"获取历史数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/quote")
async def get_stock_quote(
    symbol: str = Query(..., description="股票代码"),
    source: Optional[str] = Query(None, description="指定数据源"),
):
    """
    获取股票实时行情

    返回最新的价格、成交量等信息
    """
    try:
        preferred_source = None
        if source:
            try:
                preferred_source = DataSourceType(source.lower())
            except ValueError:
                pass

        manager = get_data_source_manager()
        result = await manager.get_realtime_quote(symbol=symbol, preferred_source=preferred_source)

        # 清理 NaN 值
        return success_response(sanitize_for_json(result))

    except Exception as e:
        logger.error(f"获取实时行情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/info")
async def get_stock_info(
    symbol: str = Query(..., description="股票代码"),
    source: Optional[str] = Query(None, description="指定数据源"),
):
    """
    获取股票基础信息

    包括股票名称、行业、市值等
    """
    try:
        preferred_source = None
        if source:
            try:
                preferred_source = DataSourceType(source.lower())
            except ValueError:
                pass

        manager = get_data_source_manager()
        result = await manager.fetch_stock_info(symbol=symbol, preferred_source=preferred_source)

        # 确保返回正确的股票名称
        if result.get("name", "").startswith("股票") and not result.get("error"):
            # 如果名称是默认的，尝试从其他源获取
            for source_type in [DataSourceType.CLOUDFLARE, DataSourceType.QMT]:
                if source_type != preferred_source:
                    alt_result = await manager.fetch_stock_info(
                        symbol=symbol, preferred_source=source_type
                    )
                    if alt_result.get("name") and not alt_result["name"].startswith("股票"):
                        return success_response(sanitize_for_json(alt_result))

        return success_response(sanitize_for_json(result))

    except Exception as e:
        logger.error(f"获取股票信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/list")
async def get_stock_list(source: Optional[str] = Query(None, description="指定数据源")):
    """
    获取股票列表

    返回所有可交易股票的代码和名称
    """
    try:
        manager = get_data_source_manager()

        # 优先从Cloudflare获取完整列表
        for source_type in [DataSourceType.CLOUDFLARE, DataSourceType.QMT]:
            provider = manager.providers.get(source_type)
            if provider and hasattr(provider, "fetch_stock_list"):
                try:
                    stocks = await provider.fetch_stock_list()
                    if stocks:
                        return success_response(
                            sanitize_for_json(
                                {"data": stocks, "source": source_type.value, "count": len(stocks)}
                            )
                        )
                except Exception as e:
                    logger.debug(f"{source_type.value} 获取股票列表失败: {e}")

        return success_response({"data": [], "source": "none", "error": "无法获取股票列表"})

    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/source/status")
async def get_source_status():
    """⚠️ 已废弃的旧数据源状态接口"""
    warning_message = (
        "接口 /api/data/source/status 已废弃，请改用 /api/data-sources/status。"
        "该接口将在后续版本移除。"
    )
    logger.warning("[DEPRECATED] %s", warning_message)
    raise HTTPException(
        status_code=404,
        detail={
            "message": warning_message,
            "replacement": "/api/data-sources/status",
        },
        headers={
            "X-Deprecated-Endpoint": "/api/data/source/status",
            "X-Replacement-Endpoint": "/api/data-sources/status",
        },
    )


@router.post("/source/check")
async def check_data_sources():
    """
    手动触发数据源健康检查

    检查所有数据源的可用性
    """
    try:
        manager = get_data_source_manager()
        await manager._check_all_sources()
        return {
            "code": 0,
            "data": {
                "status": "success",
                "message": "健康检查完成",
                "result": manager.get_status_report(),
            },
            "message": "success",
        }

    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare")
async def compare_data_sources(
    symbol: str = Query(..., description="股票代码"),
    data_type: str = Query("quote", description="数据类型：quote, info"),
):
    """
    比较不同数据源的数据

    用于验证数据一致性
    """
    try:
        manager = get_data_source_manager()
        results = {}

        for source_type in DataSourceType:
            if not manager.sources[source_type].available:
                continue

            try:
                if data_type == "quote":
                    result = await manager.get_realtime_quote(
                        symbol=symbol, preferred_source=source_type
                    )
                elif data_type == "info":
                    result = await manager.fetch_stock_info(
                        symbol=symbol, preferred_source=source_type
                    )
                else:
                    continue

                results[source_type.value] = result

            except Exception as e:
                results[source_type.value] = {"error": str(e)}

        return success_response(
            sanitize_for_json({"symbol": symbol, "data_type": data_type, "sources": results})
        )

    except Exception as e:
        logger.error(f"数据比较失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
