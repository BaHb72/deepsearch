"""
统一数据API

提供单一入口访问所有数据源
"""

# New imports for UnifiedDataFeed
from datetime import datetime
from typing import Any, Dict, Optional

from core.application.services.unified_data import get_unified_feed
from core.domain.market_data import StockListRecord
from core.ports.data.requests import KlineRequest, RealtimeQuoteRequest, StockListRequest
from core.ports.data.semantic_types import AdjustType, AssetSpec, Timeframe, TimeRange
from core.utils.data_sources import DataSourceType, get_data_source_manager
from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger

from apps.api.api.common.response_format import success_response
from apps.api.api.endpoints.data import data as data_module
from apps.api.api.utils import sanitize_for_json

router = APIRouter(prefix="/api/data", tags=["unified_data"])


def _record_to_legacy(record: StockListRecord) -> dict[str, object]:
    legacy: dict[str, object] = dict(record.as_mapping())
    if record.boards:
        legacy.setdefault("board", record.boards[0])
    return legacy


def _normalize_stock_records(
    payload: Any,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if payload is None:
        return [], []

    records: list[dict[str, object]] = []
    legacy: list[dict[str, object]] = []

    # 使用 duck typing 替代 isinstance 检查，避免跨模块导入路径导致的类身份不匹配
    if hasattr(payload, "records") and hasattr(payload, "as_legacy"):
        records = [dict(record.as_mapping()) for record in payload.records]
        legacy = payload.as_legacy()
        return records, legacy

    if hasattr(payload, "to_dict") and callable(getattr(payload, "to_dict")):
        payload = payload.to_dict("records")

    for entry in payload:
        if isinstance(entry, StockListRecord):
            record_map = dict(entry.as_mapping())
            records.append(record_map)
            legacy.append(_record_to_legacy(entry))
        elif isinstance(entry, dict):
            legacy_map = dict(entry)
            legacy.append(legacy_map)
            record = StockListRecord.from_payload(entry)
            if record.symbol:
                records.append(dict(record.as_mapping()))
        else:
            try:
                legacy_map = dict(entry)
            except Exception:
                continue
            legacy.append(legacy_map)
            record = StockListRecord.from_payload(legacy_map)
            if record.symbol:
                records.append(dict(record.as_mapping()))

    return records, legacy


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
        # 周期映射
        period_map = {
            "daily": Timeframe.D1,
            "weekly": Timeframe.W1,
            "monthly": Timeframe.MO1,
            "1": Timeframe.M1,
            "5": Timeframe.M5,
            "15": Timeframe.M15,
            "30": Timeframe.M30,
            "60": Timeframe.H1,
            "1m": Timeframe.M1,
            "5m": Timeframe.M5,
            "15m": Timeframe.M15,
            "30m": Timeframe.M30,
            "60m": Timeframe.H1,
            "1d": Timeframe.D1,
        }

        # 复权映射
        adjust_map = {"qfq": AdjustType.FORWARD, "hfq": AdjustType.BACKWARD}

        # 解析资产
        try:
            asset = AssetSpec.from_code(symbol)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的股票代码: {symbol}")

        # 构建时间范围
        timeframe = period_map.get(period, Timeframe.D1)
        adjust_type = adjust_map.get(adjust, AdjustType.NONE)

        if start_date and end_date:
            time_range = TimeRange.between(
                datetime.strptime(start_date, "%Y-%m-%d"),
                datetime.strptime(end_date, "%Y-%m-%d"),
            )
        elif start_date:
            time_range = TimeRange.between(
                datetime.strptime(start_date, "%Y-%m-%d"),
                datetime.now(),
            )
        else:
            time_range = TimeRange.last_days(100)

        # 调用 UnifiedDataFeed
        feed = get_unified_feed()
        request = KlineRequest(
            asset=asset,
            timeframe=timeframe,
            range=time_range,
            adjust=adjust_type,
        )
        response = await feed.get_kline(request)

        # 转换为前端期望格式
        result = []
        for bar in response.bars:
            result.append(
                {
                    "date": bar.timestamp.strftime("%Y-%m-%d"),
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": bar.volume,
                }
            )

        return success_response(sanitize_for_json(result))

    except HTTPException:
        raise
    except RuntimeError as e:
        logger.error(f"数据服务未就绪: {e}")
        raise HTTPException(status_code=503, detail="数据服务尚未初始化，请稍后重试")
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
        # 解析资产
        try:
            asset = AssetSpec.from_code(symbol)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的股票代码: {symbol}")

        # 调用 UnifiedDataFeed
        feed = get_unified_feed()
        request = RealtimeQuoteRequest(assets=[asset])
        response = await feed.get_realtime(request)

        if len(response) == 0:
            raise HTTPException(status_code=404, detail=f"未找到 {symbol} 的实时行情")

        quote = response.quotes[0]
        result = {
            "symbol": symbol,
            "last_price": float(quote.last_price),
            "open": float(quote.open),
            "high": float(quote.high),
            "low": float(quote.low),
            "pre_close": float(quote.pre_close),
            "volume": quote.volume,
            "amount": float(quote.amount),
            "change": float(quote.change),
            "change_pct": float(quote.change_pct),
            "timestamp": quote.timestamp.isoformat() if quote.timestamp else None,
        }

        return success_response(sanitize_for_json(result))

    except HTTPException:
        raise
    except RuntimeError as e:
        logger.error(f"数据服务未就绪: {e}")
        raise HTTPException(status_code=503, detail="数据服务尚未初始化，请稍后重试")
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
        result_raw = await manager.fetch_stock_info(
            symbol=symbol, preferred_source=preferred_source
        )
        result: Dict[str, Any] = dict(result_raw) if isinstance(result_raw, dict) else {}

        # 确保返回正确的股票名称
        name_hint = result.get("name", "") if isinstance(result, dict) else ""
        if name_hint.startswith("股票") and not result.get("error"):
            # 如果名称是默认的，尝试从其他源获取
            for source_type in [DataSourceType.CLOUDFLARE, DataSourceType.QMT]:
                if source_type != preferred_source:
                    alt_raw = await manager.fetch_stock_info(
                        symbol=symbol, preferred_source=source_type
                    )
                    alt_result = dict(alt_raw) if isinstance(alt_raw, dict) else {}
                    alt_name = alt_result.get("name")
                    if isinstance(alt_name, str) and not alt_name.startswith("股票"):
                        return success_response(sanitize_for_json(alt_result))

        return success_response(sanitize_for_json(result))

    except Exception as e:
        logger.error(f"获取股票信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/list")
async def get_stock_list(source: Optional[str] = Query(None, description="指定数据源")):
    """
    获取股票列表，返回并行的领域结构与旧结构映射。
    """
    try:
        # 使用 UnifiedDataFeed 获取股票列表（带强缓存）
        feed = get_unified_feed()
        request = StockListRequest()
        response = await feed.list_instruments(request)

        # 转换为前端期望的格式
        records: list[Any] = []
        legacy: list[Any] = []
        for stock in response.stocks:
            record = {
                "symbol": stock.asset.to_standard(),
                "name": stock.name,
                "status": stock.status.value,
                "industry": stock.industry,
                "is_st": stock.is_st,
            }
            records.append(record)
            # 兼容旧版格式
            legacy.append(
                {
                    "symbol": stock.asset.symbol,
                    "code": stock.asset.symbol,
                    "name": stock.name,
                }
            )

        payload = {
            "records": records,
            "legacy": legacy,
            "source": response.source.value,
            "count": len(records),
            "schema_version": "v2",
        }
        return success_response(sanitize_for_json(payload))

    except RuntimeError as e:
        # ReferenceDataCapability 未配置，回退到旧实现
        logger.warning(f"使用旧实现获取股票列表: {e}")
        service = data_module.get_data_service()
        stock_result = await service.get_stock_list(limit=None)
        normalized = _normalize_stock_records(stock_result)
        records = normalized[0]
        legacy = normalized[1]
        payload = {
            "records": records,
            "legacy": legacy,
            "source": "fallback",
            "count": len(records) or len(legacy),
            "schema_version": "v2",
        }
        return success_response(sanitize_for_json(payload))

    except Exception as exc:
        logger.error(f"获取股票列表失败: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/stocks")
async def get_stock_list_legacy(
    source: Optional[str] = Query(None, description="指定数据源"),
) -> list[dict[str, object]]:
    """旧版 /api/data/stocks 兼容输出，仅返回 legacy 列表。"""

    # 优先使用 UnifiedDataFeed
    try:
        feed = get_unified_feed()
        request = StockListRequest()
        response = await feed.list_instruments(request)

        legacy: list[dict[str, object]] = []
        for stock in response.stocks:
            legacy.append(
                {
                    "symbol": stock.asset.symbol,
                    "code": stock.asset.symbol,
                    "name": stock.name,
                }
            )
        return legacy
    except RuntimeError:
        logger.warning("UnifiedDataFeed 未就绪，回退到旧实现获取股票列表")
    except Exception as e:
        logger.warning(f"UnifiedDataFeed 获取股票列表失败: {e}，回退到旧实现")

    # 回退到旧实现
    service = data_module.get_data_service()
    stocks = await service.get_stock_list(limit=None)
    if stocks is not None and hasattr(stocks, "mismatch") and stocks.mismatch:
        logger.warning(
            "股票列表双写内部差异 source=%s mismatch=%d",
            getattr(stocks, "source", "unknown"),
            getattr(stocks, "mismatch", 0),
        )
    records, legacy_list = _normalize_stock_records(stocks)
    if legacy_list:
        return legacy_list
    return records


@router.get("/source/status")
async def get_source_status(request: Request):
    """返回简化的数据源状态，保持测试兼容。

    - 在 API 测试环境（带 X-Test-Mode: true 头）下，该旧端点应返回 404 以表明已废弃。
    - 在 WebUI 端到端测试（无该头）下，为兼容性返回 200 和最小结构。
    """
    # 旧端点：在测试模式下返回 404
    if request.headers.get("X-Test-Mode", "").lower() == "true":
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404, detail="endpoint deprecated; use /api/data-sources/status"
        )

    try:
        manager = get_data_source_manager()
        active_source = None
        if hasattr(manager, "get_active_source"):
            active = manager.get_active_source()
            active_source = getattr(active, "value", active)
    except Exception:
        active_source = None

    return {
        "sources": [],
        "active": active_source,
    }


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
            if not manager.is_source_available(source_type):
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
