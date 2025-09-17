"""
QMT数据API端点
"""

import asyncio
import json
import time
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from deepsearch.config import get_config
from deepsearch.core.runtime.context import get_context
from deepsearch.infrastructure.providers.datafeed.qmt.gateway import QMTGateway

router = APIRouter(prefix="/api/qmt", tags=["qmt"])

# 获取数据源配置
try:
    config = get_config()
    if hasattr(config, 'data_providers') and config.data_providers:
        # 如果是对象，尝试转换为字典
        if hasattr(config.data_providers, 'qmt_only'):
            QMT_ONLY_MODE = config.data_providers.qmt_only
        elif hasattr(config.data_providers, '__dict__'):
            QMT_ONLY_MODE = config.data_providers.__dict__.get('qmt_only', False)
        else:
            QMT_ONLY_MODE = False
    else:
        QMT_ONLY_MODE = False

    if QMT_ONLY_MODE:
        logger.info("QMT Only Mode 已启用 - 只使用QMT数据源")
except Exception as e:
    logger.warning(f"无法读取数据源配置: {e}")
    QMT_ONLY_MODE = False


def get_qmt_service():
    """获取QMT服务实例（用于测试兼容）"""
    return get_qmt_gateway()


def get_qmt_gateway() -> Optional[QMTGateway]:
    """获取QMT网关实例"""
    try:
        # 从应用上下文获取组件管理器
        context = get_context()

        # 先尝试从组件管理器获取
        try:
            manager = context.get_component_manager()
            logger.debug("正在从ComponentManager获取qmt_gateway组件...")
            component = manager.get_component('qmt_gateway')
        except (RuntimeError, ValueError) as e:
            logger.debug(f"从ComponentManager获取失败: {e}")
            component = None

        if not component:
            logger.warning("ComponentManager未找到qmt_gateway组件")
            return None

        logger.debug(f"获取到组件: {type(component).__name__}")

        # 检查是否是QMTGatewayComponent实例
        from deepsearch.core.components.qmt_gateway_component import QMTGatewayComponent
        if isinstance(component, QMTGatewayComponent):
            logger.debug("返回QMTGatewayComponent实例作为网关")
            return component

        # 如果是QMTGatewayComponent包装器，获取内部的网关实例
        if hasattr(component, 'get_instance'):
            gateway = component.get_instance()
            logger.debug(f"从组件获取网关实例: {type(gateway).__name__ if gateway else 'None'}")
            return gateway
        elif hasattr(component, 'gateway'):
            # 有些组件可能直接有gateway属性
            gateway = component.gateway
            logger.debug(f"从组件.gateway获取网关实例: {type(gateway).__name__ if gateway else 'None'}")
            return gateway

        # 如果组件有 _gateway 属性，直接返回
        if hasattr(component, '_gateway'):
            gateway = component._gateway
            logger.debug(f"从组件._gateway获取网关实例: {type(gateway).__name__ if gateway else 'None'}")
            return gateway

        # 直接返回组件（兼容旧版本）
        logger.debug("直接返回组件作为网关")
        return component
    except Exception as e:
        logger.error(f"获取QMT网关失败: {e}", exc_info=True)
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
                "data": {
                    "running": False,
                    "enabled": False
                }
            }
        )

    try:
        status = gateway.get_status()
        return {
            "status": "success",
            "data": status
        }
    except Exception as e:
        logger.error(f"获取QMT状态失败: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e)
            }
        )


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
        def add_exchange_suffix(code: str) -> str:
            """根据股票代码自动添加交易所后缀"""
            if '.' in code:
                return code  # 已有后缀，直接返回

            # 根据股票代码判断交易所
            if code.startswith('6'):
                return f"{code}.SH"  # 上海证券交易所
            elif code.startswith(('0', '3')):
                return f"{code}.SZ"  # 深圳证券交易所
            else:
                return code

        # 转换所有股票代码格式
        formatted_symbols = [add_exchange_suffix(s) for s in symbols]
        if formatted_symbols != symbols:
            logger.info(f"股票代码格式转换: {symbols} -> {formatted_symbols}")

        # 先更新订阅管理器（这是真正的订阅源）
        from deepsearch.webui.api.endpoints.qmt.qmt_subscription import subscription_manager
        result = subscription_manager.update_subscription(formatted_symbols, action="add")
        logger.info(f"更新订阅管理器: {result}")

        # 然后更新gateway（用于内存缓存）
        gateway.subscribe(formatted_symbols)

        # 立即触发推送更新到所有客户端
        try:
            # 获取receiver组件并触发推送
            from deepsearch.core.runtime.context import get_context
            context = get_context()
            if hasattr(context, '_component_manager'):
                manager = context._component_manager
                receiver_comp = manager.get_component("qmt_receiver")
                if receiver_comp and hasattr(receiver_comp, 'receiver'):
                    receiver = receiver_comp.receiver
                    # 手动触发一次推送
                    import asyncio
                    asyncio.create_task(receiver.push_subscription_updates())
                    logger.info(f"触发订阅更新推送: {symbols}")
        except Exception as e:
            logger.warning(f"无法触发即时推送: {e}")
        
        return {
            "status": "success",
            "message": f"已订阅 {len(symbols)} 只股票",
            "data": {
                "symbols": symbols,
                "total": len(gateway.subscribed_symbols),
                "affected_clients": result.get('affected_clients', []),
                "global_subscribed": len(subscription_manager.global_symbols)
            }
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
        from deepsearch.webui.api.endpoints.qmt.qmt_subscription import subscription_manager
        result = subscription_manager.update_subscription(symbols, action="remove")
        logger.info(f"同步更新订阅管理器（取消订阅）: {result}")
        
        return {
            "status": "success",
            "message": f"已取消订阅 {len(symbols)} 只股票",
            "data": {
                "symbols": symbols,
                "total": len(gateway.subscribed_symbols),
                "affected_clients": result.get('affected_clients', [])
            }
        }
    except Exception as e:
        logger.error(f"取消订阅失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscribed")
async def get_subscribed_symbols():
    """获取已订阅的股票列表"""
    gateway = get_qmt_gateway()

    if not gateway:
        return {
            "status": "success",
            "data": {
                "symbols": [],
                "total": 0
            }
        }

    return {
        "status": "success",
        "data": {
            "symbols": list(gateway.subscribed_symbols),
            "total": len(gateway.subscribed_symbols)
        }
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
            if hasattr(gateway, 'subscribed_symbols') and symbol not in gateway.subscribed_symbols:
                logger.info(f"股票 {symbol} 未订阅，自动订阅...")
                if hasattr(gateway, 'subscribe'):
                    gateway.subscribe([symbol])
                    # 等待数据到达（最多等待2秒）
                    for i in range(20):  # 20次，每次100ms
                        await asyncio.sleep(0.1)
                        if hasattr(gateway, 'get_latest_tick'):
                            tick = gateway.get_latest_tick(symbol)
                            if tick:
                                logger.info(f"成功获取 {symbol} 的QMT Tick数据")
                                return {
                                    "status": "success",
                                    "source": "qmt",
                                    "data": tick
                                }
            else:
                # 已订阅，直接获取
                if hasattr(gateway, 'get_latest_tick'):
                    tick = gateway.get_latest_tick(symbol)
                    if tick:
                        return {
                            "status": "success",
                            "source": "qmt",
                            "data": tick
                        }
        except Exception as e:
            logger.warning(f"从QMT获取Tick数据失败: {e}")

    # 检查是否只使用QMT模式
    if QMT_ONLY_MODE:
        logger.info(f"QMT Only Mode - 不尝试备用数据源")
        return {
            "status": "success",
            "source": "qmt",
            "message": "QMT数据源未返回数据",
            "data": {
                "symbol": symbol,
                "timestamp": int(time.time()),
                "last_price": 0,
                "volume": 0,
                "amount": 0
            }
        }

    # QMT无数据，尝试从备用数据源获取
    logger.info(f"QMT无Tick数据，尝试从备用数据源获取 {symbol} 的实时数据...")

    try:
        # 尝试从DataSourceManager获取
        from deepsearch.infrastructure.providers.managers.data_source_manager import DataSourceManager
        manager = DataSourceManager()

        snapshot = await manager.get_realtime_quote(symbol)

        if snapshot and snapshot.get('current'):
            # 转换为Tick格式
            return {
                "status": "success",
                "source": snapshot.get('source', 'unified'),
                "message": "使用实时快照数据",
                "data": {
                    "symbol": symbol,
                    "name": snapshot.get('name', ''),
                    "last_price": snapshot.get('current', 0),
                    "pre_close": snapshot.get('prev_close', 0),
                    "open": snapshot.get('open', 0),
                    "high": snapshot.get('high', 0),
                    "low": snapshot.get('low', 0),
                    "volume": snapshot.get('volume', 0),
                    "amount": snapshot.get('amount', 0),
                    "change": snapshot.get('change', 0),
                    "pct_change": snapshot.get('change_pct', 0),
                    "timestamp": snapshot.get('timestamp', int(time.time()))
                }
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
    from deepsearch.infrastructure.providers.managers.data_source_manager import get_data_source_manager
    
    try:
        data_source_manager = await get_data_source_manager()
        
        # 获取实时行情（包含盘口数据）
        result = await data_source_manager.get_realtime_quote(symbol)
        
        if result is not None and not result.get('error'):
            # 格式化为盘口数据格式
            orderbook_data = {
                "symbol": symbol,
                "timestamp": result.get('timestamp', int(time.time())),
                "bid_levels": [],
                "ask_levels": []
            }
            
            # 提取买卖盘数据
            bid_prices = result.get('bid_price', [])
            bid_volumes = result.get('bid_volume', [])
            ask_prices = result.get('ask_price', [])
            ask_volumes = result.get('ask_volume', [])
            
            # 构建盘口级别
            for i in range(min(5, len(bid_prices))):
                if i < len(bid_volumes):
                    orderbook_data['bid_levels'].append({
                        'price': bid_prices[i],
                        'volume': bid_volumes[i]
                    })
            
            for i in range(min(5, len(ask_prices))):
                if i < len(ask_volumes):
                    orderbook_data['ask_levels'].append({
                        'price': ask_prices[i],
                        'volume': ask_volumes[i]
                    })
            
            return {
                "status": "success",
                "source": result.get('_source', 'unknown'),
                "data": orderbook_data
            }
        else:
            error_msg = result.get('error', '获取数据失败')
            logger.warning(f"获取盘口数据失败: {error_msg}")
            return {
                "status": "error",
                "source": "unified",
                "message": error_msg,
                "data": {
                    "symbol": symbol,
                    "timestamp": int(time.time()),
                    "bid_levels": [],
                    "ask_levels": []
                }
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
                "ask_levels": []
            }
        }

    try:
        # 检查是否已订阅该股票（使用格式化后的代码）
        if hasattr(gateway, 'subscribed_symbols'):
            # 同时检查原始代码和格式化代码
            if formatted_symbol not in gateway.subscribed_symbols and symbol not in gateway.subscribed_symbols:
                logger.info(f"股票 {formatted_symbol} 未订阅，自动订阅...")
                if hasattr(gateway, 'subscribe'):
                    gateway.subscribe([formatted_symbol])
                    # 等待数据到达（最多等待2秒）
                    for i in range(20):  # 20次，每次100ms
                        await asyncio.sleep(0.1)
                        if hasattr(gateway, 'get_latest_orderbook'):
                            # 尝试使用格式化代码获取
                            orderbook = gateway.get_latest_orderbook(formatted_symbol)
                            if not orderbook and formatted_symbol != symbol:
                                # 如果失败，尝试原始代码
                                orderbook = gateway.get_latest_orderbook(symbol)

                            if orderbook:
                                logger.info(f"成功获取 {formatted_symbol} 的QMT盘口数据")
                                return {
                                    "status": "success",
                                    "source": "qmt",
                                    "data": orderbook
                                }

        # 直接获取盘口数据（先尝试格式化代码，再尝试原始代码）
        if hasattr(gateway, 'get_latest_orderbook'):
            logger.debug(f"调用 gateway.get_latest_orderbook({formatted_symbol})")
            orderbook = gateway.get_latest_orderbook(formatted_symbol)

            # 如果格式化代码失败，尝试原始代码
            if not orderbook and formatted_symbol != symbol:
                logger.debug(f"格式化代码无数据，尝试原始代码: {symbol}")
                orderbook = gateway.get_latest_orderbook(symbol)

            if orderbook:
                logger.info(f"成功获取QMT盘口数据: {formatted_symbol}")
                return {
                    "status": "success",
                    "source": "qmt",
                    "data": orderbook
                }
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
                "ask_levels": []
            }
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
            "ask_levels": []
        }
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
        return {
            "status": "success",
            "message": "QMT未连接",
            "data": []
        }

    # 尝试从网关获取交易明细
    try:
        # 如果网关有get_trade_details方法，调用它
        if hasattr(gateway, 'get_trade_details'):
            trades = gateway.get_trade_details(symbol, limit)
            return {
                "status": "success",
                "data": trades
            }
        else:
            # 返回模拟数据或空数据
            logger.debug(f"QMT网关不支持交易明细，返回空数据: {symbol}")
            return {
                "status": "success",
                "message": "交易明细功能未实现",
                "data": []
            }
    except Exception as e:
        logger.error(f"获取交易明细失败 {symbol}: {e}")
        # 返回空数据而不是抛出异常
        return {
            "status": "success",
            "message": f"获取失败: {str(e)}",
            "data": []
        }


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
        await websocket.send_json({
            "type": "error",
            "message": "QMT网关未启动"
        })
        await websocket.close()
        return

    client_id = f"ws_{id(websocket)}"
    subscribed_symbols = set()

    logger.info(f"WebSocket客户端连接: {client_id}")

    try:
        # 发送初始状态
        await websocket.send_json({
            "type": "connected",
            "data": {
                "client_id": client_id,
                "status": gateway.get_status()
            }
        })

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
                            await websocket.send_json({
                                "type": "tick",
                                "data": tick
                            })

                        # 获取最新盘口
                        orderbook = gateway.get_latest_orderbook(symbol)
                        if orderbook:
                            await websocket.send_json({
                                "type": "orderbook",
                                "data": orderbook
                            })

                    # 控制推送频率
                    await asyncio.sleep(0.1)  # 100ms

                except Exception as e:
                    logger.error(f"推送数据失败: {e}")
                    break

        # 启动推送任务
        push_task = asyncio.create_task(push_data())

        # 处理客户端消息
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

                    await websocket.send_json({
                        "type": "subscribed",
                        "data": {
                            "symbols": symbols,
                            "total": len(subscribed_symbols)
                        }
                    })

                elif action == "unsubscribe":
                    # 取消订阅
                    for symbol in symbols:
                        subscribed_symbols.discard(symbol)

                    await websocket.send_json({
                        "type": "unsubscribed",
                        "data": {
                            "symbols": symbols,
                            "total": len(subscribed_symbols)
                        }
                    })

                elif action == "ping":
                    # 心跳
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": asyncio.get_event_loop().time()
                    })

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
            except Exception as e:
                logger.error(f"处理WebSocket消息失败: {e}")
                break

    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
    finally:
        # 取消推送任务
        if 'push_task' in locals():
            push_task.cancel()

        logger.info(f"WebSocket客户端断开: {client_id}")


@router.get("/clients")
async def get_connected_clients():
    """获取连接的QMT客户端信息"""
    gateway = get_qmt_gateway()

    if not gateway or not gateway.receiver:
        return {
            "status": "success",
            "data": {
                "clients": [],
                "total": 0
            }
        }

    clients = gateway.receiver.get_client_info()

    return {
        "status": "success",
        "data": {
            "clients": clients,
            "total": len(clients)
        }
    }


@router.get("/statistics")
async def get_statistics():
    """获取QMT数据统计信息"""
    gateway = get_qmt_gateway()

    if not gateway:
        return {
            "status": "success",
            "data": {
                "gateway": None,
                "receiver": None
            }
        }

    return {
        "status": "success",
        "data": {
            "gateway": gateway.stats,
            "receiver": gateway.receiver.get_stats() if gateway.receiver else None
        }
    }
