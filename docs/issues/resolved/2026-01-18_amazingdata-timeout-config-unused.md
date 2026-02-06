# AmazingData SDK 超时配置未被使用

> 发现日期: 2026-01-18
> 发现位置: apps/api/server.py:786
> 类型: config
> 严重程度: high
> 状态: open

---

## 问题描述

server.py 创建 DaskAdapter 时未传递 timeout 参数，导致配置文件中的超时设置（如 5.0s）被忽略，实际使用 dask_adapter.py 中硬编码的 45.0s。

### 现象

```python
# server.py:786 - 未传递 timeout 参数
adapter = AmazingDataDaskAdapter(
    dask_client=dask_client,
    redis_client=redis_client,
    # timeout=??? 缺失
)

# dask_adapter.py:91-93 - 硬编码默认值
def __init__(
    self,
    timeout: float = 45.0,  # 硬编码，配置文件的值被忽略
    ...
)
```

### 影响

- 配置文件中的超时设置无效，用户无法通过配置调整超时
- 首次调用时可能因超时不足而失败（登录流程需要 30-60s）
- 调试困难：配置文件显示 5.0s，实际运行却是 45.0s

---

## 发现上下文

> 在分析 get_calendar 超时问题时发现此配置传递断层

调查 `ERROR [AmazingData/Dask] 调用超时 | method=get_calendar | timeout=45.0s` 错误日志时，发现超时值与配置文件不匹配。

---

## 相关代码

### 配置文件 (settings.dev.yaml)

```yaml
amazingdata:
  timeout: 5.0  # 期望的超时值
```

### server.py:786

```python
# 创建 adapter 时未传递 timeout
adapter = AmazingDataDaskAdapter(
    dask_client=dask_client,
    redis_client=redis_client,
)
```

### dask_adapter.py:91

```python
def __init__(
    self,
    dask_client: Client,
    redis_client: Redis | None = None,
    timeout: float = 45.0,  # 硬编码默认值
    ...
)
```

---

## 建议修复方案

### 方案 A: 传递配置值

```python
# server.py
timeout = config.get("amazingdata", {}).get("timeout", 45.0)
adapter = AmazingDataDaskAdapter(
    dask_client=dask_client,
    redis_client=redis_client,
    timeout=timeout,
)
```

### 方案 B: 依赖注入（更彻底）

创建 TimeoutConfig 类，统一管理所有超时配置：

```python
class TimeoutConfig(BaseModel):
    client_timeout: float = 45.0
    first_call_timeout: float = 90.0
    sdk_timeout: float = 30.0
```

### 预估工作量

- [x] 小（< 30 分钟）- 方案 A
- [ ] 中（30分钟 - 2小时）- 方案 B

---

## 备注

此问题与 Issue #2（SDK 架构导致首次调用超时）相关，建议一起修复。
