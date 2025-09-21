# QMT 实时订阅机制实现文档

## 项目背景

当前QMT数据采集系统存在以下问题：
1. 采集器使用硬编码的股票列表，无法动态响应服务器请求
2. 服务器端的订阅功能只在本地记录，没有通知采集器
3. 采集器没有发送Level2盘口数据，导致API返回空数据

## 实现目标

建立服务器与采集器之间的完善信号机制，实现：
- 服务器按需向采集器发送订阅/取消订阅请求
- 采集器根据服务器指令动态订阅股票
- 采集器推送TICK和Level2盘口数据
- 双向通信确认机制

## 架构设计

### 通信流程

```
用户请求 → Web API → QMT Gateway → TCP消息 → QMT Collector → QMT终端
                                          ↓
用户响应 ← Web API ← QMT Gateway ← TCP消息 ← 数据推送
```

### 消息协议

#### 1. 订阅请求（服务器→采集器）
```json
{
    "type": "SUBSCRIBE",
    "symbols": ["601606.SH", "000001.SZ"],
    "data_types": ["TICK", "LEVEL2"],
    "request_id": "req_123456"
}
```

#### 2. 订阅响应（采集器→服务器）
```json
{
    "type": "SUBSCRIBE_RESPONSE",
    "request_id": "req_123456",
    "status": "OK",
    "subscribed": ["601606.SH", "000001.SZ"],
    "message": "Successfully subscribed"
}
```

#### 3. Level2数据推送（采集器→服务器）
```json
{
    "type": "LEVEL2",
    "data": {
        "symbol": "601606.SH",
        "timestamp": 1755494688,
        "bid_price": [10.12, 10.11, 10.10, 10.09, 10.08],
        "bid_volume": [1000, 2000, 3000, 4000, 5000],
        "ask_price": [10.13, 10.14, 10.15, 10.16, 10.17],
        "ask_volume": [1500, 2500, 3500, 4500, 5500]
    }
}
```

#### 4. 取消订阅（服务器→采集器）
```json
{
    "type": "UNSUBSCRIBE",
    "symbols": ["601606.SH"],
    "request_id": "req_123457"
}
```

## 实现步骤

### Phase 1: 服务器端改进

#### 1.1 修改 QMTReceiver (receiver.py)
- 添加向客户端发送消息的功能
- 维护客户端连接映射
- 实现消息路由

#### 1.2 修改 QMTGateway (gateway.py)
- 改进subscribe()方法，发送TCP消息给采集器
- 添加请求跟踪机制
- 处理订阅响应

### Phase 2: 采集器端改进

#### 2.1 修改消息处理 (qmt_collector.py)
- 移除硬编码的default_symbols
- 改进subscribe_symbols()实现真正的QMT订阅
- 添加订阅响应机制

#### 2.2 添加Level2数据采集
- 实现get_orderbook_data()函数
- 在数据推送线程中发送Level2数据
- 处理盘口数据格式转换

### Phase 3: 集成测试

#### 3.1 功能测试
- 测试动态订阅601606股票
- 验证Level2数据推送
- 检查API返回正确的盘口数据

#### 3.2 性能测试
- 多股票同时订阅
- 高频数据推送稳定性
- 网络断线重连机制

## 实现详情

### 修改文件列表

1. ✅ `deepsearch/datafeed/qmt/receiver.py` - 已有发送消息功能，支持向客户端推送
2. ✅ `deepsearch/datafeed/qmt/gateway.py` - 实现订阅消息发送
3. ✅ `deepsearch/datafeed/qmt/scripts/qmt_collector.py` - 动态订阅和Level2数据  
4. `deepsearch/webui/api/qmt.py` - API端点优化（待测试）

### 关键代码改动

#### 1. Gateway订阅功能改进 (gateway.py)
```python
def subscribe(self, symbols: List[str]):
    """订阅股票并通知采集器"""
    # 添加到本地订阅列表
    for symbol in symbols:
        self.subscribed_symbols.add(symbol)
    
    # 向所有连接的采集器发送订阅请求
    if self.receiver and hasattr(self.receiver, 'client_writers'):
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        subscribe_msg = {
            'type': 'SUBSCRIBE',
            'symbols': symbols,
            'data_types': ['TICK', 'LEVEL2'],
            'request_id': request_id
        }
        
        # 发送给所有客户端
        asyncio.create_task(self._broadcast_to_collectors(subscribe_msg))
```

#### 2. 采集器动态订阅 (qmt_collector.py)
- 移除硬编码的default_symbols
- 添加SUBSCRIBE/UNSUBSCRIBE响应机制
- 处理SUBSCRIPTION_LIST消息

#### 3. Level2数据采集 (qmt_collector.py)
```python
def get_orderbook_data(symbol):
    """获取股票盘口数据(Level2)"""
    # 获取买盘和卖盘价格、数量
    bid_prices = data.get('bidPrice', [])
    bid_volumes = data.get('bidVol', [])
    ask_prices = data.get('askPrice', [])
    ask_volumes = data.get('askVol', [])
    
    return {
        'symbol': symbol,
        'timestamp': data.get('time', time.time()),
        'bid_price': bid_prices[:10],  # 取前10档
        'bid_volume': bid_volumes[:10],
        'ask_price': ask_prices[:10],
        'ask_volume': ask_volumes[:10]
    }
```

#### 4. 数据推送改进 (qmt_collector.py)
```python
def data_push_thread():
    # 同时采集和推送TICK和LEVEL2数据
    for symbol in g_subscribed:
        # 采集Tick数据
        tick_data = get_tick_data(symbol)
        if tick_data:
            tick_batch.append({'type': 'TICK', 'data': tick_data})
        
        # 采集盘口数据(Level2)
        orderbook_data = get_orderbook_data(symbol)
        if orderbook_data:
            orderbook_batch.append({'type': 'LEVEL2', 'data': orderbook_data})
```

## 测试计划

1. **单元测试**
   - 测试消息序列化/反序列化
   - 测试订阅状态管理
   - 测试数据格式转换

2. **集成测试**
   - 端到端订阅流程
   - 数据推送完整性
   - 错误处理和恢复

3. **用户验收测试**
   - 通过Web界面订阅601606
   - 查看实时盘口数据
   - 验证数据准确性

## 实施时间线

- Phase 1: 服务器端改进（2小时）✅ 完成
- Phase 2: 采集器端改进（3小时）✅ 完成
- Phase 3: 集成测试（1小时）🔄 进行中
- 总计：约6小时

## 风险与对策

| 风险 | 影响 | 对策 |
|-----|------|------|
| QMT API限制 | 无法获取Level2数据 | 使用模拟数据或降级到Level1 |
| 网络延迟 | 数据推送不及时 | 实现批量发送和压缩 |
| 并发订阅过多 | 系统资源耗尽 | 添加订阅数量限制 |

## 后续优化

1. 添加数据压缩减少网络带宽
2. 实现订阅优先级管理
3. 添加历史数据回放功能
4. 完善监控和告警机制

---

*文档创建时间：2025-01-18*
*作者：DeepSearch Team*