"""
MiniQMT API 端点

提供 MiniQMT 数据源的 REST API 接口
"""

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, cast

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from deepsearch.infrastructure.providers.implementations.qmt.miniqmt import MiniQMTProvider
from deepsearch.infrastructure.providers.managers.manager import DataProviderManager

# 创建 API 路由
router = APIRouter(prefix="/api/miniqmt", tags=["MiniQMT"])

# 全局 MiniQMT 实例
_miniqmt_provider: Optional[MiniQMTProvider] = None


class SubscribeRequest(BaseModel):
    """订阅请求"""

    symbols: List[str]
    data_types: Optional[List[str]] = ["tick", "orderbook"]


class UnsubscribeRequest(BaseModel):
    """取消订阅请求"""

    symbols: List[str]


class HistoryRequest(BaseModel):
    """历史数据请求"""

    symbol: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    period: str = "1d"
    adjust: str = "qfq"


class RealtimeRequest(BaseModel):
    """实时数据请求"""

    symbols: List[str]


def get_miniqmt_provider() -> MiniQMTProvider:
    """获取 MiniQMT 提供者实例"""
    global _miniqmt_provider

    if _miniqmt_provider is None:
        # 尝试从数据管理器获取
        try:
            from deepsearch.core.managers.component_manager import ComponentManager

            manager = ComponentManager()

            # 获取数据提供者管理器
            data_manager = manager.get_component("data_provider_manager")
            if isinstance(data_manager, DataProviderManager):
                provider_candidate = data_manager.get_provider("miniqmt")
                if isinstance(provider_candidate, MiniQMTProvider):
                    _miniqmt_provider = provider_candidate
        except Exception as e:
            logger.error(f"获取 MiniQMT 提供者失败: {e}")

    if _miniqmt_provider is None:
        raise HTTPException(status_code=503, detail="MiniQMT 服务不可用")

    return _miniqmt_provider


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """
    获取 MiniQMT 连接状态

    Returns:
        连接状态信息
    """
    try:
        provider = get_miniqmt_provider()
        status_raw = provider.get_connection_status()
        if not isinstance(status_raw, Mapping):
            raise HTTPException(status_code=500, detail="MiniQMT 状态格式无效")
        status_payload: Dict[str, Any] = dict(status_raw)

        # 添加连接统计信息
        stats_raw = provider.get_statistics()
        if isinstance(stats_raw, Mapping):
            statistics = dict(stats_raw)
        else:
            statistics = {"raw": stats_raw}
        status_payload.update({"statistics": statistics, "timestamp": datetime.now().isoformat()})

        return status_payload

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 MiniQMT 状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe")
async def subscribe_symbols(request: SubscribeRequest) -> Dict[str, Any]:
    """
    订阅股票行情

    Args:
        request: 订阅请求

    Returns:
        订阅结果
    """
    try:
        provider = get_miniqmt_provider()

        # 执行订阅
        success = await provider.subscribe(request.symbols)

        if success:
            return {
                "success": True,
                "message": f"成功订阅 {len(request.symbols)} 只股票",
                "symbols": request.symbols,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            raise HTTPException(status_code=400, detail="订阅失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"订阅股票失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unsubscribe")
async def unsubscribe_symbols(request: UnsubscribeRequest) -> Dict[str, Any]:
    """
    取消订阅股票行情

    Args:
        request: 取消订阅请求

    Returns:
        取消订阅结果
    """
    try:
        provider = get_miniqmt_provider()

        # 执行取消订阅
        success = await provider.unsubscribe(request.symbols)

        if success:
            return {
                "success": True,
                "message": f"成功取消订阅 {len(request.symbols)} 只股票",
                "symbols": request.symbols,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            raise HTTPException(status_code=400, detail="取消订阅失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消订阅失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/realtime")
async def get_realtime_data(
    symbols: str = Query(..., description="股票代码，逗号分隔")
) -> Dict[str, Any]:
    """
    获取实时行情数据

    Args:
        symbols: 股票代码列表（逗号分隔）

    Returns:
        实时行情数据
    """
    try:
        provider = get_miniqmt_provider()

        # 解析股票列表
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]

        if not symbol_list:
            raise HTTPException(status_code=400, detail="请提供股票代码")

        # 创建数据请求
        from deepsearch.infrastructure.providers.interfaces.base import DataRequest

        request = DataRequest(symbols=symbol_list, period="tick")

        # 获取数据
        response = await provider.get_data(request)

        if response.success:
            # 转换 DataFrame 为 JSON
            payload = response.data
            if payload is None:
                data: List[Dict[str, Any]] = []
            elif hasattr(payload, "to_dict"):
                records_any = getattr(payload, "to_dict")("records")
                data = cast(List[Dict[str, Any]], records_any)
            elif isinstance(payload, Mapping):
                data = [dict(payload)]
            elif isinstance(payload, Sequence):
                data = [dict(item) if isinstance(item, Mapping) else {"value": item} for item in payload]
            else:
                data = []

            return {
                "success": True,
                "data": data,
                "count": len(data),
                "symbols": symbol_list,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            raise HTTPException(status_code=400, detail=response.error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实时数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_history_data(
    symbol: str = Query(..., description="股票代码"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    period: str = Query("1d", description="周期"),
    adjust: str = Query("qfq", description="复权类型"),
) -> Dict[str, Any]:
    """
    获取历史K线数据

    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        period: 数据周期
        adjust: 复权类型

    Returns:
        历史K线数据
    """
    try:
        provider = get_miniqmt_provider()

        # 创建数据请求
        from deepsearch.infrastructure.providers.interfaces.base import DataRequest

        request = DataRequest(
            symbol=symbol, start_date=start_date, end_date=end_date, period=period, adjust=adjust
        )

        # 获取数据
        response = await provider.get_data(request)

        if response.success:
            payload = response.data
            if payload is None:
                data = []
            elif hasattr(payload, "to_dict"):
                records_any = getattr(payload, "to_dict")("records")
                data = cast(List[Dict[str, Any]], records_any)
            elif isinstance(payload, Mapping):
                data = [dict(payload)]
            elif isinstance(payload, Sequence):
                data = [dict(item) if isinstance(item, Mapping) else {"value": item} for item in payload]
            else:
                data = []

            return {
                "success": True,
                "data": data,
                "count": len(data),
                "symbol": symbol,
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            raise HTTPException(status_code=400, detail=response.error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取历史数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/minute")
async def get_minute_data(
    symbol: str = Query(..., description="股票代码"),
    date: Optional[str] = Query(None, description="日期"),
    period: str = Query("1m", description="分钟周期"),
) -> Dict[str, Any]:
    """
    获取分钟K线数据

    Args:
        symbol: 股票代码
        date: 日期
        period: 分钟周期（1m, 5m, 15m, 30m, 60m）

    Returns:
        分钟K线数据
    """
    try:
        provider = get_miniqmt_provider()

        # 创建数据请求
        from deepsearch.infrastructure.providers.interfaces.base import DataRequest

        request = DataRequest(symbol=symbol, start_date=date, end_date=date, period=period)

        # 获取数据
        response = await provider.get_data(request)

        if response.success:
            payload = response.data
            if payload is None:
                data = []
            elif hasattr(payload, "to_dict"):
                records_any = getattr(payload, "to_dict")("records")
                data = cast(List[Dict[str, Any]], records_any)
            elif isinstance(payload, Mapping):
                data = [dict(payload)]
            elif isinstance(payload, Sequence):
                data = [dict(item) if isinstance(item, Mapping) else {"value": item} for item in payload]
            else:
                data = []

            return {
                "success": True,
                "data": data,
                "count": len(data),
                "symbol": symbol,
                "period": period,
                "date": date,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            raise HTTPException(status_code=400, detail=response.error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分钟数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconnect")
async def reconnect() -> Dict[str, Any]:
    """
    重新连接 MiniQMT

    Returns:
        重连结果
    """
    try:
        provider = get_miniqmt_provider()

        # 先断开
        await provider._disconnect()

        # 重新连接
        success = await provider._connect()

        if success:
            return {
                "success": True,
                "message": "成功重新连接到 MiniQMT",
                "status": provider.get_connection_status(),
                "timestamp": datetime.now().isoformat(),
            }
        else:
            raise HTTPException(status_code=503, detail="重新连接失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新连接失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscriptions")
async def get_subscriptions() -> Dict[str, Any]:
    """
    获取当前订阅列表

    Returns:
        订阅的股票列表
    """
    try:
        provider = get_miniqmt_provider()
        status = provider.get_connection_status()

        return {
            "success": True,
            "subscribed_symbols": status.get("subscribed_symbols", []),
            "count": len(status.get("subscribed_symbols", [])),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取订阅列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics() -> Dict[str, Any]:
    """
    获取 MiniQMT 统计信息

    Returns:
        统计信息
    """
    try:
        provider = get_miniqmt_provider()
        stats = provider.get_statistics()

        return {"success": True, "statistics": stats, "timestamp": datetime.now().isoformat()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
