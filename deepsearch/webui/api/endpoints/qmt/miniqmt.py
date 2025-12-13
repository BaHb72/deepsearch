"""
MiniQMT API 端点

提供 MiniQMT 数据源的 REST API 接口
"""

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, cast

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from deepsearch.infrastructure.providers.implementations.qmt.miniqmt import MiniQMTProvider
# 兼容新旧管理器
from deepsearch.infrastructure.providers.managers.manager import DataProviderManager

try:
    from deepsearch.utils.data_sources import DataSourceManager
except ImportError:
    DataSourceManager = None  # type: ignore

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
            from deepsearch.core.runtime.context import get_context

            # 获取数据提供者管理器
            data_manager = get_context().get_component("data_provider_manager")
            # 兼容检查：支持新旧两种管理器
            if isinstance(data_manager, DataProviderManager) or (
                    DataSourceManager is not None and isinstance(data_manager, DataSourceManager)
            ):
                provider_candidate = data_manager.get_provider("miniqmt")
                if isinstance(provider_candidate, MiniQMTProvider):
                    _miniqmt_provider = provider_candidate
        except Exception as e:
            logger.warning(f"从管理器获取 MiniQMT 提供者失败: {e}")

    if _miniqmt_provider is None:
        # Fallback: 直接创建一个可用的 Provider 实例
        try:
            from deepsearch.infrastructure.providers.interfaces.base import (
                DataProviderConfig,
                DataSourceType,
            )

            # 创建一个实现了抽象方法的测试子类
            class _DirectMiniQMTProvider(MiniQMTProvider):
                async def initialize(self) -> bool:
                    return True

                async def get_stock_list(self, limit=None, **kwargs):
                    return []

                async def get_kline_data(self, symbol, period="1d", start_date=None,
                                         end_date=None, limit=100, adjust="none", **kwargs):
                    return []

            _miniqmt_provider = _DirectMiniQMTProvider()
            logger.info("已创建直接 MiniQMT 提供者实例")
        except Exception as e:
            logger.error(f"创建 MiniQMT 提供者失败: {e}")
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


# ==================== xtdata 直接调用端点 ====================

@router.get("/xtdata/tick")
async def get_xtdata_tick(
        symbols: str = Query(..., description="股票代码，逗号分隔，如: 000001.SZ,600000.SH")
) -> Dict[str, Any]:
    """
    直接使用 xtdata 获取 Tick 数据（含五档盘口）
    
    Args:
        symbols: 股票代码列表（逗号分隔）
    
    Returns:
        Tick 数据，包含最新价、涨跌、五档盘口等
    """
    try:
        from xtquant import xtdata

        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="请提供股票代码")

        result = xtdata.get_full_tick(symbol_list)

        if not result:
            return {
                "success": False,
                "message": "未获取到数据，请确认 MiniQMT 终端已启动",
                "data": {},
                "timestamp": datetime.now().isoformat(),
            }

        # 格式化返回数据
        formatted_data = {}
        for symbol, tick in result.items():
            if isinstance(tick, dict):
                formatted_data[symbol] = {
                    "symbol": symbol,
                    "lastPrice": tick.get("lastPrice"),
                    "open": tick.get("open"),
                    "high": tick.get("high"),
                    "low": tick.get("low"),
                    "preClose": tick.get("preClose"),
                    "volume": tick.get("volume"),
                    "amount": tick.get("amount"),
                    "bidPrice": tick.get("bidPrice", []),
                    "bidVol": tick.get("bidVol", []),
                    "askPrice": tick.get("askPrice", []),
                    "askVol": tick.get("askVol", []),
                    "time": tick.get("time"),
                }

        return {
            "success": True,
            "data": formatted_data,
            "count": len(formatted_data),
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取 xtdata tick 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/quote")
async def get_xtdata_quote(
        symbols: str = Query(..., description="股票代码，逗号分隔")
) -> Dict[str, Any]:
    """
    获取简化的实时行情数据
    
    Args:
        symbols: 股票代码列表
    
    Returns:
        简化的行情数据
    """
    try:
        from xtquant import xtdata

        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="请提供股票代码")

        result = xtdata.get_full_tick(symbol_list)

        if not result:
            return {
                "success": False,
                "message": "MiniQMT 未连接或无数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 转换为列表格式，便于前端表格展示
        quotes = []
        for symbol, tick in result.items():
            if isinstance(tick, dict):
                last_price = tick.get("lastPrice", 0)
                pre_close = tick.get("preClose", 0)
                change = last_price - pre_close if last_price and pre_close else 0
                change_pct = (change / pre_close * 100) if pre_close else 0

                quotes.append({
                    "symbol": symbol,
                    "name": symbol,  # 可以后续从其他数据源获取名称
                    "lastPrice": last_price,
                    "change": round(change, 2),
                    "changePct": round(change_pct, 2),
                    "open": tick.get("open"),
                    "high": tick.get("high"),
                    "low": tick.get("low"),
                    "volume": tick.get("volume"),
                    "amount": tick.get("amount"),
                })

        return {
            "success": True,
            "data": quotes,
            "count": len(quotes),
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取 xtdata quote 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/kline")
async def get_xtdata_kline(
        symbol: str = Query(..., description="股票代码"),
        period: str = Query("1d", description="周期: 1m, 5m, 15m, 30m, 60m, 1d"),
        count: int = Query(100, description="获取条数"),
) -> Dict[str, Any]:
    """
    获取K线历史数据
    
    Args:
        symbol: 股票代码
        period: K线周期
        count: 获取条数
    
    Returns:
        K线数据列表
    """
    try:
        from xtquant import xtdata

        # 先尝试下载数据
        try:
            xtdata.download_history_data(symbol, period, count=-1)
        except Exception:
            pass  # 忽略下载错误，尝试获取本地缓存

        result = xtdata.get_market_data(
            stock_list=[symbol],
            period=period,
            count=count,
        )

        # 检查返回数据是否有效
        if not isinstance(result, dict) or 'time' not in result or symbol not in result.get('open', {}):
            return {
                "success": False,
                "message": "未获取到K线数据或数据格式不正确",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 转换数据格式
        klines = []
        time_data = result.get('time', [])
        open_data = result.get('open', {}).get(symbol, [])
        high_data = result.get('high', {}).get(symbol, [])
        low_data = result.get('low', {}).get(symbol, [])
        close_data = result.get('close', {}).get(symbol, [])
        volume_data = result.get('volume', {}).get(symbol, [])
        amount_data = result.get('amount', {}).get(symbol, [])

        # 找出最短的数据序列长度，以防数据不一致
        min_len = min(
            len(time_data),
            len(open_data),
            len(high_data),
            len(low_data),
            len(close_data),
            len(volume_data),
            len(amount_data)
        )

        if min_len != len(time_data):
            logger.warning(f"K线数据字段长度不一致 for symbol {symbol}, period {period}")

        for i in range(min_len):
            klines.append({
                # xtdata 时间戳是毫秒
                "time": int(time_data[i]),
                "open": float(open_data[i]),
                "high": float(high_data[i]),
                "low": float(low_data[i]),
                "close": float(close_data[i]),
                "volume": int(volume_data[i]),
                "amount": float(amount_data[i]),
            })

        return {
            "success": True,
            "symbol": symbol,
            "period": period,
            "data": klines,
            "count": len(klines),
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取 xtdata kline 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/status")
async def get_xtdata_status() -> Dict[str, Any]:
    """
    获取 xtdata 连接状态
    
    Returns:
        xtdata 可用性状态
    """
    try:
        from xtquant import xtdata

        # 尝试获取一只股票来验证连接
        test_result = xtdata.get_full_tick(["000001.SZ"])
        connected = bool(test_result and "000001.SZ" in test_result)

        return {
            "success": True,
            "xtdata_available": True,
            "connected": connected,
            "message": "xtdata 已连接" if connected else "xtdata 可用但未获取到数据",
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        return {
            "success": False,
            "xtdata_available": False,
            "connected": False,
            "message": "xtquant SDK 未安装",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "success": False,
            "xtdata_available": True,
            "connected": False,
            "message": f"xtdata 连接错误: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


# ==================== 板块和股票列表端点 ====================

@router.get("/xtdata/sectors")
async def get_sectors() -> Dict[str, Any]:
    """
    获取所有板块列表
    
    Returns:
        板块列表，包含板块名称和代码
    """
    try:
        from xtquant import xtdata

        result = xtdata.get_sector_list()

        if not result:
            return {
                "success": False,
                "message": "未获取到板块数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 格式化数据
        sectors = []
        if isinstance(result, list):
            for sector in result:
                if isinstance(sector, str):
                    sectors.append({"name": sector, "code": sector})
                elif isinstance(sector, dict):
                    sectors.append(sector)

        return {
            "success": True,
            "data": sectors,
            "count": len(sectors),
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取板块列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/sector/stocks")
async def get_sector_stocks(
        sector: str = Query(..., description="板块名称，如: 沪深A股, 上证50, 中证500")
) -> Dict[str, Any]:
    """
    获取板块成分股
    
    Args:
        sector: 板块名称
    
    Returns:
        板块内的股票代码列表
    """
    try:
        from xtquant import xtdata

        result = xtdata.get_stock_list_in_sector(sector)

        if not result:
            return {
                "success": False,
                "message": f"未获取到板块 '{sector}' 的成分股",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "sector": sector,
            "data": result if isinstance(result, list) else list(result),
            "count": len(result),
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取板块成分股失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/instrument")
async def get_instrument_info(
        symbol: str = Query(..., description="股票代码，如: 000001.SZ")
) -> Dict[str, Any]:
    """
    获取合约/股票详细信息
    
    Args:
        symbol: 股票代码
    
    Returns:
        合约详细信息，包含名称、上市日期、板块等
    """
    try:
        from xtquant import xtdata

        result = xtdata.get_instrument_detail(symbol)

        if not result:
            return {
                "success": False,
                "message": f"未获取到 '{symbol}' 的合约信息",
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "symbol": symbol,
            "data": result if isinstance(result, dict) else {"raw": result},
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取合约信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/instruments")
async def get_instruments_batch(
        symbols: str = Query(..., description="股票代码列表，逗号分隔")
) -> Dict[str, Any]:
    """
    批量获取合约详细信息
    
    Args:
        symbols: 股票代码列表（逗号分隔）
    
    Returns:
        多个合约的详细信息
    """
    try:
        from xtquant import xtdata

        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="请提供股票代码")

        result = xtdata.get_instrument_detail_list(symbol_list)

        if not result:
            return {
                "success": False,
                "message": "未获取到合约信息",
                "data": {},
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "data": result if isinstance(result, dict) else {"raw": result},
            "count": len(result) if isinstance(result, dict) else 0,
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"批量获取合约信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 交易日历端点 ====================

@router.get("/xtdata/trading-dates")
async def get_trading_dates(
        market: str = Query("SH", description="市场代码: SH, SZ"),
        start_date: str = Query("", description="开始日期，格式: 20240101"),
        end_date: str = Query("", description="结束日期，格式: 20241231"),
) -> Dict[str, Any]:
    """
    获取交易日期列表
    
    Args:
        market: 市场代码
        start_date: 开始日期
        end_date: 结束日期
    
    Returns:
        交易日期列表
    """
    try:
        from xtquant import xtdata

        result = xtdata.get_trading_dates(market, start_time=start_date, end_time=end_date)

        if not result:
            return {
                "success": False,
                "message": "未获取到交易日期数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 转换时间戳为日期字符串
        dates = []
        for ts in result:
            if isinstance(ts, (int, float)):
                try:
                    dt = datetime.fromtimestamp(ts / 1000 if ts > 1e10 else ts)
                    dates.append(dt.strftime("%Y-%m-%d"))
                except Exception:
                    dates.append(str(ts))
            else:
                dates.append(str(ts))

        return {
            "success": True,
            "market": market,
            "data": dates,
            "count": len(dates),
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取交易日期失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/holidays")
async def get_holidays() -> Dict[str, Any]:
    """
    获取节假日列表
    
    Returns:
        节假日日期列表
    """
    try:
        from xtquant import xtdata

        result = xtdata.get_holidays()

        if not result:
            return {
                "success": False,
                "message": "未获取到节假日数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "data": result if isinstance(result, list) else list(result),
            "count": len(result),
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取节假日失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 财务数据端点 ====================

@router.get("/xtdata/financial")
async def get_financial_data(
        symbol: str = Query(..., description="股票代码"),
        table: str = Query("Balance",
                           description="财务表类型: Balance(资产负债表), Income(利润表), CashFlow(现金流量表)"),
) -> Dict[str, Any]:
    """
    获取财务数据
    
    Args:
        symbol: 股票代码
        table: 财务报表类型
    
    Returns:
        财务数据
    """
    try:
        from xtquant import xtdata

        # 先尝试下载财务数据
        try:
            xtdata.download_financial_data([symbol])
        except Exception:
            pass  # 忽略下载错误

        result = xtdata.get_financial_data([symbol], [table])

        if not result:
            return {
                "success": False,
                "message": f"未获取到 '{symbol}' 的财务数据",
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "symbol": symbol,
            "table": table,
            "data": result,
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取财务数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ETF 和指数端点 ====================

@router.get("/xtdata/etf-info")
async def get_etf_info(
        symbol: str = Query(..., description="ETF 代码，如: 510050.SH")
) -> Dict[str, Any]:
    """
    获取 ETF 信息
    
    Args:
        symbol: ETF 代码
    
    Returns:
        ETF 详细信息
    """
    try:
        from xtquant import xtdata

        # 先下载 ETF 信息
        try:
            xtdata.download_etf_info()
        except Exception:
            pass

        result = xtdata.get_etf_info(symbol)

        if not result:
            return {
                "success": False,
                "message": f"未获取到 '{symbol}' 的 ETF 信息",
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "symbol": symbol,
            "data": result,
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取 ETF 信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/index-weight")
async def get_index_weight(
        index: str = Query(..., description="指数代码，如: 000300.SH (沪深300)")
) -> Dict[str, Any]:
    """
    获取指数成分股权重
    
    Args:
        index: 指数代码
    
    Returns:
        指数成分股及其权重
    """
    try:
        from xtquant import xtdata

        # 先下载指数权重数据
        try:
            xtdata.download_index_weight()
        except Exception:
            pass

        result = xtdata.get_index_weight(index)

        if not result:
            return {
                "success": False,
                "message": f"未获取到 '{index}' 的权重数据",
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "index": index,
            "data": result,
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取指数权重失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 复权因子端点 ====================

@router.get("/xtdata/divid-factors")
async def get_divid_factors(
        symbol: str = Query(..., description="股票代码")
) -> Dict[str, Any]:
    """
    获取复权因子
    
    Args:
        symbol: 股票代码
    
    Returns:
        复权因子数据
    """
    try:
        from xtquant import xtdata

        result = xtdata.get_divid_factors(symbol)

        if not result:
            return {
                "success": False,
                "message": f"未获取到 '{symbol}' 的复权因子",
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "symbol": symbol,
            "data": result,
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取复权因子失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 市场信息端点 ====================

@router.get("/xtdata/markets")
async def get_markets() -> Dict[str, Any]:
    """
    获取所有市场列表
    
    Returns:
        市场代码列表
    """
    try:
        from xtquant import xtdata

        result = xtdata.get_markets()

        return {
            "success": True,
            "data": result if result else [],
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取市场列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/periods")
async def get_period_list() -> Dict[str, Any]:
    """
    获取支持的 K 线周期列表
    
    Returns:
        周期列表
    """
    try:
        from xtquant import xtdata

        result = xtdata.get_period_list()

        return {
            "success": True,
            "data": result if result else [],
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="xtquant SDK 未安装")
    except Exception as e:
        logger.error(f"获取周期列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
