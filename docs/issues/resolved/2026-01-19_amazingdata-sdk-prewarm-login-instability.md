# [WON'T FIX] AmazingData SDK Prewarm 登录不稳定

> 发现日期: 2026-01-19
> 发现位置: Dask Worker 启动日志
> 类型: performance
> 严重程度: medium
> 状态: won't fix
> 关闭日期: 2026-02-07
> 关闭理由: 单 Worker 架构已消除多 Worker 竞争问题；SDK 服务端登录不稳定属外部因素，非代码层面可控。

---

## 问题描述

在 Dask Worker 启动时的 prewarm 阶段，AmazingData SDK 登录过程不稳定，Worker-0 的首次登录在 30 秒内超时失败，需要重试才能成功。

### 现象

```
Worker-0 日志：
[AmazingDataActor] [步骤2/5] sdk.login() 耗时超过 30s，超时失败
[AmazingDataActor] 同步预热重试中... (第 1 次)
[AmazingDataActor] 重试成功，耗时 15.65s + 7.44s
```

而 Worker-1 首次登录即成功（8.087s）。

### 影响

1. Worker-0 启动时间增加约 30 秒
2. 如果 prewarm 重试次数用完，Worker 可能无法正常工作
3. 系统启动延迟不可预测（有时快有时慢）

---

## 发现上下文

> 在验证"板块数据预热超时问题修复"时发现此问题

启动后端服务进行验证时，观察到 Worker-0 和 Worker-1 的 prewarm 行为不一致。

---

## 相关日志

```
18:42:51.660   INFO - [windows-worker-0] 执行预热步骤: sdk.login()
18:43:21.660 WARNING - [windows-worker-0] sdk.login() 超时 (30.0s)
18:43:21.661   INFO - [windows-worker-0] 同步预热重试中... (第 1 次)
18:43:37.305   INFO - [windows-worker-0] sdk.login() 重试成功 | 耗时=15.65s
18:43:44.743   INFO - [windows-worker-0] get_calendar 成功 | 耗时=7.44s

对比 Worker-1:
18:42:52.123   INFO - [windows-worker-1] 执行预热步骤: sdk.login()
18:43:00.210   INFO - [windows-worker-1] sdk.login() 成功 | 耗时=8.087s
```

---

## 可能原因

1. **SDK 服务器端并发限制** - 多个 Worker 同时登录时，服务器可能有排队机制
2. **网络不稳定** - 首次连接可能遇到网络抖动
3. **SDK 内部状态** - SDK 可能有全局锁或初始化竞争

---

## 建议修复方案

### 短期方案（配置调整）

1. 增加 prewarm 登录超时时间（当前 30s -> 45s）
2. 增加 prewarm 重试次数（当前 1 -> 2）

### 长期方案（架构优化）

1. **Worker 串行启动** - 让 Worker 依次启动，避免同时登录
2. **登录状态共享** - 研究 SDK 是否支持 session 复用
3. **监控和告警** - 添加 prewarm 耗时指标，超过阈值时告警

### 预估工作量

- [x] 小（< 30 分钟）- 配置调整
- [ ] 中（30分钟 - 2小时）- 串行启动实现
- [ ] 大（> 2小时）- session 复用研究

---

## 关联问题

- [SDK 架构导致首次调用超时](2026-01-18_amazingdata-first-call-timeout.md) - 相关但不同阶段（本问题是 prewarm 阶段，那个是运行时首次调用）

---

## 备注

当前的 prewarm 机制已经比原来的方案（在运行时首次调用时登录）好很多，这个问题的严重程度为 medium 而非 high。
