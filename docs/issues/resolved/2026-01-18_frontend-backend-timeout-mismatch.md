# 前后端超时配置不同步

> 发现日期: 2026-01-18
> 发现位置: apps/web/src/api/core/client.ts:78, packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py:91
> 类型: config
> 严重程度: medium
> 状态: resolved
> 解决日期: 2026-02-07
> 解决方式: request.ts 默认超时从 30s 提升到 90s，setupRequest() 启动时从后端 /api/config/timeouts 同步配置

---

## 问题描述

前端 API 客户端超时（30s）与后端 DaskAdapter 超时（45s）不一致，可能导致前端先超时，用户看到错误但后端仍在处理请求。

### 现象

```
时间线:
0s   - 前端发起请求
30s  - 前端超时，显示错误给用户
45s  - 后端完成处理（但前端已断开）
```

用户看到"请求超时"错误，但后端实际上成功了。

### 超时配置对比

| 层级 | 位置 | 超时值 | 硬编码/可配置 |
|------|------|--------|--------------|
| 前端 API | client.ts:78 | 30s | 硬编码 |
| 后端 DaskAdapter | dask_adapter.py:91 | 45s | 硬编码 |
| SDK 内部 | amazingdata_actor.py:42 | 30s | 硬编码 |

### 影响

- 前端可能比后端先超时，用户体验混乱
- 后端继续处理已被放弃的请求，浪费资源
- 难以排查问题：前端报超时，后端日志显示成功

---

## 发现上下文

> 在分析 get_calendar 超时问题时发现超时配置分散且不一致

---

## 相关代码

### apps/web/src/api/core/client.ts:78

```typescript
const client = axios.create({
  baseURL: '/api',
  timeout: 30000,  // 30s 硬编码
  // ...
});
```

### dask_adapter.py:91

```python
def __init__(
    self,
    timeout: float = 45.0,  # 45s 硬编码
    ...
)
```

### amazingdata_actor.py:42

```python
config.timeout = 30  # SDK 30s 硬编码
```

---

## 建议修复方案

### 方案 A: 统一超时值

确保：外层超时 > 内层超时 + 网络缓冲

```
前端 (90s) > DaskAdapter (60s) > SDK (30s) + 登录 (30s)
```

### 方案 B: 超时配置中心化（推荐）

1. 后端创建 `/api/config/timeouts` 端点
2. 前端启动时获取超时配置
3. 所有超时值从配置文件读取

```typescript
// 前端
const timeouts = await api.get('/api/config/timeouts');
axios.defaults.timeout = timeouts.client_timeout;
```

```python
# 后端 settings.yaml
timeouts:
  frontend: 90.0
  dask_adapter: 60.0
  sdk: 30.0
```

### 方案 C: 区分操作类型

不同操作使用不同超时：

```typescript
// 快速操作
api.get('/status', { timeout: 5000 });

// 慢速操作（含登录）
api.get('/calendar', { timeout: 90000 });
```

### 预估工作量

- [x] 小（< 30 分钟）- 方案 A
- [ ] 中（30分钟 - 2小时）- 方案 B/C

---

## 备注

- 超时分层原则：外层 > 内层 + 缓冲
- 建议与 Issue #1、#2 一起作为"超时优化"专项修复
