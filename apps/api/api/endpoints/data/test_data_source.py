"""
数据源测试接口

提供数据源连接和性能测试功能
"""

import time
from typing import Optional

from core.observability.monitoring.data_source_monitor import DataSourceMonitor
from core.ports.data_sources import DataAccessType, DataSourceType
from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel

from apps.api.api.provider_deps import resolve_provider_from_request

router = APIRouter(prefix="/api/data-source", tags=["data-source-test"])


class TestRequest(BaseModel):
    """测试请求"""

    source: str
    symbol: str = "000001"  # 默认测试股票
    test_type: str = "realtime"  # realtime, historical


class TestResponse(BaseModel):
    """测试响应"""

    success: bool
    source: str
    latency_ms: float
    data_size: int
    message: str
    error: Optional[str] = None


@router.post("/test", response_model=TestResponse)
async def test_data_source(request: TestRequest, http_request: Request):
    """
    测试数据源连接和性能

    Args:
        request: 测试请求参数

    Returns:
        测试结果，包含延迟等性能指标
    """
    monitor = DataSourceMonitor()
    start_time = time.perf_counter()

    try:
        # 解析数据源类型
        try:
            source_type = DataSourceType(request.source.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的数据源类型: {request.source}")

        # 解析访问类型
        access_type = (
            DataAccessType.REALTIME_QUOTE
            if request.test_type == "realtime"
            else DataAccessType.HISTORICAL_KLINE
        )

        try:
            # 执行测试请求
            if source_type == DataSourceType.AKSHARE or source_type == DataSourceType.AKSHARE_PROXY:
                try:
                    provider = await resolve_provider_from_request(
                        http_request, "akshare", strict=False
                    )
                    if provider is None:
                        raise RuntimeError("AkShare provider 不可用")
                    if request.test_type == "realtime":
                        # 使用 get_realtime_data 方法，传入符号列表
                        result = await provider.get_realtime_data([request.symbol])
                        # 提取单个股票的数据
                        if result and isinstance(result, dict):
                            result = result.get(request.symbol, {"error": "No data for symbol"})
                    else:
                        # 使用 get_history_data 方法
                        result = await provider.get_history_data(
                            symbols=[request.symbol],
                            start_date=None,
                            end_date=None,
                            frequency="daily",
                        )
                        # 提取单个股票的数据
                        if result and isinstance(result, dict):
                            result = result.get(request.symbol, {"error": "No data for symbol"})
                except Exception as provider_error:
                    # 如果provider方法有问题，返回错误信息
                    logger.error(f"Provider error for {source_type}: {provider_error}")
                    result = {"error": f"Provider error: {provider_error}", "success": False}
            elif source_type == DataSourceType.AMAZINGDATA:
                provider = await resolve_provider_from_request(
                    http_request, "amazingdata", strict=False
                )
                if provider is None:
                    raise RuntimeError("AmazingData provider 不可用")
                # AmazingData测试逻辑
                if request.test_type == "realtime":
                    try:
                        result = await provider.get_realtime_data([request.symbol])
                        if result and isinstance(result, dict):
                            result = result.get(request.symbol, {"error": "No data for symbol"})
                    except AttributeError:
                        # 如果方法不存在，返回错误
                        # 注意：AmazingData实时数据需要通过订阅模式(onSnapshot)获取，不存在get_realtime_data方法
                        result = {
                            "error": "AmazingData实时数据需通过订阅接口(onSnapshot)获取，请使用datasource_manager中的新测试端点",
                            "success": False,
                        }
                else:
                    try:
                        result = await provider.get_historical_data(request.symbol)
                        if not result:
                            result = {"error": "No historical data available", "success": False}
                    except AttributeError:
                        result = {
                            "error": "AmazingData历史数据需使用特定API接口，请使用datasource_manager中的新测试端点",
                            "success": False,
                        }
            elif source_type == DataSourceType.QMT:
                provider = await resolve_provider_from_request(
                    http_request, "miniqmt", strict=False
                )
                if provider is None:
                    provider = await resolve_provider_from_request(
                        http_request, "qmt", strict=False
                    )
                if provider is None:
                    raise RuntimeError("MiniQMT provider 不可用")
                # QMT测试逻辑
                if request.test_type == "realtime":
                    try:
                        result = await provider.get_realtime_quote(request.symbol)
                        if not result:
                            result = {"error": "QMT realtime data not available", "success": False}
                    except AttributeError:
                        result = {
                            "error": "QMT provider does not support realtime quotes",
                            "success": False,
                        }
                else:
                    try:
                        result = await provider.get_kline_data(request.symbol, period="daily")
                        if not result:
                            result = {
                                "error": "QMT historical data not available",
                                "success": False,
                            }
                    except AttributeError:
                        result = {
                            "error": "QMT provider does not support kline data",
                            "success": False,
                        }
            else:
                # 统一数据源 - 使用默认测试逻辑
                try:
                    provider = await resolve_provider_from_request(
                        http_request, "unified", strict=False
                    )
                    if provider is None:
                        provider = await resolve_provider_from_request(
                            http_request, "akshare", strict=False
                        )
                    if provider is None:
                        raise RuntimeError("统一数据源不可用（unified/akshare 均不可用）")
                    # 尝试获取实时数据作为测试
                    if request.test_type == "realtime":
                        result = await provider.get_realtime_quote(request.symbol)
                    else:
                        result = await provider.get_historical_data(request.symbol, period="daily")
                except Exception as unified_error:
                    # 如果统一数据源不可用，返回错误信息
                    logger.error(f"Unified provider error: {unified_error}")
                    result = {"error": f"Unified provider error: {unified_error}", "success": False}

            # 计算延迟（毫秒）
            latency_ms = (time.perf_counter() - start_time) * 1000

            # 判断是否成功
            success = bool(result and not result.get("error"))

            # 计算数据大小
            data_size = len(str(result)) if result else 0

            # 记录到监控系统
            monitor.record_access(
                source=source_type,
                access_type=access_type,
                symbol=request.symbol,
                module="test",
                success=success,
                latency_ms=latency_ms,
                data_size=data_size,
                error_message=result.get("error") if not success else None,
            )

            # 返回测试结果
            return TestResponse(
                success=success,
                source=request.source,
                latency_ms=latency_ms,
                data_size=data_size,
                message=f"测试{'成功' if success else '失败'}",
                error=result.get("error") if not success else None,
            )

        except Exception as e:
            # 计算失败时的延迟
            latency_ms = (time.perf_counter() - start_time) * 1000

            # 记录失败到监控 - 安全地处理
            try:
                monitor.record_access(
                    source=source_type,
                    access_type=access_type,
                    symbol=request.symbol,
                    module="test",
                    success=False,
                    latency_ms=latency_ms,
                    data_size=0,
                    error_message=str(e),
                )
            except Exception as monitor_error:
                logger.warning(f"监控记录失败: {monitor_error}")

            logger.error(f"测试数据源 {request.source} 失败: {e}")

            return TestResponse(
                success=False,
                source=request.source,
                latency_ms=latency_ms,
                data_size=0,
                message="测试失败",
                error=str(e),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试接口错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-all")
async def test_all_data_sources():
    """
    测试所有数据源

    Returns:
        所有数据源的测试结果
    """
    results = {}
    test_symbol = "000001"

    # 测试所有已知数据源
    sources = [
        DataSourceType.AKSHARE_PROXY,
        DataSourceType.AKSHARE,
        DataSourceType.AMAZINGDATA,
        DataSourceType.QMT,
    ]

    for source in sources:
        try:
            request = TestRequest(source=source.value, symbol=test_symbol, test_type="realtime")
            result = await test_data_source(request)
            results[source.value] = result.dict()
        except Exception as e:
            results[source.value] = {
                "success": False,
                "error": str(e),
                "latency_ms": -1,
                "data_size": 0,
                "message": f"测试失败: {e}",
            }

    return results
