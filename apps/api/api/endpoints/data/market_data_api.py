"""
市场数据和股票信息API

提供全面的市场数据服务
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

# New imports for UnifiedDataFeed
from core.application.services.unified_data import get_unified_feed
from core.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from core.ports.data.semantic_types import AdjustType, AssetSpec, Timeframe, TimeRange
from core.utils.data_sources import get_data_source_manager
from fastapi import APIRouter, HTTPException, Path, Query, Response
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from apps.api.api.common.response_format import (
    APIResponse,
    ErrorCodes,
    error_response,
    success_response,
)

router = APIRouter(prefix="/api/data", tags=["market_data"])


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


def _parse_asset_symbol(symbol: str) -> AssetSpec:
    """解析股票代码，兼容纯 6 位代码与标准代码。"""
    normalized = symbol.strip().upper()

    try:
        return AssetSpec.from_code(normalized)
    except ValueError:
        if normalized.isdigit() and len(normalized) == 6:
            exchange = "SH" if normalized.startswith(("5", "6", "9")) else "SZ"
            return AssetSpec.from_code(f"{normalized}.{exchange}")
        raise


def _build_stub_quote(symbol: str) -> Dict[str, Any]:
    """构建离线场景兜底行情，确保接口契约稳定。"""
    return {
        "symbol": symbol,
        "name": "",
        "last_price": 0.0,
        "current": 0.0,
        "open": 0.0,
        "high": 0.0,
        "low": 0.0,
        "pre_close": 0.0,
        "volume": 0,
        "amount": 0.0,
        "change": 0.0,
        "change_pct": 0.0,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


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
            from core.config import get_config

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
        # 解析股票代码（兼容纯数字代码）
        try:
            asset = _parse_asset_symbol(symbol)
        except ValueError:
            return JSONResponse(
                status_code=404,
                content=APIResponse.error(ErrorCodes.NOT_FOUND, "无效的股票代码", status_code=404),
            )

        # 添加响应头
        if response:
            response.headers["Cache-Control"] = "public, max-age=300"
            response.headers["ETag"] = f'W/"stock-{asset.symbol}-{asset.exchange.value}"'
            response.headers["Last-Modified"] = datetime.utcnow().strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )

        # 从 ReferenceDataCapability 缓存获取
        try:
            feed = get_unified_feed()
            key = asset.to_standard()
            info = feed.reference.get_instrument(key) if feed.reference else None

            if info:
                result = {
                    "symbol": info.asset.to_standard(),
                    "code": info.asset.symbol,
                    "exchange": info.asset.exchange.value,
                    "name": info.name,
                    "status": info.status.value,
                    "industry": info.industry,
                    "is_st": info.is_st,
                }
                if response:
                    response.headers["X-Data-Source"] = "akshare"
                return success_response(result)

            # 缓存未命中时返回基础占位信息，保持接口可用
            fallback_result = {
                "symbol": asset.symbol,
                "code": asset.symbol,
                "exchange": asset.exchange.value,
                "name": "",
                "status": "unknown",
                "industry": "",
                "is_st": False,
            }
            if response:
                response.headers["X-Data-Source"] = "akshare"
            return success_response(fallback_result)

        except RuntimeError as data_error:
            logger.error(f"数据服务未就绪: {data_error}")
            return JSONResponse(
                status_code=503,
                content=APIResponse.error(
                    ErrorCodes.DATA_SOURCE_UNAVAILABLE,
                    "数据服务尚未初始化，请稍后重试",
                    status_code=503,
                ),
            )
        except Exception as data_error:
            logger.error(f"获取股票信息失败: {data_error}")
            return error_response(f"获取股票信息失败: {str(data_error)}")
    except Exception as e:
        logger.error(f"获取股票信息失败: {e}")
        return error_response(str(e))


@router.get("/market-kline")
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
            "1m": Timeframe.M1,
            "5m": Timeframe.M5,
            "15m": Timeframe.M15,
            "30m": Timeframe.M30,
            "60m": Timeframe.H1,
            "1d": Timeframe.D1,
            "1w": Timeframe.W1,
            "1M": Timeframe.MO1,
        }

        # 从 UnifiedDataFeed 获取K线数据
        try:
            asset = _parse_asset_symbol(symbol)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content=APIResponse.error(
                    ErrorCodes.INVALID_PARAMETERS,
                    f"无效的股票代码格式: {symbol}",
                    status_code=400,
                ),
            )

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
                return JSONResponse(
                    status_code=404,
                    content=APIResponse.error(
                        ErrorCodes.NOT_FOUND,
                        f"未找到 {symbol} 的K线数据",
                        status_code=404,
                    ),
                )

            # 转换为前端期望格式
            result = []
            for bar in kline_response.bars:
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
            asset = _parse_asset_symbol(symbol)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的股票代码格式: {symbol}")

        # 从 UnifiedDataFeed 获取实时行情
        try:
            feed = get_unified_feed()
            request = RealtimeQuoteRequest(assets=[asset])
            response = await feed.get_realtime(request)

            if len(response) == 0:
                return success_response(_build_stub_quote(asset.symbol))

            quote = response.quotes[0]
            quote_symbol = quote.asset.symbol if getattr(quote, "asset", None) else asset.symbol
            result = {
                "symbol": quote_symbol,
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
        except HTTPException:
            raise
        except Exception as data_error:
            logger.error(f"从 UnifiedDataFeed 获取实时行情失败: {data_error}")
            return success_response(_build_stub_quote(asset.symbol))
    except HTTPException:
        raise
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
        assets: List[AssetSpec] = []
        valid_symbols: List[str] = []
        invalid_symbols: List[str] = []
        for symbol in request.symbols:
            try:
                asset = _parse_asset_symbol(symbol)
                assets.append(asset)
                valid_symbols.append(symbol)
            except ValueError:
                logger.warning(f"无效的股票代码格式: {symbol}")
                invalid_symbols.append(symbol)

        if not assets:
            raise HTTPException(
                status_code=400,
                detail=f"所有股票代码格式无效: {', '.join(invalid_symbols)}",
            )

        # 从 UnifiedDataFeed 批量获取实时行情
        try:
            feed = get_unified_feed()
            realtime_request = RealtimeQuoteRequest(assets=assets)
            response = await feed.get_realtime(realtime_request)

            # 构建结果
            quotes: List[Dict[str, Any]] = []
            for i, quote in enumerate(response.quotes):
                quote_symbol = valid_symbols[i] if i < len(valid_symbols) else ""

                result = {
                    "symbol": quote_symbol,
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

            # 如果真实行情为空或数量不足，补齐兜底数据以保持批量接口契约稳定
            if len(quotes) < len(valid_symbols):
                missing_symbols = valid_symbols[len(quotes) :]
                quotes.extend(
                    _build_stub_quote(missing_symbol) for missing_symbol in missing_symbols
                )

            # 记录被跳过的无效代码
            if invalid_symbols:
                logger.warning(f"批量行情请求中有无效代码被跳过: {invalid_symbols}")

            if quotes:
                return success_response(quotes)
            else:
                return success_response([_build_stub_quote(symbol) for symbol in valid_symbols])
        except HTTPException:
            raise
        except Exception as data_error:
            logger.error(f"从 UnifiedDataFeed 批量获取实时行情失败: {data_error}")
            return success_response([_build_stub_quote(symbol) for symbol in valid_symbols])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量获取实时行情失败: {e}")
        return error_response(str(e))
