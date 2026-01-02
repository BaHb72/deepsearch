# encoding:gbk
"""
QMT Data Collector - Production Script
Author: DeepSearch Team
Version: 4.0.0

Note: This file MUST use GBK encoding for QMT terminal compatibility!
"""

import json
import socket
import threading
import time

# ==================== Configuration ====================
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 9999
AUTH_TOKEN = "prod-secure-token-change-this"
HEARTBEAT_INTERVAL = 30  # seconds
RECONNECT_DELAY = 5  # seconds
BATCH_SIZE = 10  # batch send size
DEBUG_MODE = False  # debug mode (auto enabled when no QMT API)

# ==================== Global State ====================
g_socket = None
g_connected = False
g_running = True
g_subscribed = []  # subscribed symbols list
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
    """Initialize QMT API"""
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
    """Connect to DeepSearch server"""
    global g_socket, g_connected

    try:
        print("[Connect] Connecting to %s:%d..." % (SERVER_HOST, SERVER_PORT))

        g_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        g_socket.settimeout(10)
        g_socket.connect((SERVER_HOST, SERVER_PORT))

        # Send authentication message
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

            # Request subscription list immediately (important)
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
    """Send message to server"""
    global g_socket, g_connected, g_stats

    # Special handling for AUTH message (send when connection not fully established)
    if msg.get("type") == "AUTH":
        if not g_socket:
            return False
    elif not g_socket or not g_connected:
        return False

    try:
        # JSON message with newline ending
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
    """Receive message from server"""
    global g_socket

    if not g_socket:
        return None

    try:
        g_socket.settimeout(0.1)  # Set timeout
        data = g_socket.recv(4096)

        if not data:
            return None

        # Parse JSON message
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
    """Subscribe to stock quotes"""
    global g_subscribed, xtdata

    if not symbols:
        return

    print("[Subscribe] Subscribing to %d symbols..." % len(symbols))

    for symbol in symbols:
        if symbol in g_subscribed:
            continue

        try:
            if xtdata and not DEBUG_MODE:
                # Real subscription
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

    # In DEBUG mode, immediately start pushing simulated data
    if DEBUG_MODE and g_subscribed:
        print("[Subscribe] DEBUG mode - will start pushing simulated data")


def unsubscribe_symbols(symbols):
    """Unsubscribe from stock quotes"""
    global g_subscribed, xtdata

    for symbol in symbols:
        if symbol not in g_subscribed:
            continue

        try:
            if xtdata and not DEBUG_MODE:
                # Real unsubscription
                xtdata.unsubscribe_quote(symbol)

            g_subscribed.remove(symbol)
            print("[Unsubscribe] Removed: %s" % symbol)

        except Exception as e:
            print("[Unsubscribe] Failed for %s: %s" % (symbol, str(e)))


def get_tick_data(symbol):
    """Get stock tick data"""
    global xtdata

    try:
        if xtdata and not DEBUG_MODE:
            # Get real tick data
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

        # Simulated data
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
    """Get stock orderbook data (Level2)"""
    global xtdata

    try:
        if xtdata and not DEBUG_MODE:
            # Get real orderbook data
            tick = xtdata.get_full_tick([symbol])

            if tick and symbol in tick:
                data = tick[symbol]
                # Get bid and ask prices and volumes
                bid_prices = data.get("bidPrice", [])
                bid_volumes = data.get("bidVol", [])
                ask_prices = data.get("askPrice", [])
                ask_volumes = data.get("askVol", [])

                return {
                    "symbol": symbol,
                    "timestamp": data.get("time", time.time()),
                    "bid_price": bid_prices[:10],  # Top 10 levels
                    "bid_volume": bid_volumes[:10],
                    "ask_price": ask_prices[:10],
                    "ask_volume": ask_volumes[:10],
                }

        # Simulated data
        if DEBUG_MODE:
            import random

            base_price = 10.0 + random.uniform(-0.5, 0.5)

            # Generate 10 levels of orderbook data
            bid_prices = []
            bid_volumes = []
            ask_prices = []
            ask_volumes = []

            for i in range(10):
                # Bids, price decreasing
                bid_prices.append(round(base_price - (i + 1) * 0.01, 2))
                bid_volumes.append(random.randint(100, 10000) * 100)

                # Asks, price increasing
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
    """Download historical K-line data"""
    global xtdata

    try:
        if xtdata and not DEBUG_MODE:
            # Download real historical data
            xtdata.download_history_data(
                stock_code=stock_code, period=period, start_time=start_time, end_time=end_time
            )

            # Get downloaded data
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
                # Convert to list format
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

        # Simulated data
        if DEBUG_MODE:
            import random

            result = []
            for i in range(10):  # Return 10 simulated data points
                base_price = 10.0 + random.uniform(-1, 1)
                result.append(
                    {
                        "time": time.time() - i * 86400,  # One per day
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
    """Handle server message"""
    msg_type = msg.get("type")

    if msg_type == "SUBSCRIBE":
        # Subscribe request
        symbols = msg.get("symbols", [])
        request_id = msg.get("request_id", "")

        print("[Subscribe] Received subscribe request for %d symbols: %s" % (len(symbols), symbols))

        if symbols:
            subscribe_symbols(symbols)

            # Send subscribe response
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
        # Unsubscribe request
        symbols = msg.get("symbols", [])
        request_id = msg.get("request_id", "")

        if symbols:
            unsubscribe_symbols(symbols)

            # Send unsubscribe response
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
        # Historical data request
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
        # Heartbeat response
        send_message({"type": "HEARTBEAT_RESPONSE"})

    elif msg_type == "STATUS_REQUEST":
        # Status request
        response = {
            "type": "STATUS",
            "subscribed": g_subscribed,
            "stats": g_stats,
            "debug_mode": DEBUG_MODE,
        }
        send_message(response)

    elif msg_type == "HEARTBEAT_RESPONSE":
        # Heartbeat response, no extra processing needed
        pass

    elif msg_type == "AUTH_RESPONSE":
        # Authentication response
        status = msg.get("status")
        if status == "OK":
            print("[Auth] Authentication successful")
            # Request subscription list after successful auth
            print("[Auth] Requesting subscription list after auth...")
            send_message({"type": "GET_SUBSCRIPTION"})
        else:
            print("[Auth] Authentication failed: %s" % msg.get("message", "Unknown error"))

    elif msg_type == "SUBSCRIPTION_LIST":
        # Subscription list
        symbols = msg.get("symbols", [])
        if symbols:
            print("[Subscription] Received subscription list: %s" % symbols)
            subscribe_symbols(symbols)
            print("[Subscription] Starting data push for subscribed symbols")
        else:
            print("[Subscription] Received empty subscription list")

    elif msg_type == "SUBSCRIPTION_UPDATE":
        # Dynamic subscription update
        action = msg.get("action", "add")
        symbols = msg.get("symbols", [])

        print("[Subscription] Received update: action=%s, symbols=%s" % (action, symbols))

        if action == "add":
            # Add subscription
            subscribe_symbols(symbols)
        elif action == "remove":
            # Remove subscription
            unsubscribe_symbols(symbols)
        elif action == "replace":
            # Replace all subscriptions
            # Cancel all subscriptions
            if g_subscribed:
                unsubscribe_symbols(g_subscribed[:])
            # Add subscriptions
            if symbols:
                subscribe_symbols(symbols)

        # Send response
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
    """Data push thread"""
    global g_running, g_connected, g_subscribed

    print("[Thread] Data push thread started")
    tick_batch = []
    orderbook_batch = []
    last_push = time.time()
    push_count = 0

    while g_running:
        if not g_connected:
            time.sleep(1)
            continue

        # Check if we have subscriptions
        if not g_subscribed:
            time.sleep(1)
            continue

        try:
            # Collect tick and orderbook data
            for symbol in g_subscribed[:]:  # Copy list to avoid modification conflicts
                # Collect tick data
                tick_data = get_tick_data(symbol)
                if tick_data:
                    tick_batch.append({"type": "TICK", "data": tick_data})

                # Collect orderbook data (Level2) - ALWAYS get it with tick
                orderbook_data = get_orderbook_data(symbol)
                if orderbook_data:
                    orderbook_batch.append({"type": "LEVEL2", "data": orderbook_data})
                    # Log every push in debug mode or every 10th push normally
                    if DEBUG_MODE or push_count % 10 == 0:
                        print(
                            "[Push] Orderbook for %s: bid=%d, ask=%d"
                            % (
                                symbol,
                                len(orderbook_data.get("bid_price", [])),
                                len(orderbook_data.get("ask_price", [])),
                            )
                        )

                # Send immediately if we have data (don't wait for batch in debug mode)
                should_send = (
                    (DEBUG_MODE and (tick_batch or orderbook_batch))
                    or (len(tick_batch) + len(orderbook_batch)) >= BATCH_SIZE
                    or (time.time() - last_push) > 1.0
                )

                if should_send and (tick_batch or orderbook_batch):
                    # Send tick data
                    for msg in tick_batch:
                        send_message(msg)

                    # Send Level2 data
                    for msg in orderbook_batch:
                        send_message(msg)

                    print(
                        "[Push] Sent %d tick + %d orderbook updates (push #%d)"
                        % (len(tick_batch), len(orderbook_batch), push_count)
                    )

                    tick_batch = []
                    orderbook_batch = []
                    last_push = time.time()
                    push_count += 1

            # Adjust frequency based on mode
            if DEBUG_MODE:
                time.sleep(1.0)  # Slower in debug mode for testing
            else:
                time.sleep(0.1)  # Normal frequency

        except Exception as e:
            print("[Push] Error: %s" % str(e))
            time.sleep(1)


def message_receiver_thread():
    """Message receiver thread"""
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
    """Heartbeat thread"""
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
    """Connection manager thread"""
    global g_running, g_connected, g_subscribed

    print("[Thread] Connection manager thread started")

    while g_running:
        if not g_connected:
            print("[Manager] Attempting to reconnect...")
            if connect_to_server():
                print("[Manager] Reconnected successfully")

                # Re-subscribe, immediately request subscription list from server
                print("[Manager] Requesting subscription list after reconnect...")
                send_message({"type": "GET_SUBSCRIPTION"})

                # If g_subscribed has list (possibly disconnected locally), re-subscribe to prevent partial loss
                if g_subscribed:
                    temp_list = g_subscribed[:]
                    g_subscribed = []
                    subscribe_symbols(temp_list)
            else:
                print("[Manager] Reconnection failed, waiting %ds..." % RECONNECT_DELAY)
                time.sleep(RECONNECT_DELAY)
        else:
            time.sleep(5)  # Interval when connection is normal


# ==================== Main Function ====================
def main():
    """Main function"""
    global g_running

    print("=" * 60)
    print("QMT Data Collector v4.0.0")
    print("=" * 60)

    # Initialize QMT API
    init_qmt_api()

    # Connect to server
    if not connect_to_server():
        print("[Main] Initial connection failed")

    # Start threads
    threads = [
        threading.Thread(target=connection_manager_thread, daemon=True),
        threading.Thread(target=message_receiver_thread, daemon=True),
        threading.Thread(target=data_push_thread, daemon=True),
        threading.Thread(target=heartbeat_thread, daemon=True),
    ]

    for thread in threads:
        thread.start()

    # In DEBUG mode, don't auto-subscribe, wait for server to send subscription list
    if DEBUG_MODE and g_connected:
        print("[Main] DEBUG mode - waiting for subscription from server...")
        # Send get subscription list request
        send_message({"type": "GET_SUBSCRIPTION"})

    print("[Main] System running, press Ctrl+C to exit")

    # Main loop
    try:
        while g_running:
            time.sleep(1)

            # Periodically print statistics
            if int(time.time()) % 60 == 0:
                uptime = int(time.time() - g_stats["start_time"])
                print(
                    "[Stats] Uptime: %ds, Sent: %d, Errors: %d"
                    % (uptime, g_stats["sent_count"], g_stats["error_count"])
                )

    except KeyboardInterrupt:
        print("\n[Main] Shutting down...")
        g_running = False

        # Close connection
        if g_socket:
            try:
                g_socket.close()
            except Exception:
                pass

        print("[Main] Goodbye!")


if __name__ == "__main__":
    main()
