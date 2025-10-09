# -*- coding: utf-8 -*-
"""
QMT Data Collector - Production Script
QMT数据采集器生产脚本
Author: DeepSearch Team
Version: 4.0.0

注意：此文件的生产版本（qmt_collector.py）必须使用GBK编码！
QMT终端只支持GBK编码，使用UTF-8会导致中文乱码。
"""

import json
import socket
import threading
import time

# ==================== Configuration ====================
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 9999
AUTH_TOKEN = "prod-secure-token-change-this"
HEARTBEAT_INTERVAL = 30  # 心跳间隔（秒）
RECONNECT_DELAY = 5  # 重连延迟（秒）
BATCH_SIZE = 10  # 批量发送大小
DEBUG_MODE = False  # 调试模式（无QMT API时自动启用）

# ==================== Global State ====================
g_socket = None
g_connected = False
g_running = True
g_subscribed = []  # 已订阅股票列表
g_lock = threading.Lock()
g_stats = {
    "sent_count": 0,
    "error_count": 0,
    "last_send_time": None,
    "last_heartbeat": None,
    "start_time": time.time(),
}

# QMT API (will be imported if available)
xtdata = None
xtconstant = None


# ==================== Initialization ====================
def init_qmt_api():
    """初始化QMT API"""
    global xtdata, xtconstant, DEBUG_MODE

    try:
        import xtquant.xtdata as _xtdata
        from xtquant import xtconstant as _xtconstant

        xtdata = _xtdata
        xtconstant = _xtconstant

        print("[Init] QMT API loaded successfully")
        return True

    except ImportError as e:
        print("[Warning] QMT API not available: %s" % str(e))
        print("[Warning] Running in DEBUG mode with simulated data")
        DEBUG_MODE = True
        return False


# ==================== Network Functions ====================
def connect_to_server():
    """连接到DeepSearch服务器"""
    global g_socket, g_connected

    try:
        print("[Connect] Connecting to %s:%d..." % (SERVER_HOST, SERVER_PORT))

        g_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        g_socket.settimeout(10)
        g_socket.connect((SERVER_HOST, SERVER_PORT))

        # 发送认证消息
        auth_msg = {
            "type": "AUTH",
            "token": AUTH_TOKEN,
            "client": "QMT_COLLECTOR",
            "version": "4.0.0",
            "capabilities": ["dynamic_subscription", "batch_mode", "history_data", "tick_data"],
            "debug_mode": DEBUG_MODE,
        }

        if send_message(auth_msg):
            print("[Connect] Authentication sent")
            g_connected = True

            # 立即请求服务器订阅列表（重要）
            print("[Connect] Requesting subscription list...")
            send_message({"type": "GET_SUBSCRIPTION"})

            return True
        else:
            print("[Connect] Failed to send authentication")
            return False

    except Exception as e:
        print("[Connect] Connection failed: %s" % str(e))
        g_connected = False
        return False


def send_message(msg):
    """发送消息到服务器"""
    global g_socket, g_connected, g_stats

    # 特殊处理AUTH消息（连接还未完全建立时发送）
    if msg.get("type") == "AUTH":
        if not g_socket:
            return False
    elif not g_socket or not g_connected:
        return False

    try:
        # JSON消息，换行符结尾
        msg_str = json.dumps(msg, ensure_ascii=False) + "\n"
        g_socket.sendall(msg_str.encode("utf-8"))

        g_stats["sent_count"] += 1
        g_stats["last_send_time"] = time.time()

        return True

    except Exception as e:
        print("[Send] Error: %s" % str(e))
        g_stats["error_count"] += 1
        g_connected = False
        return False


def receive_message():
    """接收服务器消息"""
    global g_socket

    if not g_socket:
        return None

    try:
        g_socket.settimeout(0.1)  # 设置超时
        data = g_socket.recv(4096)

        if not data:
            return None

        # 解析JSON消息
        msg_str = data.decode("utf-8").strip()
        if msg_str:
            return json.loads(msg_str)

    except socket.timeout:
        return None
    except Exception as e:
        print("[Receive] Error: %s" % str(e))
        return None


# ==================== Data Collection Functions ====================
def subscribe_symbols(symbols):
    """订阅股票行情"""
    global g_subscribed, xtdata

    if not symbols:
        return

    print("[Subscribe] Subscribing to %d symbols..." % len(symbols))

    for symbol in symbols:
        if symbol in g_subscribed:
            continue

        try:
            if xtdata and not DEBUG_MODE:
                # 真实订阅
                xtdata.subscribe_quote(
                    stock_code=symbol,
                    period="tick",
                    start_time="",
                    end_time="",
                    count=0,
                    callback=None,
                )

            g_subscribed.append(symbol)
            print("[Subscribe] Added: %s" % symbol)

        except Exception as e:
            print("[Subscribe] Failed for %s: %s" % (symbol, str(e)))

    print("[Subscribe] Total subscribed: %d" % len(g_subscribed))


def unsubscribe_symbols(symbols):
    """取消订阅股票行情"""
    global g_subscribed, xtdata

    for symbol in symbols:
        if symbol not in g_subscribed:
            continue

        try:
            if xtdata and not DEBUG_MODE:
                # 真实取消订阅
                xtdata.unsubscribe_quote(symbol)

            g_subscribed.remove(symbol)
            print("[Unsubscribe] Removed: %s" % symbol)

        except Exception as e:
            print("[Unsubscribe] Failed for %s: %s" % (symbol, str(e)))


def get_tick_data(symbol):
    """获取股票tick数据"""
    global xtdata

    try:
        if xtdata and not DEBUG_MODE:
            # 获取真实tick数据
            tick = xtdata.get_full_tick([symbol])

            if tick and symbol in tick:
                data = tick[symbol]
                return {
                    "symbol": symbol,
                    "timestamp": data.get("time", time.time()),
                    "last_price": data.get("lastPrice", 0),
                    "open": data.get("open", 0),
                    "high": data.get("high", 0),
                    "low": data.get("low", 0),
                    "volume": data.get("volume", 0),
                    "amount": data.get("amount", 0),
                    "bid_price": data.get("bidPrice", []),
                    "bid_volume": data.get("bidVol", []),
                    "ask_price": data.get("askPrice", []),
                    "ask_volume": data.get("askVol", []),
                }

        # 模拟数据
        if DEBUG_MODE:
            import random

            base_price = 10.0 + random.uniform(-0.5, 0.5)
            return {
                "symbol": symbol,
                "timestamp": time.time(),
                "last_price": base_price,
                "open": base_price - 0.1,
                "high": base_price + 0.2,
                "low": base_price - 0.2,
                "volume": random.randint(100000, 1000000),
                "amount": random.randint(1000000, 10000000),
                "bid_price": [base_price - i * 0.01 for i in range(1, 6)],
                "bid_volume": [random.randint(100, 1000) for _ in range(5)],
                "ask_price": [base_price + i * 0.01 for i in range(1, 6)],
                "ask_volume": [random.randint(100, 1000) for _ in range(5)],
            }

    except Exception as e:
        print("[Tick] Error getting data for %s: %s" % (symbol, str(e)))

    return None


def get_orderbook_data(symbol):
    """获取股票盘口数据(Level2)"""
    global xtdata

    try:
        if xtdata and not DEBUG_MODE:
            # 获取真实盘口数据
            tick = xtdata.get_full_tick([symbol])

            if tick and symbol in tick:
                data = tick[symbol]
                # 获取买盘和卖盘价格及数量
                bid_prices = data.get("bidPrice", [])
                bid_volumes = data.get("bidVol", [])
                ask_prices = data.get("askPrice", [])
                ask_volumes = data.get("askVol", [])

                return {
                    "symbol": symbol,
                    "timestamp": data.get("time", time.time()),
                    "bid_price": bid_prices[:10],  # 取前10档
                    "bid_volume": bid_volumes[:10],
                    "ask_price": ask_prices[:10],
                    "ask_volume": ask_volumes[:10],
                }

        # 模拟数据
        if DEBUG_MODE:
            import random

            base_price = 10.0 + random.uniform(-0.5, 0.5)

            # 生成10档盘口数据
            bid_prices = []
            bid_volumes = []
            ask_prices = []
            ask_volumes = []

            for i in range(10):
                # 买盘，价格递减
                bid_prices.append(round(base_price - (i + 1) * 0.01, 2))
                bid_volumes.append(random.randint(100, 10000) * 100)

                # 卖盘，价格递增
                ask_prices.append(round(base_price + (i + 1) * 0.01, 2))
                ask_volumes.append(random.randint(100, 10000) * 100)

            return {
                "symbol": symbol,
                "timestamp": time.time(),
                "bid_price": bid_prices,
                "bid_volume": bid_volumes,
                "ask_price": ask_prices,
                "ask_volume": ask_volumes,
            }

    except Exception as e:
        print("[OrderBook] Error getting data for %s: %s" % (symbol, str(e)))

    return None


def download_history_data(
    stock_code, period="1d", start_time="", end_time="", dividend_type="front"
):
    """下载历史K线数据"""
    global xtdata

    try:
        if xtdata and not DEBUG_MODE:
            # 下载真实历史数据
            xtdata.download_history_data(
                stock_code=stock_code, period=period, start_time=start_time, end_time=end_time
            )

            # 获取下载的数据
            data = xtdata.get_market_data(
                field_list=["time", "open", "high", "low", "close", "volume", "amount"],
                stock_list=[stock_code],
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=-1,
                dividend_type=dividend_type,
                fill_data=True,
            )

            if data and stock_code in data:
                # 转换为列表格式
                df_data = data[stock_code]
                result = []

                for i in range(len(df_data["time"])):
                    result.append(
                        {
                            "time": df_data["time"][i],
                            "open": df_data["open"][i],
                            "high": df_data["high"][i],
                            "low": df_data["low"][i],
                            "close": df_data["close"][i],
                            "volume": df_data["volume"][i],
                            "amount": df_data["amount"][i],
                        }
                    )

                return result

        # 模拟数据
        if DEBUG_MODE:
            import random

            result = []
            for i in range(10):  # 返回10条模拟数据
                base_price = 10.0 + random.uniform(-1, 1)
                result.append(
                    {
                        "time": time.time() - i * 86400,  # 每天一条
                        "open": base_price,
                        "high": base_price + random.uniform(0, 0.5),
                        "low": base_price - random.uniform(0, 0.5),
                        "close": base_price + random.uniform(-0.3, 0.3),
                        "volume": random.randint(100000, 1000000),
                        "amount": random.randint(1000000, 10000000),
                    }
                )
            return result

    except Exception as e:
        print("[History] Error downloading data for %s: %s" % (stock_code, str(e)))

    return None


# ==================== Message Handlers ====================
def handle_server_message(msg):
    """处理服务器消息"""
    msg_type = msg.get("type")

    if msg_type == "SUBSCRIBE":
        # 订阅请求
        symbols = msg.get("symbols", [])
        request_id = msg.get("request_id", "")

        print("[Subscribe] Received subscribe request for %d symbols: %s" % (len(symbols), symbols))

        if symbols:
            subscribe_symbols(symbols)

            # 发送订阅响应
            response = {
                "type": "SUBSCRIBE_RESPONSE",
                "request_id": request_id,
                "status": "OK",
                "subscribed": symbols,
                "message": "Successfully subscribed to %d symbols" % len(symbols),
            }
            send_message(response)
            print("[Subscribe] Sent response for request %s" % request_id)

    elif msg_type == "UNSUBSCRIBE":
        # 取消订阅请求
        symbols = msg.get("symbols", [])
        request_id = msg.get("request_id", "")

        if symbols:
            unsubscribe_symbols(symbols)

            # 发送取消响应
            response = {
                "type": "UNSUBSCRIBE_RESPONSE",
                "request_id": request_id,
                "status": "OK",
                "unsubscribed": symbols,
                "message": "Successfully unsubscribed from %d symbols" % len(symbols),
            }
            send_message(response)
            print("[Unsubscribe] Sent response for request %s" % request_id)

    elif msg_type == "HISTORY_REQUEST":
        # 历史数据请求
        params = msg.get("params", {})
        data = download_history_data(
            params.get("stock_code"),
            params.get("period", "1d"),
            params.get("start_time", ""),
            params.get("end_time", ""),
            params.get("dividend_type", "front"),
        )

        if data:
            response = {
                "type": "HISTORY_DATA",
                "symbol": params.get("stock_code"),
                "period": params.get("period", "1d"),
                "data": data,
            }
            send_message(response)

    elif msg_type == "HEARTBEAT":
        # 心跳响应
        send_message({"type": "HEARTBEAT_RESPONSE"})

    elif msg_type == "STATUS_REQUEST":
        # 状态请求
        response = {
            "type": "STATUS",
            "subscribed": g_subscribed,
            "stats": g_stats,
            "debug_mode": DEBUG_MODE,
        }
        send_message(response)

    elif msg_type == "HEARTBEAT_RESPONSE":
        # 心跳响应，不需要额外处理
        pass

    elif msg_type == "AUTH_RESPONSE":
        # 认证响应
        status = msg.get("status")
        if status == "OK":
            print("[Auth] Authentication successful")
            # 认证成功后立即请求订阅列表
            print("[Auth] Requesting subscription list after auth...")
            send_message({"type": "GET_SUBSCRIPTION"})
        else:
            print("[Auth] Authentication failed: %s" % msg.get("message", "Unknown error"))

    elif msg_type == "SUBSCRIPTION_LIST":
        # 订阅列表
        symbols = msg.get("symbols", [])
        if symbols:
            print("[Subscription] Received subscription list: %s" % symbols)
            subscribe_symbols(symbols)
        else:
            print("[Subscription] Received empty subscription list")

    elif msg_type == "SUBSCRIPTION_UPDATE":
        # 动态更新订阅列表
        action = msg.get("action", "add")
        symbols = msg.get("symbols", [])

        print("[Subscription] Received update: action=%s, symbols=%s" % (action, symbols))

        if action == "add":
            # 添加订阅
            subscribe_symbols(symbols)
        elif action == "remove":
            # 取消订阅
            unsubscribe_symbols(symbols)
        elif action == "replace":
            # 替换所有订阅
            global g_subscribed
            # 取消所有订阅
            if g_subscribed:
                unsubscribe_symbols(g_subscribed[:])
            # 添加订阅
            if symbols:
                subscribe_symbols(symbols)

        # 发送响应
        response = {
            "type": "SUBSCRIPTION_UPDATE_RESPONSE",
            "status": "OK",
            "action": action,
            "symbols": symbols,
            "total_subscribed": len(g_subscribed),
        }
        send_message(response)

    else:
        print("[Handler] Unknown message type: %s" % msg_type)


# ==================== Thread Functions ====================
def data_push_thread():
    """数据推送线程"""
    global g_running, g_connected, g_subscribed

    print("[Thread] Data push thread started")
    tick_batch = []
    orderbook_batch = []
    last_push = time.time()

    while g_running:
        if not g_connected:
            time.sleep(1)
            continue

        try:
            # 收集tick和盘口数据
            for symbol in g_subscribed[:]:  # 复制列表，避免修改时冲突
                # 收集Tick数据
                tick_data = get_tick_data(symbol)
                if tick_data:
                    tick_batch.append({"type": "TICK", "data": tick_data})

                # 收集盘口数据(Level2)
                orderbook_data = get_orderbook_data(symbol)
                if orderbook_data:
                    orderbook_batch.append({"type": "LEVEL2", "data": orderbook_data})

                # 批量发送
                if (len(tick_batch) + len(orderbook_batch)) >= BATCH_SIZE or (
                    time.time() - last_push
                ) > 1.0:
                    # 发送Tick数据
                    for msg in tick_batch:
                        send_message(msg)

                    # 发送Level2数据
                    for msg in orderbook_batch:
                        send_message(msg)

                    if tick_batch or orderbook_batch:
                        print(
                            "[Push] Sent %d tick + %d orderbook updates"
                            % (len(tick_batch), len(orderbook_batch))
                        )

                    tick_batch = []
                    orderbook_batch = []
                    last_push = time.time()

            time.sleep(0.1)  # 控制频率

        except Exception as e:
            print("[Push] Error: %s" % str(e))
            time.sleep(1)


def message_receiver_thread():
    """消息接收线程"""
    global g_running, g_connected

    print("[Thread] Message receiver thread started")

    while g_running:
        if not g_connected:
            time.sleep(1)
            continue

        try:
            msg = receive_message()
            if msg:
                handle_server_message(msg)

        except Exception as e:
            print("[Receiver] Error: %s" % str(e))
            time.sleep(1)


def heartbeat_thread():
    """心跳线程"""
    global g_running, g_connected, g_stats

    print("[Thread] Heartbeat thread started")

    while g_running:
        if g_connected:
            try:
                send_message({"type": "HEARTBEAT"})
                g_stats["last_heartbeat"] = time.time()
                print("[Heartbeat] Sent")

            except Exception as e:
                print("[Heartbeat] Error: %s" % str(e))

        time.sleep(HEARTBEAT_INTERVAL)


def connection_manager_thread():
    """连接管理线程"""
    global g_running, g_connected, g_subscribed

    print("[Thread] Connection manager thread started")

    while g_running:
        if not g_connected:
            print("[Manager] Attempting to reconnect...")
            if connect_to_server():
                print("[Manager] Reconnected successfully")

                # 重新订阅，立即请求服务器订阅列表
                print("[Manager] Requesting subscription list after reconnect...")
                send_message({"type": "GET_SUBSCRIPTION"})

                # 如果g_subscribed有列表（可能本地断线），保持重新订阅，以防部分丢失
                if g_subscribed:
                    temp_list = g_subscribed[:]
                    g_subscribed = []
                    subscribe_symbols(temp_list)
            else:
                print("[Manager] Reconnection failed, waiting %ds..." % RECONNECT_DELAY)
                time.sleep(RECONNECT_DELAY)
        else:
            time.sleep(5)  # 连接正常时的间隔


# ==================== Main Function ====================
def main():
    """主函数"""
    global g_running

    print("=" * 60)
    print("QMT Data Collector v4.0.0")
    print("=" * 60)

    # 初始化QMT API
    init_qmt_api()

    # 连接服务器
    if not connect_to_server():
        print("[Main] Initial connection failed")

    # 启动线程
    threads = [
        threading.Thread(target=connection_manager_thread, daemon=True),
        threading.Thread(target=message_receiver_thread, daemon=True),
        threading.Thread(target=data_push_thread, daemon=True),
        threading.Thread(target=heartbeat_thread, daemon=True),
    ]

    for thread in threads:
        thread.start()

    # 在DEBUG模式下不自动订阅，等待服务器发送订阅列表
    if DEBUG_MODE and g_connected:
        print("[Main] DEBUG mode - waiting for subscription from server...")
        # 发送获取订阅列表请求
        send_message({"type": "GET_SUBSCRIPTION"})

    print("[Main] System running, press Ctrl+C to exit")

    # 主循环
    try:
        while g_running:
            time.sleep(1)

            # 定期打印统计
            if int(time.time()) % 60 == 0:
                uptime = int(time.time() - g_stats["start_time"])
                print(
                    "[Stats] Uptime: %ds, Sent: %d, Errors: %d"
                    % (uptime, g_stats["sent_count"], g_stats["error_count"])
                )

    except KeyboardInterrupt:
        print("\n[Main] Shutting down...")
        g_running = False

        # 关闭连接
        if g_socket:
            try:
                g_socket.close()
            except Exception:
                pass

        print("[Main] Goodbye!")


if __name__ == "__main__":
    main()
