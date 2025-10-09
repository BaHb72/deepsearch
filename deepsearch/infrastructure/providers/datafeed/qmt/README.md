# QMT 集成模块

## 概述

本模块提供了DeepSearch系统与迅投QMT量化交易终端的集成能力，实现实时行情数据接收、交易指令执行等功能。

## 目录结构

```
qmt/
├── scripts/               # QMT内运行的Python脚本
│   ├── market_data_sender.py  # 行情数据推送脚本
│   ├── trade_executor.py       # 交易执行脚本
│   └── account_monitor.py      # 账户监控脚本
├── models/                # 数据模型定义
│   ├── tick.py           # Tick和盘口数据模型
│   └── trade.py          # 交易相关数据模型
└── README.md             # 本文档
```

## 快速开始

### 1. QMT端配置

1. 将 `scripts/market_data_sender.py` 复制到QMT的Python策略目录
2. 在QMT中创建新的Python策略
3. 修改脚本中的服务器配置：
   ```python
   context.sender = MarketDataSender(
       server_host="127.0.0.1",  # DeepSearch服务器地址
       server_port=9999,          # 端口
       auth_token="your-token"    # 认证令牌
   )
   ```
4. 添加需要订阅的股票代码
5. 运行策略

### 2. DeepSearch端配置

在 `settings.yaml` 中配置QMT接收服务：

```yaml
qmt:
  enabled: true
  receiver:
    tcp_port: 9999
    websocket_port: 9998
    host: "0.0.0.0"
  security:
    enable_auth: true
    token: "your-secure-token"
  data:
    batch_size: 100
    flush_interval: 0.1
```

### 3. 启动顺序

1. 先启动DeepSearch系统：
   ```bash
   python -m deepsearch run
   ```

2. 确认QMT接收服务已启动（查看日志）

3. 在QMT中运行行情推送策略

## 数据格式

### Tick数据

```json
{
  "type": "TICK",
  "data": {
    "symbol": "000001.SZ",
    "timestamp": 1234567890.123,
    "last_price": 12.34,
    "volume": 1000000,
    "amount": 12340000.0,
    "bid_price": [12.33, 12.32, ...],
    "ask_price": [12.34, 12.35, ...],
    "bid_volume": [1000, 2000, ...],
    "ask_volume": [1500, 2500, ...]
  }
}
```

### Level2十档盘口

```json
{
  "type": "LEVEL2",
  "data": {
    "symbol": "000001.SZ",
    "timestamp": 1234567890.123,
    "bid_price": [/* 10档买价 */],
    "ask_price": [/* 10档卖价 */],
    "bid_volume": [/* 10档买量 */],
    "ask_volume": [/* 10档卖量 */],
    "bid_count": [/* 委托笔数 */],
    "ask_count": [/* 委托笔数 */]
  }
}
```

## 通信协议

### TCP协议

- 消息格式：4字节长度 + JSON数据
- 长度使用网络字节序（big-endian）
- 支持批量发送

### 消息类型

- `AUTH`: 认证消息
- `TICK`: Tick数据
- `LEVEL2`: 十档盘口数据
- `BATCH`: 批量数据
- `HEARTBEAT`: 心跳消息
- `DISCONNECT`: 断开连接

## 监控和调试

### 查看连接状态

访问WebUI的QMT监控页面：
```
http://localhost:8000/api/qmt/status
```

### 日志位置

- QMT端日志：QMT安装目录/userdata/log/
- DeepSearch端日志：logs/deepsearch.log

### 常见问题

1. **连接失败**
   - 检查防火墙设置
   - 确认端口未被占用
   - 验证服务器地址

2. **数据延迟**
   - 调整批处理参数
   - 检查网络延迟
   - 优化数据处理逻辑

3. **订阅失败**
   - 确认股票代码格式正确
   - 检查QMT行情权限
   - 查看QMT日志

## 性能优化

### 批处理设置

```python
# 调整批处理大小和超时
batch_size = 100      # 批量大小
batch_timeout = 0.1   # 批量超时（秒）
```

### 内存优化

```python
# 调整队列大小
queue_size = 10000    # 数据队列大小
```

### 网络优化

- 使用内网IP减少延迟
- 启用TCP_NODELAY选项
- 调整系统TCP缓冲区大小

## 扩展开发

### 添加新的数据类型

1. 在 `models/` 中定义数据模型
2. 在QMT脚本中添加数据处理逻辑
3. 在接收端添加对应的事件处理

### 自定义指标计算

可以在QMT端进行实时指标计算后推送：
```python
def calculate_custom_indicator(tick_data):
    # 自定义指标计算
    return indicator_value
```

## 安全建议

1. 使用强认证令牌
2. 限制IP访问范围
3. 启用SSL/TLS加密（生产环境）
4. 定期更新认证令牌
5. 监控异常连接行为

## 联系支持

如有问题，请查看：
- DeepSearch文档：docs/
- QMT官方文档：http://www.xtquant.com/
- 提交Issue：https://github.com/your-repo/issues