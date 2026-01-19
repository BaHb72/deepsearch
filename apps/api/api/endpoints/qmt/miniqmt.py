"""
MiniQMT API 端点

提供 MiniQMT 数据源的 REST API 接口
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.infrastructure.providers.implementations.qmt.miniqmt import MiniQMTProvider

# 兼容新旧管理器
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

try:
    from core.utils.data_sources import DataSourceManager
except ImportError:
    DataSourceManager = None  # type: ignore[assignment, misc]

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


async def get_miniqmt_provider() -> Any:
    """获取 MiniQMT Actor 实例（通过 Dask Actor）"""
    from apps.api.api.providers import DataProviderFactory, DataSourceType

    try:
        provider = await DataProviderFactory.get_provider_async(DataSourceType.MINIQMT)
        if provider is None:
            raise HTTPException(status_code=503, detail="MiniQMT Actor 不可用")
        return provider
    except Exception as e:
        logger.error(f"获取 MiniQMT Actor 失败: {e}")
        raise HTTPException(status_code=503, detail=f"MiniQMT 服务不可用: {e}")


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """
    获取 MiniQMT 连接状态

    Returns:
        连接状态信息
    """
    try:
        provider = await get_miniqmt_provider()
        # Actor 使用 get_status() 方法
        status = await provider.get_status()
        status["timestamp"] = datetime.now().isoformat()
        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 MiniQMT 状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe")
async def subscribe_symbols(request: SubscribeRequest) -> Dict[str, Any]:
    """
    订阅股票行情

    注意: MiniQMT 的 xtdata 接口不需要显式订阅，数据会自动推送。
    此接口主要用于触发数据下载和验证股票代码是否有效。

    Args:
        request: 订阅请求

    Returns:
        订阅结果
    """
    try:
        provider = await get_miniqmt_provider()

        # xtdata 不需要显式订阅，但我们可以预下载数据并验证
        valid_symbols = []
        invalid_symbols = []

        for symbol in request.symbols:
            try:
                # 通过 Actor 调用 xtdata.get_full_tick 验证股票有效性
                result = await provider.call("get_full_tick", stock_list=[symbol])
                if result and symbol in result:
                    valid_symbols.append(symbol)
                else:
                    # 尝试下载历史数据
                    await provider.call(
                        "download_history_data", stock_code=symbol, period="1d", count=1
                    )
                    valid_symbols.append(symbol)
            except Exception:
                invalid_symbols.append(symbol)

        return {
            "success": len(valid_symbols) > 0,
            "message": f"成功订阅 {len(valid_symbols)} 只股票"
            + (f"，{len(invalid_symbols)} 只无效" if invalid_symbols else ""),
            "symbols": valid_symbols,
            "invalid_symbols": invalid_symbols if invalid_symbols else None,
            "timestamp": datetime.now().isoformat(),
            "note": "MiniQMT 使用 xtdata 接口，数据会自动推送，无需显式订阅",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"订阅股票失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unsubscribe")
async def unsubscribe_symbols(request: UnsubscribeRequest) -> Dict[str, Any]:
    """
    取消订阅股票行情

    注意: MiniQMT 的 xtdata 接口使用按需获取模式，不需要显式取消订阅。
    此接口仅作为兼容性保留。

    Args:
        request: 取消订阅请求

    Returns:
        取消订阅结果
    """
    # xtdata 不需要显式取消订阅，返回成功即可
    return {
        "success": True,
        "message": f"已取消订阅 {len(request.symbols)} 只股票",
        "symbols": request.symbols,
        "timestamp": datetime.now().isoformat(),
        "note": "MiniQMT 使用按需获取模式，无需显式取消订阅",
    }


@router.get("/realtime")
async def get_realtime_data(
    symbols: str = Query(..., description="股票代码，逗号分隔")
) -> Dict[str, Any]:
    """
    获取实时行情数据

    通过 Actor 调用 xtdata 获取实时 tick 数据。

    Args:
        symbols: 股票代码列表（逗号分隔）

    Returns:
        实时行情数据
    """
    try:
        provider = await get_miniqmt_provider()

        # 解析股票列表
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]

        if not symbol_list:
            raise HTTPException(status_code=400, detail="请提供股票代码")

        # 通过 Actor 调用 xtdata.get_full_tick
        result = await provider.call("get_full_tick", stock_list=symbol_list)

        if not result:
            return {
                "success": False,
                "message": "未获取到数据，请确认 MiniQMT 终端已启动",
                "data": [],
                "symbols": symbol_list,
                "timestamp": datetime.now().isoformat(),
            }

        # 转换为列表格式
        data = []
        for symbol, tick in result.items():
            if isinstance(tick, dict):
                last_price = tick.get("lastPrice", 0)
                pre_close = tick.get("preClose", 0)
                change = last_price - pre_close if last_price and pre_close else 0
                change_pct = (change / pre_close * 100) if pre_close else 0

                data.append(
                    {
                        "symbol": symbol,
                        "lastPrice": last_price,
                        "change": round(change, 2),
                        "changePct": round(change_pct, 2),
                        "open": tick.get("open"),
                        "high": tick.get("high"),
                        "low": tick.get("low"),
                        "preClose": pre_close,
                        "volume": tick.get("volume"),
                        "amount": tick.get("amount"),
                        "time": tick.get("time"),
                    }
                )

        return {
            "success": True,
            "data": data,
            "count": len(data),
            "symbols": symbol_list,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实时数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_history_data(
    symbol: str = Query(..., description="股票代码"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYYMMDD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYYMMDD)"),
    period: str = Query("1d", description="周期: 1m, 5m, 15m, 30m, 60m, 1d"),
    count: int = Query(100, description="获取条数（当不指定日期范围时使用）"),
) -> Dict[str, Any]:
    """
    获取历史K线数据

    Args:
        symbol: 股票代码
        start_date: 开始日期 (YYYYMMDD 格式)
        end_date: 结束日期 (YYYYMMDD 格式)
        period: K线周期
        count: 获取条数

    Returns:
        历史K线数据
    """
    try:
        import math

        provider = await get_miniqmt_provider()

        # 尝试下载数据
        try:
            await provider.call("download_history_data", stock_code=symbol, period=period, count=-1)
        except Exception:
            pass

        # 通过 Actor 调用 xtdata.get_market_data
        result = await provider.call(
            "get_market_data",
            field_list=[],
            stock_list=[symbol],
            period=period,
            count=count,
            start_time=start_date or "",
            end_time=end_date or "",
        )

        if not isinstance(result, dict) or not result:
            return {
                "success": False,
                "message": "未获取到历史数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # Actor 已将 DataFrame 转换为 list[dict] 格式
        # 格式: {field: [{"index": symbol, "time1": val1, "time2": val2, ...}]}
        open_records = result.get("open", [])
        high_records = result.get("high", [])
        low_records = result.get("low", [])
        close_records = result.get("close", [])
        volume_records = result.get("volume", [])
        amount_records = result.get("amount", [])

        if not open_records:
            return {
                "success": False,
                "message": "K线数据为空，可能需要先下载历史数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 从记录中提取目标股票的数据
        def find_symbol_record(records: list, target_symbol: str) -> dict:
            for rec in records:
                if rec.get("index") == target_symbol:
                    return rec
            return {}

        open_rec = find_symbol_record(open_records, symbol)
        high_rec = find_symbol_record(high_records, symbol)
        low_rec = find_symbol_record(low_records, symbol)
        close_rec = find_symbol_record(close_records, symbol)
        volume_rec = find_symbol_record(volume_records, symbol)
        amount_rec = find_symbol_record(amount_records, symbol)

        if not open_rec:
            return {
                "success": False,
                "message": f"未找到股票 {symbol} 的数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 提取时间列（排除 index 列）
        time_keys = [k for k in open_rec.keys() if k != "index"]
        time_keys.sort()  # 按时间排序

        data = []
        for time_str in time_keys:
            try:
                if isinstance(time_str, str) and len(time_str) == 8:
                    ts = int(datetime.strptime(time_str, "%Y%m%d").timestamp() * 1000)
                elif isinstance(time_str, (int, float)):
                    ts = int(time_str)
                else:
                    ts = int(datetime.strptime(str(time_str), "%Y%m%d").timestamp() * 1000)
            except Exception:
                ts = 0

            def safe_float(val: Any) -> float:
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return 0.0
                return float(val)

            def safe_int(val: Any) -> int:
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return 0
                return int(val)

            data.append(
                {
                    "time": ts,
                    "time_str": str(time_str),
                    "open": safe_float(open_rec.get(time_str)),
                    "high": safe_float(high_rec.get(time_str)),
                    "low": safe_float(low_rec.get(time_str)),
                    "close": safe_float(close_rec.get(time_str)),
                    "volume": safe_int(volume_rec.get(time_str)),
                    "amount": safe_float(amount_rec.get(time_str)),
                }
            )

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取历史数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/minute")
async def get_minute_data(
    symbol: str = Query(..., description="股票代码"),
    date: Optional[str] = Query(None, description="日期 (YYYYMMDD)"),
    period: str = Query("1m", description="分钟周期: 1m, 5m, 15m, 30m, 60m"),
    count: int = Query(240, description="获取条数"),
) -> Dict[str, Any]:
    """
    获取分钟K线数据

    Args:
        symbol: 股票代码
        date: 日期 (YYYYMMDD 格式)
        period: 分钟周期（1m, 5m, 15m, 30m, 60m）
        count: 获取条数

    Returns:
        分钟K线数据
    """
    try:
        import math

        provider = await get_miniqmt_provider()

        # 尝试下载数据
        try:
            await provider.call("download_history_data", stock_code=symbol, period=period, count=-1)
        except Exception:
            pass

        # 通过 Actor 调用 xtdata.get_market_data
        result = await provider.call(
            "get_market_data",
            field_list=[],
            stock_list=[symbol],
            period=period,
            count=count,
            start_time=date or "",
            end_time=date or "",
        )

        if not isinstance(result, dict) or not result:
            return {
                "success": False,
                "message": "未获取到分钟数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # Actor 已将 DataFrame 转换为 list[dict] 格式
        open_records = result.get("open", [])
        high_records = result.get("high", [])
        low_records = result.get("low", [])
        close_records = result.get("close", [])
        volume_records = result.get("volume", [])
        amount_records = result.get("amount", [])

        if not open_records:
            return {
                "success": False,
                "message": "分钟K线数据为空",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 从记录中提取目标股票的数据
        def find_symbol_record(records: list, target_symbol: str) -> dict:
            for rec in records:
                if rec.get("index") == target_symbol:
                    return rec
            return {}

        open_rec = find_symbol_record(open_records, symbol)
        high_rec = find_symbol_record(high_records, symbol)
        low_rec = find_symbol_record(low_records, symbol)
        close_rec = find_symbol_record(close_records, symbol)
        volume_rec = find_symbol_record(volume_records, symbol)
        amount_rec = find_symbol_record(amount_records, symbol)

        if not open_rec:
            return {
                "success": False,
                "message": f"未找到股票 {symbol} 的数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 提取时间列（排除 index 列）
        time_keys = [k for k in open_rec.keys() if k != "index"]
        time_keys.sort()  # 按时间排序

        data = []
        for time_val in time_keys:
            # 分钟数据的时间戳格式可能是 YYYYMMDDHHmmss 或时间戳
            try:
                time_str = str(time_val)
                if len(time_str) == 14:  # YYYYMMDDHHmmss
                    ts = int(datetime.strptime(time_str, "%Y%m%d%H%M%S").timestamp() * 1000)
                elif len(time_str) == 12:  # YYYYMMDDHHmm
                    ts = int(datetime.strptime(time_str, "%Y%m%d%H%M").timestamp() * 1000)
                elif time_str.isdigit():
                    ts = int(time_str)
                else:
                    ts = 0
            except Exception:
                ts = int(time_val) if isinstance(time_val, (int, float)) else 0

            def safe_float(val: Any) -> float:
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return 0.0
                return float(val)

            def safe_int(val: Any) -> int:
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return 0
                return int(val)

            data.append(
                {
                    "time": ts,
                    "time_str": str(time_val),
                    "open": safe_float(open_rec.get(time_val)),
                    "high": safe_float(high_rec.get(time_val)),
                    "low": safe_float(low_rec.get(time_val)),
                    "close": safe_float(close_rec.get(time_val)),
                    "volume": safe_int(volume_rec.get(time_val)),
                    "amount": safe_float(amount_rec.get(time_val)),
                }
            )

        return {
            "success": True,
            "data": data,
            "count": len(data),
            "symbol": symbol,
            "period": period,
            "date": date,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分钟数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconnect")
async def reconnect() -> Dict[str, Any]:
    """
    重新连接 MiniQMT

    通过 Actor 重新初始化连接。

    Returns:
        重连结果
    """
    try:
        # 获取 Actor
        provider = await get_miniqmt_provider()

        # 先关闭现有连接
        try:
            await provider.shutdown()
        except Exception as shutdown_err:
            logger.warning(f"关闭 Actor 时出错（可忽略）: {shutdown_err}")

        # 重新初始化
        init_success = await provider.initialize()

        if init_success:
            # 使用 heartbeat 验证连接
            connected = await provider.heartbeat()
            status = await provider.get_status()

            return {
                "success": connected,
                "message": (
                    "成功重新连接到 MiniQMT" if connected else "MiniQMT Actor 已重启但连接状态异常"
                ),
                "actor_status": status,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "success": False,
                "message": "MiniQMT Actor 初始化失败",
                "timestamp": datetime.now().isoformat(),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新连接失败: {e}")
        return {
            "success": False,
            "message": f"重新连接失败: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/subscriptions")
async def get_subscriptions() -> Dict[str, Any]:
    """
    获取当前订阅列表

    Returns:
        订阅的股票列表
    """
    try:
        provider = await get_miniqmt_provider()
        # Actor 通过 get_status 返回状态
        status = await provider.get_status()

        return {
            "success": True,
            "subscribed_symbols": [],  # Actor 暂不支持订阅
            "count": 0,
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
        provider = await get_miniqmt_provider()
        # Actor 使用 get_status 返回包含统计信息的状态
        status = await provider.get_status()

        return {"success": True, "statistics": status, "timestamp": datetime.now().isoformat()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connection-guard")
async def get_connection_guard_status() -> Dict[str, Any]:
    """
    获取连接守卫状态

    返回连接状态管理器的当前状态，包括：
    - 服务是否可用
    - 上次检测时间
    - 连续失败次数
    - 被抑制的日志数量

    Returns:
        连接守卫状态信息
    """
    try:
        from core.infrastructure.providers.implementations.qmt.connection_guard import (
            MiniQMTConnectionGuard,
        )

        status = MiniQMTConnectionGuard.get_status()

        return {
            "success": True,
            "guard_status": status,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取连接守卫状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== xtdata 直接调用端点 ====================


@router.get("/xtdata/tick")
async def get_xtdata_tick(
    symbols: str = Query(..., description="股票代码，逗号分隔，如: 000001.SZ,600000.SH")
) -> Dict[str, Any]:
    """
    通过 Actor 获取 Tick 数据（含五档盘口）

    Args:
        symbols: 股票代码列表（逗号分隔）

    Returns:
        Tick 数据，包含最新价、涨跌、五档盘口等
    """
    try:
        provider = await get_miniqmt_provider()

        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="请提供股票代码")

        result = await provider.call("get_full_tick", stock_list=symbol_list)

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 xtdata tick 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/quote")
async def get_xtdata_quote(
    symbols: str = Query(..., description="股票代码，逗号分隔")
) -> Dict[str, Any]:
    """
    通过 Actor 获取简化的实时行情数据

    Args:
        symbols: 股票代码列表

    Returns:
        简化的行情数据
    """
    try:
        provider = await get_miniqmt_provider()

        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="请提供股票代码")

        result = await provider.call("get_full_tick", stock_list=symbol_list)

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

                quotes.append(
                    {
                        "symbol": symbol,
                        "name": symbol,
                        "lastPrice": last_price,
                        "change": round(change, 2),
                        "changePct": round(change_pct, 2),
                        "open": tick.get("open"),
                        "high": tick.get("high"),
                        "low": tick.get("low"),
                        "volume": tick.get("volume"),
                        "amount": tick.get("amount"),
                    }
                )

        return {
            "success": True,
            "data": quotes,
            "count": len(quotes),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
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
    通过 Actor 获取 K 线历史数据

    Args:
        symbol: 股票代码
        period: K线周期
        count: 获取条数

    Returns:
        K线数据列表
    """
    import math

    try:
        provider = await get_miniqmt_provider()

        # 先尝试下载数据
        try:
            await provider.call("download_history_data", stock_code=symbol, period=period, count=-1)
        except Exception:
            pass

        # 通过 Actor 获取 K 线数据
        result = await provider.call(
            "get_market_data",
            field_list=[],
            stock_list=[symbol],
            period=period,
            count=count,
        )

        if not isinstance(result, dict) or not result:
            return {
                "success": False,
                "message": "未获取到K线数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # Actor 已将 DataFrame 转换为 list[dict] 格式
        open_records = result.get("open", [])
        high_records = result.get("high", [])
        low_records = result.get("low", [])
        close_records = result.get("close", [])
        volume_records = result.get("volume", [])
        amount_records = result.get("amount", [])

        if not open_records:
            return {
                "success": False,
                "message": "K线数据为空，可能需要先下载历史数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 从记录中提取目标股票的数据
        def find_symbol_record(records: list, target_symbol: str) -> dict:
            for rec in records:
                if rec.get("index") == target_symbol:
                    return rec
            return {}

        open_rec = find_symbol_record(open_records, symbol)
        high_rec = find_symbol_record(high_records, symbol)
        low_rec = find_symbol_record(low_records, symbol)
        close_rec = find_symbol_record(close_records, symbol)
        volume_rec = find_symbol_record(volume_records, symbol)
        amount_rec = find_symbol_record(amount_records, symbol)

        if not open_rec:
            return {
                "success": False,
                "message": f"未找到股票 {symbol} 的数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 提取时间列
        time_keys = [k for k in open_rec.keys() if k != "index"]
        time_keys.sort()

        klines = []
        for time_str in time_keys:
            try:
                if isinstance(time_str, str) and len(time_str) == 8:
                    ts = int(datetime.strptime(time_str, "%Y%m%d").timestamp() * 1000)
                elif isinstance(time_str, (int, float)):
                    ts = int(time_str)
                else:
                    ts = int(datetime.strptime(str(time_str), "%Y%m%d").timestamp() * 1000)
            except Exception:
                ts = 0

            def safe_float(val: Any) -> float:
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return 0.0
                return float(val)

            def safe_int(val: Any) -> int:
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return 0
                return int(val)

            klines.append(
                {
                    "time": ts,
                    "time_str": str(time_str),
                    "open": safe_float(open_rec.get(time_str)),
                    "high": safe_float(high_rec.get(time_str)),
                    "low": safe_float(low_rec.get(time_str)),
                    "close": safe_float(close_rec.get(time_str)),
                    "volume": safe_int(volume_rec.get(time_str)),
                    "amount": safe_float(amount_rec.get(time_str)),
                }
            )

        return {
            "success": True,
            "symbol": symbol,
            "period": period,
            "data": klines,
            "count": len(klines),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 xtdata kline 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/status")
async def get_xtdata_status() -> Dict[str, Any]:
    """
    通过 Actor 获取 xtdata 连接状态

    Returns:
        xtdata 可用性状态
    """
    try:
        provider = await get_miniqmt_provider()

        # 使用 Actor 的 heartbeat 检测连接
        connected = await provider.heartbeat()
        status = await provider.get_status()

        return {
            "success": True,
            "xtdata_available": status.get("sdk_available", False),
            "connected": connected,
            "message": "xtdata 已连接" if connected else "xtdata 可用但未获取到数据",
            "actor_status": status,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "xtdata_available": False,
            "connected": False,
            "message": f"xtdata 连接错误: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


# ==================== 板块和股票列表端点 ====================


@router.get("/xtdata/sectors")
async def get_sectors() -> Dict[str, Any]:
    """
    通过 Actor 获取所有板块列表

    Returns:
        板块列表，包含板块名称和代码
    """
    try:
        provider = await get_miniqmt_provider()

        result = await provider.call("get_sector_list")

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取板块列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/sector/stocks")
async def get_sector_stocks(
    sector: str = Query(..., description="板块名称，如: 沪深A股, 上证50, 中证500")
) -> Dict[str, Any]:
    """
    通过 Actor 获取板块成分股

    Args:
        sector: 板块名称

    Returns:
        板块内的股票代码列表
    """
    try:
        provider = await get_miniqmt_provider()

        result = await provider.call("get_stock_list_in_sector", sector_name=sector)

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取板块成分股失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/instrument")
async def get_instrument_info(
    symbol: str = Query(..., description="股票代码，如: 000001.SZ")
) -> Dict[str, Any]:
    """
    通过 Actor 获取合约/股票详细信息

    Args:
        symbol: 股票代码

    Returns:
        合约详细信息，包含名称、上市日期、板块等
    """
    try:
        provider = await get_miniqmt_provider()

        result = await provider.call("get_instrument_detail", stock_code=symbol)

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取合约信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/instruments")
async def get_instruments_batch(
    symbols: str = Query(..., description="股票代码列表，逗号分隔")
) -> Dict[str, Any]:
    """
    通过 Actor 批量获取合约详细信息

    Args:
        symbols: 股票代码列表（逗号分隔）

    Returns:
        多个合约的详细信息
    """
    try:
        provider = await get_miniqmt_provider()

        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="请提供股票代码")

        result = await provider.call("get_instrument_detail_list", stock_list=symbol_list)

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

    except HTTPException:
        raise
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
    通过 Actor 获取交易日期列表

    Args:
        market: 市场代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        交易日期列表
    """
    try:
        provider = await get_miniqmt_provider()

        result = await provider.call(
            "get_trading_dates", market=market, start_time=start_date, end_time=end_date
        )

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取交易日期失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/holidays")
async def get_holidays() -> Dict[str, Any]:
    """
    通过 Actor 获取节假日列表

    Returns:
        节假日日期列表
    """
    try:
        provider = await get_miniqmt_provider()

        result = await provider.call("get_holidays")

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取节假日失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 财务数据端点 ====================


@router.get("/xtdata/financial")
async def get_financial_data(
    symbols: str = Query(..., description="股票代码列表，逗号分隔，如: 000001.SZ,600000.SH"),
    tables: Optional[str] = Query(
        None,
        description="财务表类型列表，逗号分隔: Balance(资产负债表), Income(利润表), CashFlow(现金流量表), Capital(股本), Holdernum(股东数), Top10holder(十大股东), Top10flowholder(十大流通股东), Pershareindex(每股指标)。为空获取三大报表",
    ),
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    report_type: str = Query(
        "report_time",
        description="报告类型: report_time(按截止日期), announce_time(按披露日期)",
    ),
    auto_download: bool = Query(True, description="是否自动下载数据到本地缓存"),
    timeout: int = Query(30, description="超时时间（秒）"),
) -> Dict[str, Any]:
    """
    获取财务数据（支持批量查询）

    注意: 此功能需要 MiniQMT 投研版 VIP 权限

    支持的财务表:
    - Balance: 资产负债表
    - Income: 利润表
    - CashFlow: 现金流量表
    - Capital: 股本结构表
    - Holdernum: 股东数
    - Top10holder: 十大股东
    - Top10flowholder: 十大流通股东
    - Pershareindex: 每股指标

    Args:
        symbols: 股票代码列表，逗号分隔
        tables: 财务表列表，逗号分隔（为空获取三大报表）
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        report_type: 报告类型
        auto_download: 是否自动下载
        timeout: 超时时间（秒）

    Returns:
        财务数据，格式: {symbol: {table: data}}
    """
    import asyncio

    try:
        provider = await get_miniqmt_provider()

        # 解析股票代码列表
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]

        # 解析财务表列表
        table_list = None
        if tables:
            table_list = [t.strip() for t in tables.split(",") if t.strip()]
        else:
            table_list = ["Balance", "Income", "CashFlow"]

        # 自动下载财务数据（带超时）
        if auto_download:
            try:
                await asyncio.wait_for(
                    provider.call(
                        "download_financial_data", stock_list=symbol_list, table_list=table_list
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"财务数据下载超时（{timeout}秒），将尝试读取缓存")
            except Exception as download_err:
                logger.warning(f"财务数据下载失败（将尝试读取缓存）: {download_err}")

        # 获取财务数据（带超时）
        try:
            result = await asyncio.wait_for(
                provider.call(
                    "get_financial_data",
                    stock_list=symbol_list,
                    table_list=table_list,
                    start_time=start_date or "",
                    end_time=end_date or "",
                    report_type=report_type,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return {
                "success": False,
                "message": f"获取财务数据超时（{timeout}秒），请稍后重试或减少查询范围",
                "symbols": symbol_list,
                "tables": table_list,
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        if not result:
            return {
                "success": False,
                "message": "未获取到财务数据，可能需要 VIP 权限",
                "symbols": symbol_list,
                "tables": table_list,
                "data": None,
                "timestamp": datetime.now().isoformat(),
                "note": "此功能需要 MiniQMT 投研版 VIP 权限",
            }

        # Actor 已将 DataFrame 转换为可序列化格式
        return {
            "success": True,
            "symbols": symbol_list,
            "tables": table_list,
            "symbol_count": len(result) if isinstance(result, dict) else 0,
            "data": result,
            "timestamp": datetime.now().isoformat(),
            "note": "此功能需要 MiniQMT 投研版 VIP 权限",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取财务数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ETF 和指数端点 ====================


@router.get("/xtdata/etf-info")
async def get_etf_info(
    symbol: str = Query(..., description="ETF 代码，如: 510050.SH"),
    timeout: int = Query(30, description="超时时间（秒）"),
) -> Dict[str, Any]:
    """
    获取 ETF 信息

    Args:
        symbol: ETF 代码
        timeout: 超时时间（秒）

    Returns:
        ETF 详细信息
    """
    import asyncio

    try:
        provider = await get_miniqmt_provider()

        # 先下载 ETF 信息（带超时）
        try:
            await asyncio.wait_for(
                provider.call("download_etf_info"),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"ETF 信息下载超时（{timeout}秒），将尝试读取缓存")
        except Exception:
            pass

        # 获取 ETF 信息（带超时）
        try:
            result = await asyncio.wait_for(
                provider.call("get_etf_info", fund_code=symbol),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return {
                "success": False,
                "message": f"获取 ETF 信息超时（{timeout}秒），请稍后重试",
                "symbol": symbol,
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 ETF 信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/index-weight")
async def get_index_weight(
    index: str = Query(..., description="指数代码，如: 000300.SH (沪深300)"),
    timeout: int = Query(30, description="超时时间（秒）"),
) -> Dict[str, Any]:
    """
    获取指数成分股权重

    Args:
        index: 指数代码
        timeout: 超时时间（秒）

    Returns:
        指数成分股及其权重
    """
    import asyncio

    try:
        provider = await get_miniqmt_provider()

        # 先下载指数权重数据（带超时）
        try:
            await asyncio.wait_for(
                provider.call("download_index_weight"),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"指数权重下载超时（{timeout}秒），将尝试读取缓存")
        except Exception:
            pass

        # 获取指数权重（带超时）
        try:
            result = await asyncio.wait_for(
                provider.call("get_index_weight", index_code=index),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return {
                "success": False,
                "message": f"获取指数权重超时（{timeout}秒），请稍后重试",
                "index": index,
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取指数权重失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 复权因子端点 ====================


@router.get("/xtdata/divid-factors")
async def get_divid_factors(symbol: str = Query(..., description="股票代码")) -> Dict[str, Any]:
    """
    获取复权因子

    Args:
        symbol: 股票代码

    Returns:
        复权因子数据
    """
    try:
        provider = await get_miniqmt_provider()

        # 通过 Actor 调用 xtdata.get_divid_factors
        result = await provider.call("get_divid_factors", stock_code=symbol)

        # 检查结果是否为空（处理 DataFrame/dict/None 等不同类型）
        import pandas as pd

        is_empty = (
            result is None
            or (isinstance(result, pd.DataFrame) and result.empty)
            or (isinstance(result, dict) and len(result) == 0)
            or (isinstance(result, list) and len(result) == 0)
        )

        if is_empty:
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取复权因子失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 市场信息端点 ====================


@router.get("/xtdata/markets")
async def get_markets() -> Dict[str, Any]:
    """
    通过 Actor 获取所有市场列表

    Returns:
        市场代码列表
    """
    try:
        provider = await get_miniqmt_provider()

        result = await provider.call("get_markets")

        return {
            "success": True,
            "data": result if result else [],
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取市场列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/periods")
async def get_period_list() -> Dict[str, Any]:
    """
    通过 Actor 获取支持的 K 线周期列表

    Returns:
        周期列表
    """
    try:
        provider = await get_miniqmt_provider()

        result = await provider.call("get_period_list")

        return {
            "success": True,
            "data": result if result else [],
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取周期列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 板块资金流向端点 ====================


@router.get("/xtdata/sector-capital-flow")
async def get_sector_capital_flow(
    indicator: str = Query("今日", description="时间周期: 今日, 5日, 10日"),
    sector_type: str = Query(
        "行业资金流", description="板块类型: 行业资金流, 概念资金流, 地域资金流"
    ),
) -> Dict[str, Any]:
    """
    获取板块资金流向排名

    使用 akshare 的 stock_sector_fund_flow_rank 接口获取数据

    Args:
        indicator: 时间周期 (今日/5日/10日)
        sector_type: 板块类型 (行业资金流/概念资金流/地域资金流)

    Returns:
        板块资金流向排名数据
    """
    try:
        import akshare as ak
        import pandas as pd

        # 调用 akshare 接口获取板块资金流向排名
        df = ak.stock_sector_fund_flow_rank(indicator=indicator, sector_type=sector_type)

        if df is None or df.empty:
            return {
                "success": False,
                "message": "未获取到板块资金流向数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 转换 DataFrame 为列表
        # 处理 NaN 和 Infinity 值
        df = df.replace([float("inf"), float("-inf")], None)
        df = df.where(pd.notnull(df), None)

        # 转换为 JSON 可序列化格式
        records = df.to_dict("records")

        # 清理 None 值和格式化数字
        cleaned_records = []
        for record in records:
            cleaned: Dict[str, Any] = {}
            for k, v in record.items():
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    cleaned[k] = None
                elif isinstance(v, float):
                    cleaned[k] = round(v, 4)
                else:
                    cleaned[k] = v
            cleaned_records.append(cleaned)

        return {
            "success": True,
            "indicator": indicator,
            "sector_type": sector_type,
            "data": cleaned_records,
            "count": len(cleaned_records),
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError:
        raise HTTPException(status_code=503, detail="akshare 未安装，请运行: pip install akshare")
    except Exception as e:
        logger.error(f"获取板块资金流向失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/stock-list")
async def get_stock_list(
    sector: str = Query("沪深A股", description="板块名称，默认沪深A股"),
    limit: int = Query(0, description="返回数量限制，0表示全部"),
    refresh: bool = Query(False, description="是否强制刷新缓存"),
) -> Dict[str, Any]:
    """
    获取股票列表（含名称和拼音首字母）

    从缓存读取，响应速度快。若缓存不存在则触发后台刷新。

    Args:
        sector: 板块名称，默认"沪深A股"
        limit: 返回数量限制，0表示全部
        refresh: 是否强制刷新缓存

    Returns:
        股票列表，包含 symbol, name, pinyin 字段
    """
    from apps.api.api.services.stock_cache import get_stock_list_from_cache, refresh_stock_cache

    try:
        # 强制刷新
        if refresh:
            logger.info(f"[StockList] 收到刷新请求: {sector}")
            # 异步刷新，不阻塞响应
            asyncio.create_task(refresh_stock_cache(sector))
            return {
                "success": True,
                "message": "缓存刷新任务已启动，请稍后重试获取",
                "sector": sector,
                "data": [],
                "count": 0,
                "refreshing": True,
                "timestamp": datetime.now().isoformat(),
            }

        # 从缓存读取
        cached = get_stock_list_from_cache(sector, limit)

        if cached is not None:
            return {
                "success": True,
                "sector": sector,
                "data": cached if limit <= 0 else cached[:limit],
                "count": len(cached) if limit <= 0 else min(limit, len(cached)),
                "cached": True,
                "timestamp": datetime.now().isoformat(),
            }

        # 缓存不存在，触发异步刷新并返回空
        logger.info(f"[StockList] 缓存不存在，触发刷新: {sector}")
        asyncio.create_task(refresh_stock_cache(sector))

        return {
            "success": True,
            "message": "缓存正在初始化，请稍后重试",
            "sector": sector,
            "data": [],
            "count": 0,
            "refreshing": True,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/sector/stocks-with-names")
async def get_sector_stocks_with_names(
    sector: str = Query(..., description="板块名称"),
) -> Dict[str, Any]:
    """
    通过 Actor 获取板块成分股（含股票名称）

    Args:
        sector: 板块名称

    Returns:
        成分股列表，包含 symbol 和 name
    """
    try:
        provider = await get_miniqmt_provider()

        # 获取板块内股票列表
        stock_list = await provider.call("get_stock_list_in_sector", sector_name=sector)

        if not stock_list:
            return {
                "success": False,
                "message": f"未获取到 {sector} 板块的成分股",
                "data": [],
                "count": 0,
                "timestamp": datetime.now().isoformat(),
            }

        # 批量获取股票名称
        result = []
        for symbol in stock_list:
            try:
                detail = await provider.call("get_instrument_detail", stock_code=symbol)
                name = detail.get("InstrumentName", symbol) if detail else symbol

                # 处理编码问题
                if name and isinstance(name, str):
                    try:
                        name = name.encode("latin1").decode("gbk")
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        pass

                result.append(
                    {
                        "symbol": symbol,
                        "name": name or symbol,
                    }
                )
            except Exception:
                result.append(
                    {
                        "symbol": symbol,
                        "name": symbol,
                    }
                )

        return {
            "success": True,
            "sector": sector,
            "data": result,
            "count": len(result),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取板块成分股失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
