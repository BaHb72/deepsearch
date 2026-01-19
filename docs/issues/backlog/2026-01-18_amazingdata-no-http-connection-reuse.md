# SDK 无 HTTP 连接复用

> 发现日期: 2026-01-18
> 发现位置: packages/core/infrastructure/providers/implementations/amazingdata/
> 类型: performance
> 严重程度: medium
> 状态: open

---

## 问题描述

每次 SDK 调用都新建 TCP/TLS 连接，是 15-30s 延迟的主要原因之一。SDK 未启用 HTTP 会话复用（Connection: keep-alive）。

### 现象

网络耗时分解（每次调用）：

| 阶段 | 耗时 |
|------|------|
| TCP 三次握手 | 10-15ms |
| TLS/SSL 握手 | 5-10ms |
| TGW 协议初始化 | 5-10s |
| 推送服务连接(端口600) | 5-10s |
| HTTP 请求/响应 | 200-500ms |
| 数据解析 | 100-200ms |
| **首次调用总计** | **10-20s** |

### 影响

- 每次调用都有 10-20ms 的连接建立开销
- TGW 协议初始化重复进行
- 高并发时连接数爆炸

---

## 发现上下文

> 在深入分析 get_calendar 超时原因时发现 SDK 网络架构问题

登录只需 2.9s，但 get_calendar 需要 15-30s，分析发现主要耗时在网络连接建立。

---

## 相关代码

### SDK 连接管理（推测）

```python
# amazingdata_extended.py:515 附近
# 每次请求新建连接，未复用
response = requests.get(url, ...)  # 未使用 Session
```

### 连接池配置过小

```python
# connection_manager.py:28-35
PoolConfig(
    min_size=1,
    max_size=10,  # 过小，高并发受限
    idle_timeout=300,
)
```

---

## 建议修复方案

### 方案 A: 启用 HTTP 会话复用

```python
# 创建全局 Session，复用连接
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
session.headers['Connection'] = 'keep-alive'

# 配置连接池
adapter = HTTPAdapter(
    pool_connections=20,
    pool_maxsize=50,
    max_retries=Retry(total=3, backoff_factor=0.5)
)
session.mount('http://', adapter)
session.mount('https://', adapter)
```

### 方案 B: 扩大连接池

```python
PoolConfig(
    min_size=5,    # 最小保持 5 个连接
    max_size=50,   # 最大 50 个连接
    idle_timeout=600,  # 空闲 10 分钟后关闭
)
```

### 方案 C: 禁用推送服务（如不需要实时数据）

检查是否可以禁用端口 600 的连接，减少登录时的网络往返。

### 方案 D: 添加网络性能监控

```python
import time

class NetworkMonitor:
    def log_request(self, url, start_time, end_time):
        duration = end_time - start_time
        logger.info(f"Network: {url} took {duration:.2f}s")
```

### 预估工作量

- [ ] 小（< 30 分钟）
- [x] 中（30分钟 - 2小时）- 方案 A+B
- [ ] 大（> 2小时）- 需要修改 SDK 内部

---

## 诊断建议

1. **启用 TGW 日志**：配置 `tgw_log_path` 捕获 SDK 内部时序
2. **检查网络连通性**：验证到 `101.230.159.234:8600` 和端口 600 的连通性
3. **监控连接复用率**：添加日志跟踪连接是否被复用

---

## 备注

- 此问题可能需要修改 SDK 内部代码，取决于 SDK 是否支持自定义 Session
- 建议先尝试方案 A+B，如果 SDK 不支持则考虑联系 SDK 供应商
- 与 Issue #2（首次调用超时）密切相关
