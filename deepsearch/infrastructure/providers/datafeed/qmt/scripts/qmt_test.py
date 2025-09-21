# encoding:gbk
"""
QMT Test Script - Development & Debug
QMT测试脚本，用于开发调试
Author: DeepSearch Team
Version: 1.0.0
"""

import json
import socket
import time
import threading
import random
from datetime import datetime

# ==================== Configuration ====================
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 9999
AUTH_TOKEN = 'prod-secure-token-change-this'

# 测试配置
TEST_SYMBOLS = ['000001.SZ', '000002.SZ', '600000.SH', '600519.SH', '000858.SZ']
ENABLE_VERBOSE_LOG = True  # 详细日志
ENABLE_PERFORMANCE_LOG = True  # 性能日志
LOG_FILE = 'qmt_test_%s.log' % datetime.now().strftime("%Y%m%d_%H%M%S")

# ==================== Global State ====================
g_socket = None
g_connected = False
g_running = True
g_log_file = None

# 性能统计
g_perf_stats = {
    'connect_time': [],
    'send_time': [],
    'receive_time': [],
    'total_sent': 0,
    'total_received': 0,
    'total_errors': 0,
    'start_time': time.time()
}


# ==================== Logging Functions ====================
def log(level, message):
    """增强的日志函数"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    log_msg = '[%s] [%-8s] %s' % (timestamp, level, message)
    
    # 控制台输出
    print(log_msg)
    
    # 写入文件
    if g_log_file:
        g_log_file.write(log_msg + '\n')
        g_log_file.flush()


def log_performance(operation, duration):
    """记录性能数据"""
    if ENABLE_PERFORMANCE_LOG:
        if operation + '_time' not in g_perf_stats:
            g_perf_stats[operation + '_time'] = []
        
        g_perf_stats[operation + '_time'].append(duration)
        avg_time = sum(g_perf_stats[operation + '_time']) / len(g_perf_stats[operation + '_time'])
        log('PERF', '%s: %.3fs (avg: %.3fs)' % (operation, duration, avg_time))


# ==================== Test Data Generation ====================
def generate_mock_tick(symbol):
    """生成模拟tick数据"""
    base_prices = {
        '000001.SZ': 10.5,   # 平安银行
        '000002.SZ': 15.8,   # 万科A
        '600000.SH': 5.2,    # 浦发银行
        '600519.SH': 1850.0, # 贵州茅台
        '000858.SZ': 280.0   # 五粮液
    }
    
    base_price = base_prices.get(symbol, 10.0)
    variation = random.uniform(-0.02, 0.02)  # 2%波动
    
    current_price = base_price * (1 + variation)
    
    return {
        'symbol': symbol,
        'timestamp': time.time(),
        'last_price': round(current_price, 2),
        'open': round(base_price, 2),
        'high': round(current_price * 1.01, 2),
        'low': round(current_price * 0.99, 2),
        'volume': random.randint(100000, 10000000),
        'amount': random.randint(10000000, 100000000),
        'bid_price': [round(current_price - i * 0.01, 2) for i in range(1, 6)],
        'bid_volume': [random.randint(100, 10000) * 100 for _ in range(5)],
        'ask_price': [round(current_price + i * 0.01, 2) for i in range(1, 6)],
        'ask_volume': [random.randint(100, 10000) * 100 for _ in range(5)],
        'turnover_rate': round(random.uniform(0.1, 5.0), 2),
        'pe_ratio': round(random.uniform(10, 50), 2)
    }


def generate_mock_kline(symbol, period='1d', count=10):
    """生成模拟K线数据"""
    base_price = 10.0
    klines = []
    
    for i in range(count):
        open_price = base_price + random.uniform(-0.5, 0.5)
        close_price = open_price + random.uniform(-0.3, 0.3)
        high_price = max(open_price, close_price) + random.uniform(0, 0.2)
        low_price = min(open_price, close_price) - random.uniform(0, 0.2)
        
        klines.append({
            'time': time.time() - (count - i) * 86400,
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': random.randint(1000000, 10000000),
            'amount': random.randint(10000000, 100000000)
        })
        
        base_price = close_price
    
    return klines


# ==================== Network Functions ====================
def test_connection():
    """测试连接"""
    global g_socket, g_connected
    
    log('INFO', 'Testing connection to %s:%d...' % (SERVER_HOST, SERVER_PORT))
    start_time = time.time()
    
    try:
        # 创建socket
        g_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        g_socket.settimeout(5)
        
        # 连接
        g_socket.connect((SERVER_HOST, SERVER_PORT))
        connect_time = time.time() - start_time
        
        log('SUCCESS', 'Connected in %.3fs' % connect_time)
        log_performance('connect', connect_time)
        
        # 发送认证
        auth_msg = {
            'type': 'AUTH',
            'token': AUTH_TOKEN,
            'client': 'QMT_TEST',
            'version': '1.0.0',
            'test_mode': True,
            'capabilities': ['test', 'debug', 'mock_data']
        }
        
        if send_test_message(auth_msg):
            log('SUCCESS', 'Authentication sent')
            g_connected = True
            
            # 尝试接收响应
            response = receive_test_message(timeout=2)
            if response:
                log('SUCCESS', 'Auth response: %s' % str(response))
            
            return True
        else:
            log('ERROR', 'Failed to send authentication')
            return False
            
    except socket.timeout:
        log('ERROR', 'Connection timeout')
        return False
    except Exception as e:
        log('ERROR', 'Connection failed: %s' % str(e))
        return False


def send_test_message(msg):
    """发送测试消息"""
    global g_socket, g_perf_stats
    
    if not g_socket:
        return False
    
    try:
        start_time = time.time()
        
        msg_str = json.dumps(msg, ensure_ascii=False) + '\n'
        g_socket.sendall(msg_str.encode('utf-8'))
        
        send_time = time.time() - start_time
        g_perf_stats['total_sent'] += 1
        
        if ENABLE_VERBOSE_LOG:
            log('DEBUG', 'Sent: %s...' % msg_str.strip()[:100])
        
        log_performance('send', send_time)
        return True
        
    except Exception as e:
        log('ERROR', 'Send failed: %s' % str(e))
        g_perf_stats['total_errors'] += 1
        return False


def receive_test_message(timeout=0.1):
    """接收测试消息"""
    global g_socket, g_perf_stats
    
    if not g_socket:
        return None
    
    try:
        start_time = time.time()
        g_socket.settimeout(timeout)
        
        data = g_socket.recv(4096)
        if not data:
            return None
        
        receive_time = time.time() - start_time
        g_perf_stats['total_received'] += 1
        
        msg_str = data.decode('utf-8').strip()
        if msg_str:
            msg = json.loads(msg_str)
            
            if ENABLE_VERBOSE_LOG:
                log('DEBUG', 'Received: %s...' % msg_str[:100])
            
            log_performance('receive', receive_time)
            return msg
            
    except socket.timeout:
        return None
    except Exception as e:
        log('ERROR', 'Receive failed: %s' % str(e))
        g_perf_stats['total_errors'] += 1
        return None


# ==================== Test Scenarios ====================
def test_tick_data():
    """测试tick数据推送"""
    log('INFO', '=== Testing Tick Data Push ===')
    
    for symbol in TEST_SYMBOLS:
        tick = generate_mock_tick(symbol)
        msg = {
            'type': 'TICK',
            'data': tick
        }
        
        if send_test_message(msg):
            log('SUCCESS', 'Tick sent for %s' % symbol)
        else:
            log('ERROR', 'Failed to send tick for %s' % symbol)
        
        time.sleep(0.1)


def test_kline_data():
    """测试K线数据"""
    log('INFO', '=== Testing K-Line Data ===')
    
    for symbol in TEST_SYMBOLS[:2]:  # 只测试前两个
        klines = generate_mock_kline(symbol, '1d', 5)
        msg = {
            'type': 'HISTORY_DATA',
            'symbol': symbol,
            'period': '1d',
            'data': klines
        }
        
        if send_test_message(msg):
            log('SUCCESS', 'K-line sent for %s, %d bars' % (symbol, len(klines)))
        else:
            log('ERROR', 'Failed to send K-line for %s' % symbol)
        
        time.sleep(0.2)


def test_subscription():
    """测试订阅功能"""
    log('INFO', '=== Testing Subscription ===')
    
    # 发送订阅请求
    sub_msg = {
        'type': 'SUBSCRIBE',
        'symbols': TEST_SYMBOLS
    }
    
    if send_test_message(sub_msg):
        log('SUCCESS', 'Subscription request sent for %d symbols' % len(TEST_SYMBOLS))
    
    # 等待响应
    response = receive_test_message(timeout=2)
    if response:
        log('SUCCESS', 'Subscription response: %s' % str(response))


def test_heartbeat():
    """测试心跳"""
    log('INFO', '=== Testing Heartbeat ===')
    
    heartbeat_msg = {'type': 'HEARTBEAT'}
    
    for i in range(3):
        if send_test_message(heartbeat_msg):
            log('SUCCESS', 'Heartbeat %d sent' % (i+1))
            
            response = receive_test_message(timeout=1)
            if response and response.get('type') == 'HEARTBEAT_RESPONSE':
                log('SUCCESS', 'Heartbeat response received')
        
        time.sleep(1)


def test_stress():
    """压力测试"""
    log('INFO', '=== Stress Test ===')
    
    start_time = time.time()
    message_count = 100
    
    for i in range(message_count):
        symbol = random.choice(TEST_SYMBOLS)
        tick = generate_mock_tick(symbol)
        msg = {
            'type': 'TICK',
            'data': tick
        }
        
        send_test_message(msg)
        
        if (i + 1) % 10 == 0:
            log('INFO', 'Sent %d/%d messages' % (i + 1, message_count))
    
    duration = time.time() - start_time
    rate = message_count / duration
    
    log('SUCCESS', 'Stress test completed: %d messages in %.2fs (%.1f msg/s)' % 
        (message_count, duration, rate))


def continuous_push_thread():
    """连续推送线程（模拟真实环境）"""
    global g_running, g_connected
    
    log('INFO', 'Continuous push thread started')
    
    while g_running and g_connected:
        try:
            # 随机选择股票
            symbol = random.choice(TEST_SYMBOLS)
            tick = generate_mock_tick(symbol)
            
            msg = {
                'type': 'TICK',
                'data': tick
            }
            
            send_test_message(msg)
            
            # 随机延迟，模拟真实tick频率
            time.sleep(random.uniform(0.1, 0.5))
            
        except Exception as e:
            log('ERROR', 'Push thread error: %s' % str(e))
            time.sleep(1)


# ==================== Main Test Function ====================
def main():
    """主测试函数"""
    global g_running, g_log_file
    
    # 打开日志文件
    try:
        g_log_file = open(LOG_FILE, 'w', encoding='gbk')
        log('INFO', 'Log file: %s' % LOG_FILE)
    except Exception as e:
        print('Failed to open log file: %s' % str(e))
    
    print('=' * 70)
    print('QMT Test Script v1.0.0')
    print('=' * 70)
    
    # 1. 测试连接
    if not test_connection():
        log('ERROR', 'Connection test failed, exiting...')
        return
    
    # 2. 运行测试场景
    try:
        test_subscription()
        time.sleep(1)
        
        test_tick_data()
        time.sleep(1)
        
        test_kline_data()
        time.sleep(1)
        
        test_heartbeat()
        time.sleep(1)
        
        # 3. 可选：压力测试
        user_input = raw_input('\nRun stress test? (y/n): ') if hasattr(__builtins__, 'raw_input') else input('\nRun stress test? (y/n): ')
        if user_input.lower() == 'y':
            test_stress()
        
        # 4. 可选：连续推送
        user_input = raw_input('\nStart continuous push? (y/n): ') if hasattr(__builtins__, 'raw_input') else input('\nStart continuous push? (y/n): ')
        if user_input.lower() == 'y':
            # 启动推送线程
            push_thread = threading.Thread(target=continuous_push_thread)
            push_thread.daemon = True
            push_thread.start()
            
            log('INFO', 'Continuous push started, press Ctrl+C to stop')
            
            while g_running:
                time.sleep(1)
                
                # 定期打印统计
                if int(time.time()) % 10 == 0:
                    uptime = int(time.time() - g_perf_stats['start_time'])
                    log('STATS', 
                        'Uptime: %ds, Sent: %d, Received: %d, Errors: %d' %
                        (uptime, g_perf_stats["total_sent"], 
                         g_perf_stats["total_received"], g_perf_stats["total_errors"]))
        
    except KeyboardInterrupt:
        log('INFO', 'Test interrupted by user')
    
    except Exception as e:
        log('ERROR', 'Test error: %s' % str(e))
    
    finally:
        # 清理
        g_running = False
        
        if g_socket:
            try:
                g_socket.close()
                log('INFO', 'Connection closed')
            except:
                pass
        
        # 打印最终统计
        print('\n' + '=' * 70)
        print('Test Summary:')
        print('  Total sent: %d' % g_perf_stats["total_sent"])
        print('  Total received: %d' % g_perf_stats["total_received"])
        print('  Total errors: %d' % g_perf_stats["total_errors"])
        
        if g_perf_stats.get('connect_time'):
            avg_connect = sum(g_perf_stats["connect_time"]) / len(g_perf_stats["connect_time"])
            print('  Avg connect time: %.3fs' % avg_connect)
        if g_perf_stats.get('send_time'):
            avg_send = sum(g_perf_stats["send_time"]) / len(g_perf_stats["send_time"])
            print('  Avg send time: %.6fs' % avg_send)
        if g_perf_stats.get('receive_time'):
            avg_receive = sum(g_perf_stats["receive_time"]) / len(g_perf_stats["receive_time"])
            print('  Avg receive time: %.6fs' % avg_receive)
        
        print('=' * 70)
        
        if g_log_file:
            g_log_file.close()
            print('Log saved to: %s' % LOG_FILE)


if __name__ == '__main__':
    main()