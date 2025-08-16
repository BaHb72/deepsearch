# encoding:utf-8
# QMT Dynamic Data Push Script
# Designed for QMT terminal with dynamic subscription support

import json
import socket
import time
from datetime import datetime

# ==================== Configuration ====================
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 9999
AUTH_TOKEN = 'prod-secure-token-change-this'
DEBUG_MODE = True  # 调试模式标志
DEFAULT_SYMBOLS = ['000001.SZ', '000002.SZ', '600000.SH']  # 默认测试股票

# ==================== Global Variables ====================
g_socket = None
g_subscribed = []
g_stats = {
    'sent_count': 0,
    'error_count': 0,
    'last_send_time': None,
    'last_heartbeat': None
}
g_running = True  # 运行标志


# ==================== Network Functions ====================
def connect_server():
    '''Connect to DeepSearch server'''
    global g_socket

    try:
        g_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        g_socket.settimeout(30.0)  # 设置超时时间到30秒
        g_socket.connect((SERVER_HOST, SERVER_PORT))
        print('Connected to server %s:%d' % (SERVER_HOST, SERVER_PORT))

        # Send auth message
        auth_msg = {
            'type': 'AUTH',
            'token': AUTH_TOKEN,
            'client': 'QMT_DYNAMIC',
            'version': '2.0.0',
            'capabilities': ['dynamic_subscription']
        }

        send_message(auth_msg)
        print('Auth message sent')

        # Request subscription list
        request_msg = {
            'type': 'GET_SUBSCRIPTION',
            'client': 'QMT'
        }
        send_message(request_msg)
        print('Requested subscription list')

        return True

    except Exception as e:
        print('Connection failed: %s' % str(e))
        g_socket = None
        return False


def disconnect_server():
    '''Disconnect from server'''
    global g_socket

    if g_socket:
        try:
            disconnect_msg = {'type': 'DISCONNECT'}
            send_message(disconnect_msg)
        except:
            pass

        try:
            g_socket.close()
        except:
            pass

        g_socket = None
        print('Disconnected from server')


def send_message(msg):
    '''Send message to server'''
    global g_socket, g_stats

    if not g_socket:
        return False

    try:
        # Use newline delimited JSON
        data = json.dumps(msg, ensure_ascii=False) + '\n'
        g_socket.sendall(data.encode('utf-8'))

        g_stats['sent_count'] += 1
        g_stats['last_send_time'] = time.time()
        return True

    except Exception as e:
        print('Send failed: %s' % str(e))
        g_stats['error_count'] += 1
        g_socket = None
        return False


def receive_message():
    '''Receive message from server'''
    global g_socket

    if not g_socket:
        return None

    try:
        g_socket.settimeout(0.1)  # Non-blocking receive
        data = g_socket.recv(4096)
        if data:
            # Handle newline delimited messages
            messages = data.decode('utf-8').strip().split('\n')
            for msg_str in messages:
                if msg_str:
                    return json.loads(msg_str)
        return None
    except socket.timeout:
        return None
    except Exception as e:
        return None


def send_heartbeat():
    '''Send heartbeat to keep connection alive'''
    global g_stats

    heartbeat_msg = {
        'type': 'HEARTBEAT',
        'timestamp': time.time(),
        'client': 'QMT_DYNAMIC'
    }

    if send_message(heartbeat_msg):
        g_stats['last_heartbeat'] = time.time()
        print('[Heartbeat] Sent at %s' % datetime.now().strftime('%H:%M:%S'))
        return True
    return False


def process_server_message(msg):
    '''Process message from server'''
    global g_subscribed, DEBUG_MODE

    msg_type = msg.get('type')

    if msg_type == 'AUTH_RESPONSE':
        # Authentication response
        status = msg.get('status')
        if status == 'OK':
            print('Authentication successful')
            print('Client ID: %s' % msg.get('client_id', 'Unknown'))
        else:
            print('Authentication failed: %s' % msg.get('message', 'Unknown error'))

    elif msg_type == 'SUBSCRIBE':
        # Server requests subscription
        symbols = msg.get('symbols', [])
        print('Server requested subscription: %d symbols' % len(symbols))
        subscribe_symbols(symbols)

    elif msg_type == 'UNSUBSCRIBE':
        # Server requests unsubscription  
        symbols = msg.get('symbols', [])
        print('Server requested unsubscription: %d symbols' % len(symbols))
        unsubscribe_symbols(symbols)

    elif msg_type == 'SUBSCRIPTION_LIST':
        # Server sends full subscription list
        symbols = msg.get('symbols', [])
        print('=' * 60)
        print('Received subscription list: %d symbols' % len(symbols))
        if symbols:
            print('Symbols: %s' % ', '.join(symbols[:10]))  # Show first 10
            if len(symbols) > 10:
                print('... and %d more' % (len(symbols) - 10))
        print('=' * 60)

        # 如果收到空列表，在调试模式下使用默认股票
        if len(symbols) == 0:
            print('WARNING: Received empty subscription list!')
            if DEBUG_MODE:
                print('Using default symbols in debug mode')
                symbols = DEFAULT_SYMBOLS

        # Clear and resubscribe
        if g_subscribed:
            print('Clearing existing subscriptions: %d symbols' % len(g_subscribed))
            unsubscribe_symbols(g_subscribed[:])

        # Subscribe to new symbols
        subscribe_symbols(symbols)

    elif msg_type == 'HEARTBEAT_RESPONSE':
        # Heartbeat response from server
        print('[Heartbeat] Response received')

    else:
        print('Received message type: %s' % msg_type)


def subscribe_symbols(symbols):
    '''Subscribe to symbols'''
    global g_subscribed, DEBUG_MODE

    try:
        from xtquant import xtdata

        for symbol in symbols:
            if symbol not in g_subscribed:
                try:
                    xtdata.subscribe_quote(
                        stock_code=symbol,
                        period='tick',
                        start_time='',
                        end_time='',
                        count=0,
                        callback=None
                    )

                    g_subscribed.append(symbol)
                    print('Subscribed: %s' % symbol)

                except Exception as e:
                    print('Subscribe %s failed: %s' % (symbol, str(e)))

        print('Total subscribed: %d' % len(g_subscribed))

    except ImportError:
        print('Warning: QMT API not found, running in simulation mode')
        DEBUG_MODE = True  # 自动设置调试模式
        # 在调试模式下，直接添加到订阅列表
        for symbol in symbols:
            if symbol not in g_subscribed:
                g_subscribed.append(symbol)
                print('Subscribed (simulated): %s' % symbol)
        print('Total subscribed (simulated): %d' % len(g_subscribed))


def unsubscribe_symbols(symbols):
    '''Unsubscribe from symbols'''
    global g_subscribed

    try:
        from xtquant import xtdata

        for symbol in symbols:
            if symbol in g_subscribed:
                try:
                    xtdata.unsubscribe_quote(symbol)
                    g_subscribed.remove(symbol)
                    print('Unsubscribed: %s' % symbol)
                except Exception as e:
                    print('Unsubscribe %s failed: %s' % (symbol, str(e)))

    except ImportError:
        pass


def reconnect():
    '''Reconnect to server'''
    print('Attempting reconnection...')
    disconnect_server()
    time.sleep(2)

    if connect_server():
        print('Reconnected successfully')
        return True
    else:
        print('Reconnection failed')
        return False


def generate_mock_tick(symbol):
    '''Generate mock tick data for testing'''
    import random

    # 生成模拟数据
    base_price = 10.0 + random.uniform(-0.5, 0.5)

    return {
        'symbol': symbol,
        'timestamp': time.time(),
        'last_price': base_price,
        'volume': random.randint(1000, 10000) * 100,
        'amount': base_price * random.randint(1000, 10000) * 100,
        'open': base_price - random.uniform(0, 0.2),
        'high': base_price + random.uniform(0, 0.3),
        'low': base_price - random.uniform(0, 0.3),
        'pre_close': base_price - random.uniform(-0.1, 0.1)
    }


def get_orderbook_data(symbol):
    '''Get orderbook (5-level bid/ask) data for a symbol'''
    try:
        from xtquant import xtdata

        # Define fields for 5-level orderbook
        fields = []
        for i in range(1, 6):
            fields.extend([
                'bidPrice%d' % i, 'askPrice%d' % i,
                'bidVol%d' % i, 'askVol%d' % i
            ])

        # Get market data with orderbook fields
        data = xtdata.get_market_data_ex(
            field_list=fields,
            stock_list=[symbol],
            period='tick',
            count=1
        )

        if data and symbol in data and len(data[symbol]) > 0:
            latest = data[symbol].iloc[-1]

            # Extract bid/ask prices and volumes
            bid_prices = []
            ask_prices = []
            bid_volumes = []
            ask_volumes = []

            for i in range(1, 6):
                bid_prices.append(float(latest.get('bidPrice%d' % i, 0)))
                ask_prices.append(float(latest.get('askPrice%d' % i, 0)))
                bid_volumes.append(int(latest.get('bidVol%d' % i, 0)))
                ask_volumes.append(int(latest.get('askVol%d' % i, 0)))

            return {
                'bid_price': bid_prices,
                'ask_price': ask_prices,
                'bid_volume': bid_volumes,
                'ask_volume': ask_volumes
            }

        return None

    except ImportError:
        # Return mock orderbook in debug mode
        if DEBUG_MODE:
            import random
            base_price = 10.0 + random.uniform(-0.5, 0.5)
            bid_prices = []
            ask_prices = []
            bid_volumes = []
            ask_volumes = []

            for i in range(5):
                bid_prices.append(round(base_price - 0.01 * (i + 1), 2))
                ask_prices.append(round(base_price + 0.01 * (i + 1), 2))
                bid_volumes.append((5 - i) * 1000 * 100)
                ask_volumes.append((i + 1) * 1000 * 100)

            return {
                'bid_price': bid_prices,
                'ask_price': ask_prices,
                'bid_volume': bid_volumes,
                'ask_volume': ask_volumes
            }
        return None
    except Exception as e:
        print('Get orderbook for %s failed: %s' % (symbol, str(e)))
        return None


# ==================== QMT Callback Functions ====================
def init(context):
    '''QMT strategy initialization'''
    print('=' * 60)
    print('DeepSearch QMT Dynamic Data Push Service')
    print('=' * 60)
    print('Start time: %s' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print('Server: %s:%d' % (SERVER_HOST, SERVER_PORT))
    print('-' * 60)

    # Connect to server
    if not connect_server():
        print('Warning: Cannot connect to server, will retry in handle_data')

    # Initialize context
    context.last_status_time = time.time()
    context.tick_count = 0
    context.last_reconnect_time = 0
    context.last_server_check = 0

    print('Initialization complete')


def handle_data(context):
    '''QMT data handler (called periodically)'''
    global g_socket, g_stats, g_subscribed, DEBUG_MODE

    # Check connection
    if not g_socket:
        if time.time() - context.last_reconnect_time > 10:
            context.last_reconnect_time = time.time()
            reconnect()

    # Send heartbeat every 30 seconds
    if g_socket and (g_stats['last_heartbeat'] is None or
                     time.time() - g_stats['last_heartbeat'] > 30):
        send_heartbeat()

    # Check for server messages
    if g_socket and time.time() - context.last_server_check > 0.5:
        context.last_server_check = time.time()
        msg = receive_message()
        if msg:
            process_server_message(msg)

    # Get and send market data
    if g_socket and g_subscribed:
        try:
            from xtquant import xtdata

            batch_data = []

            for symbol in g_subscribed:
                try:
                    # Get latest tick
                    tick = xtdata.get_market_data_ex(
                        stock_list=[symbol],
                        period='tick',
                        count=1
                    )

                    if tick and symbol in tick:
                        data = tick[symbol]
                        if len(data) > 0:
                            latest = data.iloc[-1]

                            # Build message
                            tick_msg = {
                                'type': 'TICK',
                                'data': {
                                    'symbol': symbol,
                                    'timestamp': time.time(),
                                    'last_price': float(latest.get('lastPrice', 0)),
                                    'volume': int(latest.get('volume', 0)),
                                    'amount': float(latest.get('amount', 0)),
                                    'open': float(latest.get('open', 0)),
                                    'high': float(latest.get('high', 0)),
                                    'low': float(latest.get('low', 0)),
                                    'pre_close': float(latest.get('preClose', 0))
                                }
                            }

                            batch_data.append(tick_msg)
                            context.tick_count += 1

                except Exception as e:
                    print('Get %s data failed: %s' % (symbol, str(e)))

            # Get and send orderbook data
            for symbol in g_subscribed:
                try:
                    orderbook = get_orderbook_data(symbol)
                    if orderbook:
                        level2_msg = {
                            'type': 'LEVEL2',
                            'data': {
                                'symbol': symbol,
                                'timestamp': time.time(),
                                'bid_price': orderbook['bid_price'],
                                'ask_price': orderbook['ask_price'],
                                'bid_volume': orderbook['bid_volume'],
                                'ask_volume': orderbook['ask_volume']
                            }
                        }
                        batch_data.append(level2_msg)
                        print('[Orderbook] Got data for %s: bid=%s, ask=%s' % (
                            symbol,
                            orderbook['bid_price'][0] if orderbook['bid_price'] else 'N/A',
                            orderbook['ask_price'][0] if orderbook['ask_price'] else 'N/A'
                        ))
                except Exception as e:
                    print('Get orderbook for %s failed: %s' % (symbol, str(e)))

            # Send batch data
            if batch_data:
                batch_msg = {
                    'type': 'BATCH',
                    'count': len(batch_data),
                    'data': batch_data
                }

                if not send_message(batch_msg):
                    print('Send failed, will retry')
                else:
                    print('[Batch] Sent %d messages (Tick+Orderbook)' % len(batch_data))

        except ImportError:
            # 在调试模式下使用模拟数据
            if DEBUG_MODE:
                batch_data = []

                for symbol in g_subscribed:
                    # 生成模拟tick数据
                    tick_data = generate_mock_tick(symbol)

                    tick_msg = {
                        'type': 'TICK',
                        'data': tick_data
                    }

                    batch_data.append(tick_msg)
                    context.tick_count += 1

                # Add mock orderbook data
                for symbol in g_subscribed:
                    orderbook = get_orderbook_data(symbol)
                    if orderbook:
                        level2_msg = {
                            'type': 'LEVEL2',
                            'data': {
                                'symbol': symbol,
                                'timestamp': time.time(),
                                'bid_price': orderbook['bid_price'],
                                'ask_price': orderbook['ask_price'],
                                'bid_volume': orderbook['bid_volume'],
                                'ask_volume': orderbook['ask_volume']
                            }
                        }
                        batch_data.append(level2_msg)

                # Send batch data
                if batch_data:
                    batch_msg = {
                        'type': 'BATCH',
                        'count': len(batch_data),
                        'data': batch_data
                    }

                    if send_message(batch_msg):
                        print('[Mock] Sent %d messages (Tick+Orderbook)' % len(batch_data))
                    else:
                        print('[Mock] Send failed, will retry')
        except Exception as e:
            print('Data processing error: %s' % str(e))

    # Print status periodically
    if time.time() - context.last_status_time > 30:
        context.last_status_time = time.time()
        print('[Status] Sent: %d, Errors: %d, Ticks: %d, Subscribed: %d' % (
            g_stats['sent_count'],
            g_stats['error_count'],
            context.tick_count,
            len(g_subscribed)
        ))


def on_order_response(context, order):
    '''Order response callback'''
    pass


def on_trade(context, trade):
    '''Trade callback'''
    pass


def exit(context):
    '''QMT strategy exit'''
    print('Strategy exiting...')

    disconnect_server()

    print('Final stats - Sent: %d, Errors: %d' % (
        g_stats['sent_count'],
        g_stats['error_count']
    ))
    print('Cleanup complete')


# ==================== Debug Mode ====================
if __name__ == '__main__':
    # Standalone test mode
    print('=' * 60)
    print('QMT Dynamic Data Push - Debug Mode')
    print('=' * 60)
    print('Press Ctrl+C to stop')
    print('-' * 60)

    # Set debug mode flag
    DEBUG_MODE = True


    class MockContext:
        pass


    ctx = MockContext()

    # Initialize
    init(ctx)

    # Continuous run until interrupted
    try:
        iteration = 0
        while g_running:
            iteration += 1
            handle_data(ctx)

            # Print progress every 10 iterations
            if iteration % 10 == 0:
                print('[Debug] Iteration %d, Running for %d seconds' %
                      (iteration, iteration))

            time.sleep(1)

    except KeyboardInterrupt:
        print('\nUser interrupted, shutting down gracefully...')
        g_running = False
    except Exception as e:
        print('Unexpected error: %s' % str(e))
        g_running = False
    finally:
        exit(ctx)
        print('Debug mode ended')
