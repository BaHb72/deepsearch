"""
QMT数据API端点
"""

import asyncio
import json
import time
from collections.abc import MutableSet, Sequence
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, cast, runtime_checkable

from core.config import get_config
from core.core.runtime.context import get_context
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from loguru import logger

if TYPE_CHECKING:
    from core.core.managers.component_manager import ComponentManager

router = APIRouter(prefix="/api/qmt", tags=["qmt"])


@runtime_checkable
class QMTGatewayReceiver(Protocol):
    """Minimum interface required for WebUI receiver usage."""

    def get_client_info(self) -> List[Dict[str, Any]]: ...

    def get_stats(self) -> Dict[str, Any]: ...


@runtime_checkable
class QMTGatewayLike(Protocol):
    """Interface abstraction for gateway implementations used by the WebUI."""

    subscribed_symbols: MutableSet[str]
    receiver: Optional[QMTGatewayReceiver]
    stats: Dict[str, Any]

    def get_status(self) -> Dict[str, Any]: ...

    def subscribe(self, symbols: Sequence[str]) -> Any: ...

    def unsubscribe(self, symbols: Sequence[str]) -> Any: ...

    def get_latest_tick(self, symbol: str) -> Optional[Dict[str, Any]]: ...

    def get_latest_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]: ...


def _ensure_gateway(candidate: Any) -> Optional[QMTGatewayLike]:
    """Validate candidate objects and narrow their type to QMTGatewayLike."""
    if candidate is None:
        return None
    required_attrs = (
        "subscribed_symbols",
        "receiver",
        "stats",
        "get_status",
        "subscribe",
        "unsubscribe",
        "get_latest_tick",
        "get_latest_orderbook",
    )
    if not all(hasattr(candidate, attr) for attr in required_attrs):
        return None
    return cast(QMTGatewayLike, candidate)


# 获取数据源配置
try:
    config = get_config()
    if hasattr(config, "data_providers") and config.data_providers:
        # 如果是对象，尝试转换为字典
        if hasattr(config.data_providers, "qmt_only"):
            QMT_ONLY_MODE = config.data_providers.qmt_only
        elif hasattr(config.data_providers, "__dict__"):
            QMT_ONLY_MODE = config.data_providers.__dict__.get("qmt_only", False)
        else:
            QMT_ONLY_MODE = False
    else:
        QMT_ONLY_MODE = False

    if QMT_ONLY_MODE:
        logger.info("QMT Only Mode 已启用 - 只使用QMT数据源")
except Exception as e:
    logger.warning(f"无法读取数据源配置: {e}")
    QMT_ONLY_MODE = False


def add_exchange_suffix(code: str) -> str:
    """根据股票代码自动添加交易所后缀"""
    if "." in code:
        return code
    if code.startswith("6"):
        return f"{code}.SH"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    return code


def get_qmt_service() -> Optional[QMTGatewayLike]:
    """获取QMT服务实例（可用于内部落地）"""
    return get_qmt_gateway()


def get_qmt_gateway() -> Optional[QMTGatewayLike]:
    """获取QMT服务实现"""
    try:
        context = get_context()
        manager: Optional["ComponentManager"] = None
        try:
            manager = context.get_component_manager()
        except AttributeError:
            manager_candidate = getattr(context, "_component_manager", None)
            if manager_candidate is not None:
                manager = cast("ComponentManager", manager_candidate)
        if manager is None:
            logger.warning("ComponentManager 未初始化或不可用，无法获取 qmt_gateway 组件")
            return None

        logger.debug("尝试从 ComponentManager 获取 qmt_gateway 组件...")
        component = manager.get_component("qmt_gateway")
    except (RuntimeError, ValueError) as exc:
        logger.debug(f"从 ComponentManager 获取 qmt_gateway 失败: {exc}")
        component = None
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(f"获取 QMT 网关失败: {exc}", exc_info=True)
        return None

    gateway = _ensure_gateway(component)
    if gateway is not None:
        logger.debug(f"使用组件 {type(component).__name__} 作为 QMT 网关实现")
        return gateway

    for attr in ("get_instance", "gateway", "_gateway"):
        if not hasattr(component, attr):
            continue
        candidate = getattr(component, attr)
        try:
            if attr == "get_instance" and callable(candidate):
                candidate = candidate()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"访问 {attr} 失败: {exc}")
            continue

        gateway = _ensure_gateway(candidate)
        if gateway is not None:
            logger.debug(f"通过 {attr} 获取到网关实现: {type(candidate).__name__}")
            return gateway

    logger.warning("未能找到符合接口的 QMT 网关实现")
    return None


@router.get("/status")
async def get_qmt_status():
    """获取QMT连接状态"""
    gateway = get_qmt_gateway()

    if not gateway:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": "QMT网关未启动",
                "data": {"running": False, "enabled": False},
            },
        )

    try:
        status = gateway.get_status()
        return {"status": "success", "data": status}
    except Exception as e:
        logger.error(f"获取QMT状态失败: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.post("/subscribe")
async def subscribe_symbols(symbols: List[str]):
    """
    订阅股票行情

    Args:
        symbols: 股票代码列表，如 ["000001.SZ", "600000.SH"]
    """
    gateway = get_qmt_gateway()

    if not gateway:
        raise HTTPException(status_code=503, detail="QMT网关未启动")

    try:
        # 智能添加交易所后缀
        # 转换所有股票代码格式
        formatted_symbols = [add_exchange_suffix(s) for s in symbols]
        if formatted_symbols != symbols:
            logger.info(f"股票代码格式转换: {symbols} -> {formatted_symbols}")

        # 先更新订阅管理器（这是真正的订阅源）
        from apps.api.api.endpoints.qmt.qmt_subscription import subscription_manager

        result = subscription_manager.update_subscription(formatted_symbols, action="add")
        logger.info(f"更新订阅管理器: {result}")

        # 然后更新gateway（用于内存缓存）
        gateway.subscribe(formatted_symbols)

        # 立即触发推送更新到所有客户端
        try:
            context = get_context()
            manager = getattr(context, "_component_manager", None)
            if manager is not None:
                receiver_comp = manager.get_component("qmt_receiver")
                receiver = getattr(receiver_comp, "receiver", None) if receiver_comp else None
                if receiver and hasattr(receiver, "push_subscription_updates"):
                    asyncio.create_task(receiver.push_subscription_updates())
                    logger.info(f"已通知接收端刷新订阅: {symbols}")
        except Exception as e:
            logger.warning(f"无法触发订阅刷新: {e}")

        return {
            "status": "success",
            "message": f"已订阅 {len(symbols)} 只股票",
            "data": {
                "symbols": symbols,
                "total": len(gateway.subscribed_symbols),
                "affected_clients": result.get("affected_clients", []),
                "global_subscribed": len(subscription_manager.global_symbols),
            },
        }
    except Exception as e:
        logger.error(f"订阅股票失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unsubscribe")
async def unsubscribe_symbols(symbols: List[str]):
    """
    取消订阅股票行情

    Args:
        symbols: 股票代码列表
    """
    gateway = get_qmt_gateway()

    if not gateway:
        raise HTTPException(status_code=503, detail="QMT网关未启动")

    try:
        # 更新gateway订阅列表
        gateway.unsubscribe(symbols)

        # 同步更新subscription_manager
        from apps.api.api.endpoints.qmt.qmt_subscription import subscription_manager

        result = subscription_manager.update_subscription(symbols, action="remove")
        logger.info(f"同步更新订阅管理器（取消订阅）: {result}")

        return {
            "status": "success",
            "message": f"已取消订阅 {len(symbols)} 只股票",
            "data": {
                "symbols": symbols,
                "total": len(gateway.subscribed_symbols),
                "affected_clients": result.get("affected_clients", []),
            },
        }
    except Exception as e:
        logger.error(f"取消订阅失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscribed")
async def get_subscribed_symbols():
    """获取已订阅的股票列表"""
    gateway = get_qmt_gateway()

    if not gateway:
        return {"status": "success", "data": {"symbols": [], "total": 0}}

    return {
        "status": "success",
        "data": {
            "symbols": list(gateway.subscribed_symbols),
            "total": len(gateway.subscribed_symbols),
        },
    }


@router.get("/tick/{symbol}")
async def get_latest_tick(symbol: str):
    """
    获取最新的Tick数据

    Args:
        symbol: 股票代码，如 "000001.SZ"
    """
    gateway = get_qmt_gateway()

    # 尝试从QMT获取数据
    if gateway:
        try:
            # 检查是否已订阅该股票
            if hasattr(gateway, "subscribed_symbols") and symbol not in gateway.subscribed_symbols:
                logger.info(f"股票 {symbol} 未订阅，自动订阅...")
                if hasattr(gateway, "subscribe"):
                    gateway.subscribe([symbol])
                    # 等待数据到达（最多等待2秒）
                    for i in range(20):  # 20次，每次100ms
                        await asyncio.sleep(0.1)
                        if hasattr(gateway, "get_latest_tick"):
                            tick = gateway.get_latest_tick(symbol)
                            if tick:
                                logger.info(f"成功获取 {symbol} 的QMT Tick数据")
                                return {"status": "success", "source": "qmt", "data": tick}
            else:
                # 已订阅，直接获取
                if hasattr(gateway, "get_latest_tick"):
                    tick = gateway.get_latest_tick(symbol)
                    if tick:
                        return {"status": "success", "source": "qmt", "data": tick}
        except Exception as e:
            logger.warning(f"从QMT获取Tick数据失败: {e}")

    # 检查是否只使用QMT模式
    if QMT_ONLY_MODE:
        logger.info("QMT Only Mode - 不尝试备用数据源")
        return {
            "status": "success",
            "source": "qmt",
            "message": "QMT数据源未返回数据",
            "data": {
                "symbol": symbol,
                "timestamp": int(time.time()),
                "last_price": 0,
                "volume": 0,
                "amount": 0,
            },
        }

    # QMT无数据，尝试从备用数据源获取
    logger.info(f"QMT无Tick数据，尝试从备用数据源获取 {symbol} 的实时数据...")

    try:
        # 尝试从统一数据源管理器获取
        from core.utils.data_sources import get_data_source_manager

        manager = get_data_source_manager()
        if not manager.initialized:
            await manager.initialize()

        snapshot = await manager.get_realtime_quote(symbol)

        if snapshot and snapshot.get("current"):
            # 转换为Tick格式
            return {
                "status": "success",
                "source": snapshot.get("source", "unified"),
                "message": "使用实时快照数据",
                "data": {
                    "symbol": symbol,
                    "name": snapshot.get("name", ""),
                    "last_price": snapshot.get("current", 0),
                    "pre_close": snapshot.get("prev_close", 0),
                    "open": snapshot.get("open", 0),
                    "high": snapshot.get("high", 0),
                    "low": snapshot.get("low", 0),
                    "volume": snapshot.get("volume", 0),
                    "amount": snapshot.get("amount", 0),
                    "change": snapshot.get("change", 0),
                    "pct_change": snapshot.get("change_pct", 0),
                    "timestamp": snapshot.get("timestamp", int(time.time())),
                },
            }
    except Exception as e:
        logger.warning(f"从备用数据源获取Tick失败: {e}")

    # 所有数据源都失败
    raise HTTPException(status_code=404, detail=f"未找到 {symbol} 的Tick数据")


@router.get("/orderbook/{symbol}")
async def get_latest_orderbook(symbol: str):
    """
    获取最新的盘口数据

    使用统一数据源管理器，按优先级尝试各数据源

    Args:
        symbol: 股票代码
    """
    logger.info(f"收到获取盘口数据请求: {symbol}")

    # 使用统一数据源管理器
    from core.utils.data_sources import get_data_source_manager

    try:
        data_source_manager = get_data_source_manager()
        if not data_source_manager.initialized:
            await data_source_manager.initialize()

        # 获取实时行情（包含盘口数据）
        result_raw = await data_source_manager.get_realtime_quote(symbol)
        result_data = result_raw if isinstance(result_raw, dict) else None

        if result_data is not None and not result_data.get("error"):
            # 格式化为盘口数据格式
            orderbook_data = {
                "symbol": symbol,
                "timestamp": result_data.get("timestamp", int(time.time())),
                "bid_levels": [],
                "ask_levels": [],
            }

            # 读取盘口数据
            bid_prices = result_data.get("bid_price", [])
            bid_volumes = result_data.get("bid_volume", [])
            ask_prices = result_data.get("ask_price", [])
            ask_volumes = result_data.get("ask_volume", [])

            # 构建盘口档位
            for i in range(min(5, len(bid_prices))):
                if i < len(bid_volumes):
                    orderbook_data["bid_levels"].append(
                        {"price": bid_prices[i], "volume": bid_volumes[i]}
                    )

            for i in range(min(5, len(ask_prices))):
                if i < len(ask_volumes):
                    orderbook_data["ask_levels"].append(
                        {"price": ask_prices[i], "volume": ask_volumes[i]}
                    )

            return {
                "status": "success",
                "source": result_data.get("_source", "unknown"),
                "data": orderbook_data,
            }
        else:
            error_msg = (
                result_data.get("error", "获取数据失败")
                if isinstance(result_data, dict)
                else "获取数据失败"
            )
            logger.warning(f"获取盘口数据失败: {error_msg}")
            return {
                "status": "error",
                "source": "unified",
                "message": error_msg,
                "data": {
                    "symbol": symbol,
                    "timestamp": int(time.time()),
                    "bid_levels": [],
                    "ask_levels": [],
                },
            }

    except Exception as e:
        logger.error(f"获取盘口数据异常: {e}")
        return {
            "status": "error",
            "source": "unified",
            "message": str(e),
            "data": {
                "symbol": symbol,
                "timestamp": int(time.time()),
                "bid_levels": [],
                "ask_levels": [],
            },
        }

    gateway = get_qmt_gateway()
    if not gateway:
        return {
            "status": "error",
            "source": "qmt",
            "message": "QMT����δ����",
            "data": {
                "symbol": symbol,
                "timestamp": int(time.time()),
                "bid_levels": [],
                "ask_levels": [],
            },
        }

    formatted_symbol = add_exchange_suffix(symbol)

    try:
        # 检查是否已订阅该股票（使用格式化后的代码）
        if hasattr(gateway, "subscribed_symbols"):
            # 同时检查原始代码和格式化代码
            if (
                formatted_symbol not in gateway.subscribed_symbols
                and symbol not in gateway.subscribed_symbols
            ):
                logger.info(f"股票 {formatted_symbol} 未订阅，自动订阅...")
                if hasattr(gateway, "subscribe"):
                    gateway.subscribe([formatted_symbol])
                    # 等待数据到达（最多等待2秒）
                    for i in range(20):  # 20次，每次100ms
                        await asyncio.sleep(0.1)
                        if hasattr(gateway, "get_latest_orderbook"):
                            # 尝试使用格式化代码获取
                            orderbook = gateway.get_latest_orderbook(formatted_symbol)
                            if not orderbook and formatted_symbol != symbol:
                                # 如果失败，尝试原始代码
                                orderbook = gateway.get_latest_orderbook(symbol)

                            if orderbook:
                                logger.info(f"成功获取 {formatted_symbol} 的QMT盘口数据")
                                return {"status": "success", "source": "qmt", "data": orderbook}

        # 直接获取盘口数据（先尝试格式化代码，再尝试原始代码）
        if hasattr(gateway, "get_latest_orderbook"):
            logger.debug(f"调用 gateway.get_latest_orderbook({formatted_symbol})")
            orderbook = gateway.get_latest_orderbook(formatted_symbol)

            # 如果格式化代码失败，尝试原始代码
            if not orderbook and formatted_symbol != symbol:
                logger.debug(f"格式化代码无数据，尝试原始代码: {symbol}")
                orderbook = gateway.get_latest_orderbook(symbol)

            if orderbook:
                logger.info(f"成功获取QMT盘口数据: {formatted_symbol}")
                return {"status": "success", "source": "qmt", "data": orderbook}
            else:
                logger.debug(f"QMT暂无 {formatted_symbol} 的盘口数据")

    except Exception as e:
        logger.error(f"从QMT获取盘口数据异常: {e}")
        return {
            "status": "error",
            "source": "qmt",
            "message": str(e),
            "data": {
                "symbol": symbol,
                "timestamp": int(time.time()),
                "bid_levels": [],
                "ask_levels": [],
            },
        }

    # QMT没有数据（正常情况，可能未收到推送）
    return {
        "status": "warning",
        "source": "qmt",
        "message": "暂无数据（等待QMT推送）",
        "data": {
            "symbol": symbol,
            "timestamp": int(time.time()),
            "bid_levels": [],
            "ask_levels": [],
        },
    }


@router.get("/trades/{symbol}")
async def get_trade_details(symbol: str, limit: int = Query(20, ge=1, le=100)):
    """
    获取股票交易明细

    Args:
        symbol: 股票代码
        limit: 返回记录数限制
    """
    gateway = get_qmt_gateway()

    # 如果QMT网关未启动，返回空数据而不是错误
    if not gateway:
        logger.debug(f"QMT网关未启动，返回空交易明细数据: {symbol}")
        return {"status": "success", "message": "QMT未连接", "data": []}

    # 尝试从网关获取交易明细
    try:
        # 如果网关有get_trade_details方法，调用它
        if hasattr(gateway, "get_trade_details"):
            trades = gateway.get_trade_details(symbol, limit)
            return {"status": "success", "data": trades}
        else:
            # 返回模拟数据或空数据
            logger.debug(f"QMT网关不支持交易明细，返回空数据: {symbol}")
            return {"status": "success", "message": "交易明细功能未实现", "data": []}
    except Exception as e:
        logger.error(f"获取交易明细失败 {symbol}: {e}")
        # 返回空数据而不是抛出异常
        return {"status": "success", "message": f"获取失败: {str(e)}", "data": []}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket实时数据推送

    客户端消息格式：
    {
        "action": "subscribe" | "unsubscribe",
        "symbols": ["000001.SZ", "600000.SH"]
    }

    服务端推送格式：
    {
        "type": "tick" | "orderbook" | "trade",
        "data": {...}
    }
    """
    await websocket.accept()

    gateway = get_qmt_gateway()
    if not gateway:
        await websocket.send_json({"type": "error", "message": "QMT网关未启动"})
        await websocket.close()
        return

    client_id = f"ws_{id(websocket)}"
    subscribed_symbols: set[str] = set()

    logger.info(f"WebSocket客户端连接: {client_id}")

    try:
        # 发送初始状态
        await websocket.send_json(
            {"type": "connected", "data": {"client_id": client_id, "status": gateway.get_status()}}
        )

        # 创建数据推送任务
        async def push_data():
            """推送实时数据到WebSocket"""
            while True:
                try:
                    # 推送订阅股票的最新数据
                    for symbol in subscribed_symbols:
                        # 获取最新Tick
                        tick = gateway.get_latest_tick(symbol)
                        if tick:
                            await websocket.send_json({"type": "tick", "data": tick})

                        # 获取最新盘口
                        orderbook = gateway.get_latest_orderbook(symbol)
                        if orderbook:
                            await websocket.send_json({"type": "orderbook", "data": orderbook})

                    # 控制推送频率
                    await asyncio.sleep(0.1)  # 100ms

                except Exception as e:
                    logger.error(f"推送数据失败: {e}")
                    break

        # 启动推送任务
        push_task = asyncio.create_task(push_data())

        # 处理客户端消息
        try:
            while True:
                try:
                    # 接收客户端消息
                    data = await websocket.receive_text()
                    msg = json.loads(data)

                    action = msg.get("action")
                    symbols = msg.get("symbols", [])

                    if action == "subscribe":
                        # 订阅股票
                        for symbol in symbols:
                            subscribed_symbols.add(symbol)

                        await websocket.send_json(
                            {
                                "type": "subscribed",
                                "data": {"symbols": symbols, "total": len(subscribed_symbols)},
                            }
                        )

                    elif action == "unsubscribe":
                        # 取消订阅
                        for symbol in symbols:
                            subscribed_symbols.discard(symbol)

                        await websocket.send_json(
                            {
                                "type": "unsubscribed",
                                "data": {"symbols": symbols, "total": len(subscribed_symbols)},
                            }
                        )

                    elif action == "ping":
                        # 心跳
                        await websocket.send_json(
                            {"type": "pong", "timestamp": asyncio.get_event_loop().time()}
                        )

                except WebSocketDisconnect:
                    break
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                except Exception as e:
                    logger.error(f"处理WebSocket消息失败: {e}")
                    break
        finally:
            # 正确取消并等待推送任务完成
            push_task.cancel()
            try:
                await push_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"推送任务取消时发生异常: {e}")

    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
    finally:
        logger.info(f"WebSocket客户端断开: {client_id}")


@router.get("/clients")
async def get_connected_clients():
    """获取连接的QMT客户端信息"""
    gateway = get_qmt_gateway()

    if not gateway or not gateway.receiver:
        return {"status": "success", "data": {"clients": [], "total": 0}}

    clients = gateway.receiver.get_client_info()

    return {"status": "success", "data": {"clients": clients, "total": len(clients)}}


@router.get("/statistics")
async def get_statistics():
    """获取QMT数据统计信息"""
    gateway = get_qmt_gateway()

    if not gateway:
        return {"status": "success", "data": {"gateway": None, "receiver": None}}

    return {
        "status": "success",
        "data": {
            "gateway": gateway.stats,
            "receiver": gateway.receiver.get_stats() if gateway.receiver else None,
        },
    }


# ================== MiniQMT 板块数据 API ==================


async def _get_miniqmt_provider():
    """获取MiniQMT provider实例"""
    from apps.api.api.providers import DataProviderFactory, DataSourceType

    try:
        provider = await DataProviderFactory.get_provider_async(DataSourceType.MINIQMT)
        if provider is None:
            return None
        return provider
    except Exception as e:
        logger.error(f"获取MiniQMT provider失败: {e}")
        return None


@router.get("/calendar", summary="获取交易日历")
async def get_trading_calendar(
    market: str = Query("SH", description="市场类型，SH/SZ"),
    start_date: str = Query(..., description="开始日期，格式YYYYMMDD"),
    end_date: str = Query(..., description="结束日期，格式YYYYMMDD"),
):
    """
    获取交易日历

    通过 xtquant SDK 获取指定市场的交易日历

    Args:
        market: 市场类型，SH或SZ
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        交易日期列表
    """
    provider = await _get_miniqmt_provider()

    if not provider:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "MiniQMT provider 不可用"},
        )

    try:
        result = await provider.get_calendar(market, start_date, end_date)
        return {
            "status": "success",
            "market": market,
            "start_date": start_date,
            "end_date": end_date,
            "count": len(result),
            "data": result,
        }
    except Exception as e:
        logger.error(f"获取交易日历失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


@router.get("/sectors", summary="获取所有板块列表")
async def get_sector_list():
    """
    获取所有板块列表

    通过 xtquant SDK 获取所有板块名称列表

    Returns:
        板块名称列表
    """
    provider = await _get_miniqmt_provider()

    if not provider:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "MiniQMT provider 不可用"},
        )

    try:
        result = await provider.get_sector_list()
        return {
            "status": "success",
            "count": len(result),
            "data": result,
        }
    except Exception as e:
        logger.error(f"获取板块列表失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


@router.get("/sectors/{sector}/stocks", summary="获取板块成分股")
async def get_sector_stocks(sector: str):
    """
    获取板块成分股

    通过 xtquant SDK 获取指定板块的成分股列表

    Args:
        sector: 板块名称，如 "沪深300"、"上证50" 等

    Returns:
        成分股代码列表
    """
    provider = await _get_miniqmt_provider()

    if not provider:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "MiniQMT provider 不可用"},
        )

    try:
        result = await provider.get_stock_list(sector)
        return {
            "status": "success",
            "sector": sector,
            "count": len(result),
            "data": result,
        }
    except Exception as e:
        logger.error(f"获取板块成分股失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


@router.get("/instrument/{symbol}", summary="获取合约详情")
async def get_instrument_detail(symbol: str):
    """
    获取股票/合约详细信息

    通过 xtquant SDK 获取指定股票或合约的详细信息

    Args:
        symbol: 股票/合约代码，如 "000001.SZ"、"600000.SH"

    Returns:
        合约详情信息，包括:
        - InstrumentID: 合约代码
        - InstrumentName: 合约名称
        - ExchangeID: 交易所代码
        - ProductID: 品种代码
        - VolumeMultiple: 合约乘数
        - PriceTick: 最小变动价位
        - ExpireDate: 到期日（如适用）
        - 其他相关字段
    """
    provider = await _get_miniqmt_provider()

    if not provider:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "MiniQMT provider 不可用"},
        )

    try:
        # 添加交易所后缀
        formatted_symbol = add_exchange_suffix(symbol)
        result = await provider.get_stock_info(formatted_symbol)
        return {
            "status": "success",
            "symbol": formatted_symbol,
            "data": result,
        }
    except Exception as e:
        logger.error(f"获取合约详情失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


@router.get("/index/{index_code}/weight", summary="获取指数成分股权重")
async def get_index_weight(index_code: str):
    """
    获取指数成分股权重

    通过 xtquant SDK 获取指定指数的成分股权重

    Args:
        index_code: 指数代码，如 "000300.SH"（沪深300）、"000016.SH"（上证50）

    Returns:
        成分股权重字典，格式: {成分股代码: 权重(%)}

    示例:
        - 沪深300: 000300.SH
        - 上证50: 000016.SH
        - 中证500: 000905.SH
    """
    provider = await _get_miniqmt_provider()

    if not provider:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "MiniQMT provider 不可用"},
        )

    try:
        result = await provider.get_index_weight(index_code)
        return {
            "status": "success",
            "index_code": index_code,
            "constituent_count": len(result),
            "data": result,
        }
    except Exception as e:
        logger.error(f"获取指数权重失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


@router.get("/kline", summary="获取K线数据")
async def get_kline(
    symbols: str = Query(..., description="股票代码列表，逗号分隔，如 '000001.SZ,600000.SH'"),
    period: str = Query("1d", description="周期: 1m/5m/15m/30m/60m/1d/1w/1M"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    adjust: str = Query("none", description="复权类型: none/qfq/hfq"),
):
    """
    获取K线数据

    通过 xtquant SDK 获取指定股票的K线数据

    Args:
        symbols: 股票代码列表，逗号分隔
        period: 周期 (1m/5m/15m/30m/60m/1d/1w/1M)
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        adjust: 复权类型 (none/qfq/hfq)

    Returns:
        K线数据字典，格式: {代码: [K线记录列表]}
    """
    provider = await _get_miniqmt_provider()

    if not provider:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "MiniQMT provider 不可用"},
        )

    try:
        # 解析股票代码列表
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        # 添加交易所后缀
        formatted_symbols = [add_exchange_suffix(s) for s in symbol_list]

        result = await provider.get_kline(
            symbols=formatted_symbols,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )

        # 统计返回的数据
        total_records = sum(len(records) for records in result.values())

        return {
            "status": "success",
            "symbols": formatted_symbols,
            "period": period,
            "adjust": adjust,
            "symbol_count": len(result),
            "total_records": total_records,
            "data": result,
        }
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


@router.get("/realtime", summary="获取实时行情")
async def get_realtime_quote(
    symbols: str = Query(..., description="股票代码列表，逗号分隔，如 '000001.SZ,600000.SH'"),
):
    """
    获取实时行情数据

    通过 xtquant SDK 获取指定股票的实时行情

    Args:
        symbols: 股票代码列表，逗号分隔

    Returns:
        实时行情数据字典，格式: {代码: 行情数据}
    """
    provider = await _get_miniqmt_provider()

    if not provider:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "MiniQMT provider 不可用"},
        )

    try:
        # 解析股票代码列表
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        # 添加交易所后缀
        formatted_symbols = [add_exchange_suffix(s) for s in symbol_list]

        result = await provider.get_realtime_quote(formatted_symbols)

        return {
            "status": "success",
            "symbols": formatted_symbols,
            "quote_count": len(result),
            "data": result,
        }
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


# ==================== VIP 功能端点 ====================


@router.get("/north-flow", summary="获取北向资金流向")
async def get_north_flow(
    symbols: Optional[str] = Query(None, description="股票代码列表，逗号分隔（可选）"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    period: str = Query("1d", description="周期: 1m(分钟级), 1d(日级)"),
):
    """
    获取北向资金流向数据（沪港通/深港通）

    通过 xtquant SDK 获取北向资金数据

    注意: 此功能需要 MiniQMT 投研版 VIP 权限

    Args:
        symbols: 股票代码列表，逗号分隔（可选，为空获取市场整体数据）
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        period: 周期类型 (1m=分钟级, 1d=日级)

    Returns:
        北向资金数据列表
    """
    provider = await _get_miniqmt_provider()

    if not provider:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "MiniQMT provider 不可用"},
        )

    try:
        # 解析股票代码列表
        symbol_list = None
        if symbols:
            symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
            symbol_list = [add_exchange_suffix(s) for s in symbol_list]

        result = await provider.get_north_flow(
            symbols=symbol_list,
            start_date=start_date,
            end_date=end_date,
            period=period,
        )

        return {
            "status": "success",
            "period": period,
            "record_count": len(result) if result else 0,
            "data": result or [],
            "note": "此功能需要 MiniQMT 投研版 VIP 权限",
        }
    except Exception as e:
        logger.error(f"获取北向资金失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


@router.get("/dragon-tiger", summary="获取龙虎榜数据")
async def get_dragon_tiger(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD，默认最新"),
    symbols: Optional[str] = Query(None, description="股票代码列表，逗号分隔（用于过滤）"),
):
    """
    获取龙虎榜数据

    注意: 由于 xtquant SDK 不支持龙虎榜，数据来源于 AkShare

    Args:
        date: 查询日期 YYYYMMDD，为空获取最新数据
        symbols: 股票代码列表，逗号分隔（可选，用于过滤结果）

    Returns:
        龙虎榜数据列表
    """
    provider = await _get_miniqmt_provider()

    if not provider:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "MiniQMT provider 不可用"},
        )

    try:
        # 解析股票代码列表
        symbol_list = None
        if symbols:
            symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]

        result = await provider.get_dragon_tiger(
            date=date,
            symbols=symbol_list,
        )

        return {
            "status": "success",
            "date": date or "latest",
            "record_count": len(result) if result else 0,
            "data": result or [],
            "source": "akshare",
            "note": "数据来源于 AkShare，非 xtquant SDK 原生数据",
        }
    except Exception as e:
        logger.error(f"获取龙虎榜失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


@router.get("/limit-performance", summary="获取涨跌表现数据")
async def get_limit_up_performance(
    symbols: str = Query(..., description="股票代码列表，逗号分隔"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
):
    """
    获取涨跌表现数据（连板、封板等）

    通过 xtquant SDK 获取涨跌表现数据

    返回字段说明:
    - openVol: 开盘集合竞价成交量
    - closeVol: 收盘集合竞价成交量
    - startUp/endUp: 涨停开始/结束时间
    - breakUp: 炸板次数
    - upAmount: 涨停金额
    - direct: 涨跌方向 (0-无, 1-涨停, 2-跌停)
    - sealCount: 连板数

    注意: 此功能需要 MiniQMT 投研版 VIP 权限

    Args:
        symbols: 股票代码列表，逗号分隔
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD

    Returns:
        涨跌表现数据列表
    """
    provider = await _get_miniqmt_provider()

    if not provider:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "MiniQMT provider 不可用"},
        )

    try:
        # 解析股票代码列表
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        formatted_symbols = [add_exchange_suffix(s) for s in symbol_list]

        result = await provider.get_limit_up_performance(
            symbols=formatted_symbols,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "status": "success",
            "symbols": formatted_symbols,
            "record_count": len(result) if result else 0,
            "data": result or [],
            "note": "此功能需要 MiniQMT 投研版 VIP 权限",
        }
    except Exception as e:
        logger.error(f"获取涨跌表现失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )
