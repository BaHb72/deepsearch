# AmazingData 登录退避与节流机制

## 背景

AmazingData 官方 SDK 在登录失败时会直接调用 `SystemExit` 结束进程，导致我们需要通过独立进程池来隔离崩溃。为了避免同一个账号在短时间内重复触发
SDK 退避甚至“雪崩”，系统新增了一套节流机制，对登录请求进行串行化并在失败时按照 `5s → 10s → 20s` 的阶梯延迟重试。

## 后端改动

- `AmazingDataProcessPool`
    - 引入 `LoginThrottle`，同一 `datasource_id` 在登录时会先申请节流槽位，永远只允许一个 worker 正在登录。
    - 记录登录开始/结束时间、最近错误信息、失败次数等运行指标，通过 `get_status()` 暴露在 `processes[<datasource_id>]` 中。
- `ProcessIsolatedAmazingDataProvider` 与 `AmazingDataSafeWrapper`
    - 登录前调用 `wait_for_login_slot`，登录结果（含错误信息）回填到进程池，确保即便异常抛出也会释放槽位。
- `DataSourceManager.get_status_report()`
    - 将进程池的节流状态映射到数据源运行状态中，新增字段：
        - `loginThrottle`: `{ inProgress, waitSeconds, nextAllowedAt, backoffLevel, failureStreak }`
        - `pendingLogin`: 是否存在正在执行的登录
        - `lastLoginStartedAt / CompletedAt / SuccessAt / ErrorAt / ErrorReason`

## 前端改动

- **数据源监控页**
    - 新增“登录节流”列，展示当前是否在登录、剩余退避秒数、当前退避级别等信息，悬浮提示显示最早重试时间、连续失败次数以及最近一次错误原因。
    - `状态` 列 tooltip 同步展示节流信息，便于观察异常。
- **系统配置 → 数据源管理**
    - 列表中加入节流列，`测试连接` 按钮在登录退避或已有登录任务时会被禁用，并弹出提示。
    - 编辑表单顶部增加提醒，当存在退避窗口或未完成的登录任务时给出说明以及最早可重试时间。

## 使用建议

1. **观察退避**：当看到“登录中”或“等待 XXs”时无需手动干预，进程池会在窗口结束后自动重试；连续失败会逐步延长窗口。
2. **主动重试**：如果需要立即重试，可在节流窗口结束后点击“测试连接”，或在终端触发
   `pool.record_login_result(..., success=True)` 解除退避。
3. **排查失效**：若提示“最后错误”持续不变，优先检查账号、网络或 AmazingData 官方服务，再考虑重启服务。

该机制只在 AmazingData 数据源生效，其他数据源行为不受影响。*** End Patch
