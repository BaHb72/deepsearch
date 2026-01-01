"""
市场数据和股票信息API

提供全面的市场数据服务
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, Response
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from deepsearch.utils.data_sources import DataSourceManager, DataSourceType, get_data_source_manager

# New imports for UnifiedDataFeed
from deepsearch.application.services.unified_data import get_unified_feed
from deepsearch.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from deepsearch.ports.data.semantic_types import AssetSpec, Timeframe, AdjustType, TimeRange
from deepsearch.webui.api.common.response_format import (
    APIResponse,
    ErrorCodes,
    error_response,
    success_response,
)

router = APIRouter(prefix="/api/data", tags=["market_data"])


STUB_SOURCE_LABEL = "stub"


def _resolve_source_label(
    manager: DataSourceManager, source: Optional[DataSourceType], prefer_stub: bool = False
) -> str:
    """根据当前数据源状态推断响应头所需的来源标识。"""

    if isinstance(source, DataSourceType):
        return source.value

    available_sources = []
    try:
        available_sources = list(manager.get_available_sources())
    except Exception as lookup_error:  # pragma: no cover - 调试辅助
        logger.debug(f"获取可用数据源失败: {lookup_error}")

    for candidate in available_sources:
        if isinstance(candidate, DataSourceType):
            return candidate.value

    return STUB_SOURCE_LABEL if prefer_stub else "unknown"


def _build_stub_stock_info(symbol: str) -> Dict[str, Any]:
    base_symbol = symbol or "000001"
    return {
        "symbol": base_symbol,
        "name": f"演示{base_symbol}",
        "exchange": "SSE" if base_symbol.startswith("6") else "SZSE",
        "industry": "示例行业",
        "price": 10.5,
        "change": 0.12,
        "change_pct": 1.15,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def _build_stub_kline(symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
    base = datetime.utcnow()
    rows: List[Dict[str, Any]] = []
    for idx in range(limit):
        day = (base - timedelta(days=idx)).date()
        rows.append(
            {
                "date": day.isoformat(),
                "open": 10.0 + idx * 0.1,
                "high": 10.5 + idx * 0.1,
                "low": 9.8 + idx * 0.1,
                "close": 10.2 + idx * 0.1,
                "volume": 1_000_000 + idx * 10_000,
            }
        )
    return rows


def _build_stub_realtime(symbol: str) -> Dict[str, Any]:
    info = _build_stub_stock_info(symbol)
    return {
        **info,
        "name": info["name"],
        "current": info.get("price", 10.5),
        "amount": 12_345_678.9,
        "volume": 1_234_567,
    }


class SourceConfigRequest(BaseModel):
    """数据源配置请求"""

    source: str
    enabled: bool
    priority: Optional[int] = None
    config: Optional[Dict[str, Any]] = None


class BatchQuoteRequest(BaseModel):
    """批量实时行情请求"""

    symbols: List[str]
    fields: Optional[List[str]] = None


@router.post("/source/config")
async def update_source_config(config: SourceConfigRequest):
    """
    更新数据源配置

    Args:
        config: 数据源配置请求

    Returns:
        配置更新结果
    """
    try:
        # 获取数据源管理器
        manager = get_data_source_manager()

        # 验证数据源存在
        provider_info = manager.get_provider_info(config.source)
        if not provider_info:
            return error_response(f"数据源 {config.source} 不存在")

        # 更新数据源配置
        update_result: Dict[str, Any] = {}

        # 更新启用状态
        if config.enabled is not None:
            if config.enabled:
                manager.enable_provider(config.source)
                update_result["enabled"] = True
            else:
                manager.disable_provider(config.source)
                update_result["enabled"] = False

        # 更新优先级
        if config.priority is not None:
            manager.set_provider_priority(config.source, config.priority)
            update_result["priority"] = config.priority

        # 更新额外配置
        if config.config:
            # 获取当前配置并合并新配置
            current_config = provider_info.get("config", {})
            updated_config = {**current_config, **config.config}

            # 保存更新后的配置
            from pathlib import Path

            import yaml

            from deepsearch.config import get_config

            app_config = get_config()
            config_dir = Path(app_config.app.data_dir) / "config"
            config_dir.mkdir(parents=True, exist_ok=True)

            config_file = config_dir / f"{config.source}_config.yaml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(updated_config, f, allow_unicode=True, default_flow_style=False)

            update_result["config"] = updated_config

        logger.info(f"数据源 {config.source} 配置更新成功: {update_result}")
        return success_response(
            {
                "source": config.source,
                "updated": update_result,
                "message": f"数据源 {config.source} 配置已更新",
            }
        )

    except Exception as e:
        logger.error(f"更新数据源配置失败: {e}")
        return error_response(str(e))


@router.get("/stock/{symbol}")
async def get_stock_info(
    response: Response,
    symbol: str = Path(..., description="股票代码"),
):
    """
    获取股票基本信息

    Args:
        symbol: 股票代码

    Returns:
        股票基本信息
    """
    try:
        # 验证股票代码格式
        if not symbol.isdigit() or len(symbol) != 6:
            return JSONResponse(
                status_code=404,
                content=APIResponse.error(ErrorCodes.NOT_FOUND, "无效的股票代码", status_code=404),
            )

        # 添加响应头
        if response:
            response.headers["Cache-Control"] = "public, max-age=300"

        # 从 ReferenceDataCapability 缓存获取
        try:
            feed = get_unified_feed()
            # 尝试解析为标准格式
            try:
                asset = AssetSpec.from_code(symbol)
                key = asset.to_standard()
            except ValueError:
                # 简单代码，尝试两个交易所
                key = f"{symbol}.SH" if symbol.startswith(("6", "5")) else f"{symbol}.SZ"

            info = feed.reference.get_instrument(key) if feed.reference else None

            if info:
                result = {
                    "symbol": info.asset.to_standard(),
                    "code": info.asset.symbol,
                    "name": info.name,
                    "status": info.status.value,
                    "industry": info.industry,
                    "is_st": info.is_st,
                }
                if response:
                    response.headers["X-Data-Source"] = "reference_cache"
                return success_response(result)

            # 缓存未命中，返回 stub
            logger.warning(f"未能从缓存获取 {symbol} 的信息，返回示例数据")
            result = _build_stub_stock_info(symbol)
            if response:
                response.headers["X-Data-Source"] = "stub"
            return success_response(result)

        except Exception as data_error:
            logger.error(f"获取股票信息失败: {data_error}")
            return error_response(f"获取股票信息失败: {str(data_error)}")
    except Exception as e:
        logger.error(f"获取股票信息失败: {e}")
        return error_response(str(e))


@router.get("/kline")
async def get_kline_data(
    response: Response,
    symbol: str = Query(..., description="股票代码"),
    period: str = Query("1d", description="K线周期"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
):
    """
    获取K线数据

    Args:
        symbol: 股票代码
        period: K线周期
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        K线数据列表
    """
    try:
        # 验证日期范围
        if start_date and end_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            if end < start:
                return JSONResponse(
                    status_code=400,
                    content=APIResponse.error(
                        ErrorCodes.INVALID_PARAMETERS, "结束日期不能早于开始日期", status_code=400
                    ),
                )

        # 添加响应头
        if response:
            response.headers["Cache-Control"] = "public, max-age=60"

        # 周期映射
        period_map = {
            "1m": Timeframe.M1, "5m": Timeframe.M5, "15m": Timeframe.M15,
            "30m": Timeframe.M30, "60m": Timeframe.H1, "1d": Timeframe.D1,
            "1w": Timeframe.W1, "1M": Timeframe.MO1,
        }

        # 从 UnifiedDataFeed 获取K线数据
        try:
            asset = AssetSpec.from_code(symbol)
        except ValueError:
            logger.warning(f"无效的股票代码格式: {symbol}，返回示例数据")
            result = _build_stub_kline(symbol)
            if response:
                response.headers["X-Data-Source"] = STUB_SOURCE_LABEL
            return success_response(result)

        # 构建时间范围
        timeframe = period_map.get(period, Timeframe.D1)
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

        try:
            feed = get_unified_feed()
            kline_request = KlineRequest(
                asset=asset,
                timeframe=timeframe,
                range=time_range,
                adjust=AdjustType.FORWARD,
            )
            kline_response = await feed.get_kline(kline_request)

            if kline_response.is_empty():
                logger.warning(f"未能获取 {symbol} 的K线数据，返回示例数据")
                result = _build_stub_kline(symbol)
                if response:
                    response.headers["X-Data-Source"] = STUB_SOURCE_LABEL
                return success_response(result)

            # 转换为前端期望格式
            result = []
            for bar in kline_response.bars:
                result.append({
                    "date": bar.timestamp.strftime("%Y-%m-%d"),
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": bar.volume,
                })

            if response:
                response.headers["X-Data-Source"] = "unified_feed"
            return success_response(result)
        except Exception as data_error:
            logger.error(f"从 UnifiedDataFeed 获取K线数据失败: {data_error}")
            return error_response(f"获取K线数据失败: {str(data_error)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        return error_response(str(e))


@router.get("/realtime/{symbol}")
async def get_realtime_quote(symbol: str = Path(..., description="股票代码")):
    """
    获取实时行情

    Args:
        symbol: 股票代码

    Returns:
        实时行情数据
    """
    try:
        # 解析资产
        try:
            asset = AssetSpec.from_code(symbol)
        except ValueError:
            logger.warning(f"无效的股票代码格式: {symbol}，返回示例数据")
            return success_response(_build_stub_realtime(symbol))

        # 从 UnifiedDataFeed 获取实时行情
        try:
            feed = get_unified_feed()
            request = RealtimeQuoteRequest(assets=[asset])
            response = await feed.get_realtime(request)

            if len(response) == 0:
                logger.warning(f"未能获取 {symbol} 的实时行情，返回示例数据")
                return success_response(_build_stub_realtime(symbol))

            quote = response.quotes[0]
            result = {
                "symbol": symbol,
                "name": "",
                "last_price": float(quote.last_price),
                "current": float(quote.last_price),
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
            return success_response(result)
        except Exception as data_error:
            logger.error(f"从 UnifiedDataFeed 获取实时行情失败: {data_error}")
            return error_response(f"获取实时行情失败: {str(data_error)}")
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}")
        return error_response(str(e))


@router.post("/realtime/batch")
async def get_batch_realtime_quotes(request: BatchQuoteRequest):
    """
    批量获取实时行情

    Args:
        request: 批量行情请求

    Returns:
        批量行情数据
    """
    try:
        # 解析所有资产
        assets = []
        invalid_symbols = []
        for symbol in request.symbols:
            try:
                asset = AssetSpec.from_code(symbol)
                assets.append(asset)
            except ValueError:
                logger.warning(f"无效的股票代码格式: {symbol}")
                invalid_symbols.append(symbol)

        if not assets:
            # 所有代码都无效，返回示例数据
            quotes = [_build_stub_realtime(s) for s in request.symbols]
            return success_response(quotes)

        # 从 UnifiedDataFeed 批量获取实时行情
        try:
            feed = get_unified_feed()
            realtime_request = RealtimeQuoteRequest(assets=assets)
            response = await feed.get_realtime(realtime_request)

            # 构建结果
            quotes = []
            for i, quote in enumerate(response.quotes):
                result = {
                    "symbol": assets[i].to_standard() if i < len(assets) else "",
                    "name": "",
                    "last_price": float(quote.last_price),
                    "current": float(quote.last_price),
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
                quotes.append(result)

            # 为无效代码添加示例数据
            for symbol in invalid_symbols:
                quotes.append(_build_stub_realtime(symbol))

            if quotes:
                return success_response(quotes)
            else:
                return error_response("无法获取任何股票的实时行情")
        except Exception as data_error:
            logger.error(f"从 UnifiedDataFeed 批量获取实时行情失败: {data_error}")
            return error_response(f"批量获取实时行情失败: {str(data_error)}")
    except Exception as e:
        logger.error(f"批量获取实时行情失败: {e}")
        return error_response(str(e))
