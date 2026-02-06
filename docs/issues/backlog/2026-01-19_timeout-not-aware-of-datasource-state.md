# 超时机制没有感知数据源的工作状态

> 发现日期: 2026-01-19
> 发现位置: apps/api/services/market_data_runtime.py:76-149
> 类型: architecture
> 严重程度: high
> 状态: open

---

## 问题描述

当前超时机制使用硬编码或配置文件中的固定值，没有考虑数据源的实际工作状态。当数据源正在执行耗时但正常的操作（如批量下载、首次登录）时，固定超时会错误地触发。

### 现象

用户日志显示：

```
strength fallback 超时（5秒），跳过 akshare fallback
板块数据获取超时 (第1次尝试, 60.01s), 准备重试...
板块数据预热总超时 (90.0s), 无可用缓存
```

同时，AkShare 可能正在下载 557 条数据（每条 1.2s），这是**正常但耗时的操作**。

### 当前超时配置（硬编码）

```python
# market_data_runtime.py
warmup_timeout = 90.0    # 预热总超时
fetch_timeout = 60.0     # 单次获取超时

# 其他地方
akshare_fallback_timeout = 5.0   # AkShare fallback 超时（太短）
```

### 问题本质

超时机制是"时间盲"的：

- 不知道数据源当前在做什么（空闲/连接中/批量下载）
- 不知道当前操作的预期耗时
- 无法区分"真正卡死"和"正常但慢"

---

## 发现上下文

> 分析板块数据预热超时日志时，发现超时触发与 AkShare 批量下载时间重叠。

---

## 相关代码

### market_data_runtime.py:76-99

```python
# 从配置读取预热参数
warmup_timeout = getattr(realtime_cfg, "warmup_timeout_seconds", 90.0)
fetch_timeout = getattr(realtime_cfg, "warmup_fetch_timeout_seconds", 60.0)
retry_count = getattr(realtime_cfg, "warmup_retry_count", 2)

# ...

async def _fetch_with_retry() -> bool:
    for attempt in range(retry_count + 1):
        try:
            await asyncio.wait_for(
                service.refresh_board_universe(), timeout=fetch_timeout  # 固定60s
            )
```

### 配置模型 (market_data.py)

```python
class RealtimeConfig(BaseModel):
    warmup_timeout_seconds: float = 90.0
    warmup_fetch_timeout_seconds: float = 60.0
    warmup_retry_count: int = 2
```

---

## 建议修复方案

### 方案 A: 分层超时配置（快速止血）

为不同场景配置不同超时值：

```yaml
timeout:
  akshare:
    fast_api: 5       # 单条数据请求
    batch_api: 180    # 批量数据（如 stock_list 557条）
  amazingdata:
    normal: 45
    first_call: 90    # 包含 SDK 登录
```

### 方案 B: 状态感知超时（彻底根治）

创建 `TimeoutManager` 统一管理超时逻辑：

```python
from enum import Enum
from dataclasses import dataclass

class DataSourceState(Enum):
    IDLE = "idle"               # 空闲
    CONNECTING = "connecting"   # 连接中（如 SDK 登录）
    FETCHING = "fetching"       # 获取数据中
    BATCH_FETCHING = "batch_fetching"  # 批量获取

@dataclass
class TimeoutConfig:
    idle_timeout: float = 5.0
    connect_timeout: float = 90.0
    fetch_timeout: float = 30.0
    batch_timeout: float = 300.0

class TimeoutManager:
    def __init__(self):
        self._source_states: dict[str, DataSourceState] = {}
        self._configs: dict[str, TimeoutConfig] = {}

    def get_timeout(self, source: str, operation: str = "fetch") -> float:
        """根据数据源状态返回适当的超时时间"""
        state = self._source_states.get(source, DataSourceState.IDLE)
        config = self._configs.get(source, TimeoutConfig())

        if state == DataSourceState.BATCH_FETCHING:
            return config.batch_timeout
        elif state == DataSourceState.CONNECTING:
            return config.connect_timeout
        else:
            return config.fetch_timeout

    def set_state(self, source: str, state: DataSourceState):
        """设置数据源状态"""
        self._source_states[source] = state
```

### 集成点

1. **AkShare 适配器** - 下载批量数据前设置 `BATCH_FETCHING` 状态
2. **AmazingData Actor** - 登录前设置 `CONNECTING` 状态
3. **板块数据预热** - 查询 `TimeoutManager.get_timeout()` 而非硬编码

### 预估工作量

- [ ] 小（< 30 分钟）- 方案 A
- [x] 中（1-2小时）- 方案 B（推荐）

---

## 文件修改清单

| 文件 | 修改内容 |
|------|----------|
| `packages/core/utils/timeout/__init__.py` | **新建** |
| `packages/core/utils/timeout/timeout_manager.py` | **新建** - 核心类 |
| `packages/core/utils/timeout/config.py` | **新建** - 配置模型 |
| `apps/api/services/market_data_runtime.py` | 使用 TimeoutManager |
| `akshare_adapter.py` / `akshare_direct.py` | 设置批量状态 |
| `amazingdata_actor.py` | 设置连接状态 |

---

## 备注

此问题与 Issue #1（stock_list 数据源优先级）相关。如果 stock_list 改为 AmazingData 优先，可以部分缓解超时问题，但不能根本解决。

建议实施方案 B，从架构层面解决超时管理问题。

---

## 2026-02-07 更新

### 已解决部分

- **方案 B 核心框架已实现**：`TimeoutManager` + `DataSourceState` 枚举 + `TimeoutConfig` 数据类
- **YAML 配置化完成**：`TimeoutsConfig` Pydantic 模型（`packages/core/config/models/timeouts.py`），dev/prod 环境独立配置
- **桥接层完成**：`load_timeout_configs_from_settings()` 将 Pydantic Settings 导入 TimeoutManager
- **主要调用点已集成**：`dask_init_state.py`、`market_data_runtime.py`、`dask_worker_manager.py`、`server.py`、`server_manager.py`

### 残余项

- 更多调用点集成状态感知 API（如 AkShare batch 操作、Redis 健康检查等边缘场景）
- `TimeoutManager.get_timeout()` 的状态感知逻辑可进一步细化（当前主要区分 IDLE/CONNECTING/FETCHING/BATCH_FETCHING）
