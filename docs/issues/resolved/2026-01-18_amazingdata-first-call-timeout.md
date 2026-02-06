# SDK 架构导致首次调用超时

> 发现日期: 2026-01-18
> 发现位置: packages/core/compute/actors/amazingdata_actor.py
> 类型: architecture
> 严重程度: high
> 状态: open

---

## 问题描述

首次调用 get_calendar 会触发完整的 SDK 登录流程，总耗时可能超过 45s 超时阈值，导致超时失败。

### 现象

```
2026-01-18 22:05:29.293  ERROR [AmazingData/Dask] 调用超时 | method=get_calendar | timeout=45.0s
2026-01-18 22:05:29.294   INFO [AmazingData/Dask] 重试 1/3
```

### 登录流程耗时分解

| 步骤 | 操作 | 超时设置 | 实际耗时 |
|------|------|---------|---------|
| 1.5 | 预清理 logout | 1s | ~1s |
| 2 | sdk.login() | 30s | 15-30s |
| 3 | BaseData 初始化 | - | <1ms |
| 4 | get_calendar() | 30s | 15-30s |
| 5 | MarketData 初始化 | - | <1ms |
| **总计** | | | **30-60s** |

### 影响

- 系统启动后首次调用 API 必定超时（45s < 60s）
- 重试机制会触发，但每次重试都要完整登录，浪费资源
- 用户体验差：首次访问总是失败

---

## 发现上下文

> 在分析 get_calendar 超时问题时发现登录流程是主要耗时来源

通过添加详细日志分析发现，登录只需 2.9s，但整个首次调用流程需要 30-60s。

---

## 相关代码

### amazingdata_actor.py:42

```python
# SDK 登录超时配置
config.timeout = 30  # SDK 内部超时
```

### amazingdata_actor.py:332

```python
# BaseData 初始化，触发登录
def initialize_base_data(self):
    self.sdk.login()  # 15-30s
    self.base_data = BaseData(self.sdk)
```

### dask_adapter.py:91

```python
# 外层超时 45s，不足以覆盖完整登录流程
timeout: float = 45.0
```

---

## 建议修复方案

### 方案 A: 增加首次调用超时

```python
# 区分首次调用和后续调用的超时
first_call_timeout: float = 90.0  # 首次调用，含登录
normal_timeout: float = 45.0       # 后续调用
```

### 方案 B: 启用预热机制（推荐）

```yaml
# settings.dev.yaml
amazingdata:
  prewarm: true  # Worker 启动时完成登录
```

```python
# amazingdata_actor.py
async def on_worker_start():
    """Worker 启动时预热登录"""
    await sdk.login()
    await base_data.get_calendar()  # 预热缓存
```

### 方案 C: 异步登录 + 就绪信号

```python
# 登录异步进行，API 调用等待就绪
class AmazingDataActor:
    ready_event: asyncio.Event

    async def wait_ready(self, timeout: float = 90.0):
        await asyncio.wait_for(self.ready_event.wait(), timeout)
```

### 预估工作量

- [ ] 小（< 30 分钟）- 方案 A
- [x] 中（30分钟 - 2小时）- 方案 B/C

---

## 备注

- 方案 B 是最佳实践：消除用户感知的延迟
- 需要配合 Issue #1（超时配置未被使用）一起修复
- SDK 使用 TGW 协议，有额外的初始化开销
