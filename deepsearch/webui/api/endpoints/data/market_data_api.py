"""
市场数据和股票信息API

提供全面的市场数据服务
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query, HTTPException, Path, Body, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger
import pandas as pd
from datetime import datetime, timedelta

from deepsearch.infrastructure.providers.managers.data_source_manager import (
    get_data_source_manager
)
from deepsearch.webui.api.common.response_format import (
    success_response, error_response, APIResponse, ErrorCodes
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
        update_result = {}

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
            from deepsearch.config import get_config
            from pathlib import Path
            import yaml

            app_config = get_config()
            config_dir = Path(app_config.app.data_dir) / "config"
            config_dir.mkdir(parents=True, exist_ok=True)

            config_file = config_dir / f"{config.source}_config.yaml"
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(updated_config, f, allow_unicode=True, default_flow_style=False)

            update_result["config"] = updated_config

        logger.info(f"数据源 {config.source} 配置更新成功: {update_result}")
        return success_response({
            "source": config.source,
            "updated": update_result,
            "message": f"数据源 {config.source} 配置已更新"
        })

    except Exception as e:
        logger.error(f"更新数据源配置失败: {e}")
        return error_response(str(e))


@router.get("/stock/{symbol}")
async def get_stock_info(
    symbol: str = Path(..., description="股票代码"),
    response: Response = None
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
                content=APIResponse.error(
                    ErrorCodes.NOT_FOUND,
                    "无效的股票代码",
                    status_code=404
                )
            )

        # 添加响应头
        if response:
            response.headers["X-Data-Source"] = "cloudflare"
            response.headers["Cache-Control"] = "public, max-age=300"

        # 尝试从数据源获取股票信息
        manager = get_data_source_manager()
        try:
            result = await manager.execute_with_fallback(
                "get_stock_info",
                symbol=symbol
            )
            if result:
                return success_response(result)
            else:
                return error_response(f"无法获取股票 {symbol} 的信息")
        except Exception as data_error:
            logger.error(f"从数据源获取股票信息失败: {data_error}")
            return error_response(f"获取股票信息失败: {str(data_error)}")
    except Exception as e:
        logger.error(f"获取股票信息失败: {e}")
        return error_response(str(e))


@router.get("/kline")
async def get_kline_data(
    symbol: str = Query(..., description="股票代码"),
    period: str = Query("1d", description="K线周期"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    response: Response = None
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
                        ErrorCodes.INVALID_PARAMETERS,
                        "结束日期不能早于开始日期",
                        status_code=400
                    )
                )

        # 添加响应头
        if response:
            response.headers["X-Data-Source"] = "cloudflare"
            response.headers["Cache-Control"] = "public, max-age=60"

        # 从数据源获取K线数据
        manager = get_data_source_manager()
        try:
            result = await manager.execute_with_fallback(
                "get_kline_data",
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date
            )
            if result:
                return success_response(result)
            else:
                return error_response(f"无法获取股票 {symbol} 的K线数据")
        except Exception as data_error:
            logger.error(f"从数据源获取K线数据失败: {data_error}")
            return error_response(f"获取K线数据失败: {str(data_error)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        return error_response(str(e))


@router.get("/realtime/{symbol}")
async def get_realtime_quote(
    symbol: str = Path(..., description="股票代码")
):
    """
    获取实时行情

    Args:
        symbol: 股票代码

    Returns:
        实时行情数据
    """
    try:
        # 从数据源获取实时行情
        manager = get_data_source_manager()
        try:
            result = await manager.execute_with_fallback(
                "get_realtime_quote",
                symbol=symbol
            )
            if result:
                return success_response(result)
            else:
                return error_response(f"无法获取股票 {symbol} 的实时行情")
        except Exception as data_error:
            logger.error(f"从数据源获取实时行情失败: {data_error}")
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
        # 从数据源批量获取实时行情
        manager = get_data_source_manager()
        try:
            quotes = []
            for symbol in request.symbols:
                result = await manager.execute_with_fallback(
                    "get_realtime_quote",
                    symbol=symbol
                )
                if result:
                    quotes.append(result)
                else:
                    # 记录失败但继续处理其他股票
                    logger.warning(f"无法获取股票 {symbol} 的实时行情")

            if quotes:
                return success_response(quotes)
            else:
                return error_response("无法获取任何股票的实时行情")
        except Exception as data_error:
            logger.error(f"批量获取实时行情失败: {data_error}")
            return error_response(f"批量获取实时行情失败: {str(data_error)}")
    except Exception as e:
        logger.error(f"批量获取实时行情失败: {e}")
        return error_response(str(e))