# 数据源访问失败与系统健康降级

> 发现日期: 2026-01-18
> 发现位置: 系统运行日志
> 类型: performance
> 严重程度: high
> 状态: open

---

## 问题描述

系统运行过程中出现多个数据源访问失败和超时问题，导致系统健康状态降级为 `degraded`。

### 现象

1. **AkShare Fallback 失败**
   - `stock_list` 接口返回 None
   - `strength` 和 `board_overview` 的 akshare fallback 超时（5秒）

2. **DaskAdapter 调用超时**
   - `get_code_list` 方法 30 秒超时
   - 触发重试机制（1/3）

3. **Redis 响应时间过高**
   - 系统健康检查报告 Redis 响应时间过高
   - 整体系统状态降级为 `degraded`

### 影响

- 行情数据获取延迟或失败
- 系统整体可用性降低
- 用户体验受影响（进度条卡在低百分比）

---

## 发现上下文

> 在切换 AmazingData 到 distributed 模式后运行系统时发现

系统刚完成数据源运行模式配置修改（从 local 切换到 distributed 模式），在启动后的首次数据加载过程中出现上述问题。

---

## 相关日志

```
2026-01-18 17:28:25.815  WARNING [data_source_monitor:271]
数据访问失败: akshare -> stock_list [None] None

2026-01-18 17:28:25.815  WARNING [live_api:315]
strength fallback 超时（5秒），跳过 akshare fallback

2026-01-18 17:28:28.035  ERROR [dask_adapter:337]
[DaskAdapter] 调用超时 | method=get_code_list | timeout=30.0s

2026-01-18 17:28:28.036  INFO [dask_adapter:344]
[DaskAdapter] 重试 1/3

2026-01-18 17:28:40.300  WARNING [health.manager:297]
系统健康状态异常: degraded | 问题组件: redis=degraded(Redis response time is high)
```

---

## 根因分析

### 可能原因 1：Dask Worker 冷启动延迟

刚切换到 distributed 模式，Dask Worker 首次启动需要：

- 加载 AmazingData SDK
- 建立 SDK 连接
- 初始化 Actor 实例

这个过程可能超过 30 秒的超时时间。

### 可能原因 2：资源竞争

多个组件同时启动：

- Dask Scheduler + Worker
- AmazingData Actor
- Redis 健康检查
- 前端数据请求

导致系统资源紧张，响应时间延长。

### 可能原因 3：AkShare 服务端问题

AkShare 作为 fallback 数据源也失败，可能是：

- 网络问题
- AkShare API 限流
- Worker 代理服务不稳定

---

## 建议修复方案

### 短期（快速止血）

1. **增加 DaskAdapter 超时时间**
   - 当前：30 秒
   - 建议：首次调用 60 秒，后续 30 秒

2. **增加 AkShare fallback 超时**
   - 当前：5 秒
   - 建议：10 秒

3. **优化启动顺序**
   - 先等待 Dask Worker ready
   - 再开始接受数据请求

### 长期（彻底根治）

1. **实现 Worker 预热机制**
   - 启动时主动调用一次 SDK
   - 确保 SDK 连接建立后再标记为 ready

2. **健康检查细化**
   - 区分"启动中"和"故障"状态
   - 启动中不应触发降级告警

3. **Redis 连接池优化**
   - 检查 Redis 配置
   - 考虑使用连接池

---

## 预估工作量

- [x] 小（< 30 分钟）：增加超时配置
- [ ] 中（30分钟 - 2小时）：优化启动顺序
- [ ] 大（> 2小时）：实现预热机制

---

## 备注

- 该问题在 distributed 模式下更容易出现
- local 模式下可能不会有此问题（直接 SDK 调用，无 Dask 开销）
- 如果问题持续，建议暂时切换回 local 模式
