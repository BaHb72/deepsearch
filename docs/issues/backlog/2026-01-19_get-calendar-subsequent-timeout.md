# get_calendar 后续调用持续超时

> **状态**: 观察中
> **日期**: 2026-01-19
> **分类**: performance / stability

## 问题现象

1. 服务启动时 `get_calendar` 首次调用成功（耗时 2.81s）
2. 约 1-2 分钟后，后续的 `get_calendar` 调用开始持续超时
3. 即使设置了 90s 超时，仍然超时失败
4. 重试机制正常工作（重试 3 次），但每次都超时

## 日志摘录

```
00:34:51 INFO  get_calendar 成功 | 耗时=2.81s
...
00:36:29 ERROR 调用超时 | method=get_calendar | timeout=90.0s (首次调用)
00:36:29 INFO  重试 1/3
00:38:06 ERROR 调用超时 | method=get_calendar | timeout=90.0s
00:38:06 INFO  重试 2/3
00:39:43 ERROR 调用超时 | method=get_calendar | timeout=90.0s
00:39:43 INFO  重试 3/3
```

## 可能原因

1. **Actor 挂起/死锁** - 初次调用后 Actor 状态异常
2. **Worker 任务堆积** - Dask Worker 任务队列阻塞
3. **SDK 连接断开** - AmazingData SDK 的 TCP 连接可能超时断开
4. **线程池耗尽** - SDK 使用的线程池可能被占满

## 排查方向

1. 检查 Worker 日志中 Actor 的状态变化
2. 确认 SDK 是否有心跳/重连机制
3. 检查是否有其他任务阻塞了 Actor
4. 验证 Redis 结果传递通道是否正常

## 与超时配置的关系

超时配置修复已验证有效（90s 已正确应用）。此问题是独立的 Actor 稳定性问题，不是超时配置问题。

## 备注

用户选择"继续观察"，可能是临时网络波动导致。如果持续复现，需要深入排查 Actor 生命周期管理。
