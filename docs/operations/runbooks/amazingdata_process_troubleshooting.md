# AmazingData 进程异常排查手册

## 背景

AmazingData SDK 在进程隔离模式下偶尔会在执行 `InfoData` / `MarketData` 请求后异常退出，导致进程池频繁重启。为快速定位问题，我们在
`amazingdata_process_proxy` 中增加了结构化日志与子进程文件日志。本手册记录如何获取这些信息以及排查步骤。

## 日志入口

- **主进程日志** `data/logs/deepsearch_*.log`  
  关键日志示例：
    - `InfoData call success/fallback/failed …`：记录方法名、耗时及结果规模。
    - `MarketData call …`：与上面一致，便于确认行情接口是否触发异常。
    - `Worker process crashed during request … (details={'pid': …, 'exitcode': …})`：包含请求类型与退出码；`exitcode=0` 视为
      SDK 主动退出，`exitcode=1`/负数需重点关注。
    - `ProcessPool Restarting unhealthy process … details=(exitcode=…, pid=…)`：进程池重启事件，配合上面的请求信息判断崩溃点。

- **子进程文件日志** `data/logs/datasource/amazingdata_worker_YYYYMMDD.log`  
  自动滚动保存所有 worker stdout/stderr 与结构化信息，便于核对 SDK 行为，例如：
    - `InfoData call fallback … error=InfoData.get_stock_basic() got an unexpected keyword argument 'is_local'`
    - `Login successful …`，`Attempting safe logout …`

## 排查流程

1. **锁定时间窗口**  
   通过监控告警或业务报错，确定问题发生的时间段。优先查看主进程日志中的 `Worker process crashed` 记录。

2. **确认请求类型与退出码**
    - `exitcode=0`：SDK 执行完成后主动退出，多数与登录状态或安全退出策略相关，重点检查文件日志是否在 logout 前出现异常提示。
    - `exitcode=-15`（`signal=15`）：通常意味着外部信号终止，确认是否有并发重启或系统清理脚本。
    - `exitcode=1`：SDK 内部未捕获异常。需要结合文件日志中的最后一条 `InfoData` / `MarketData` 调用记录。

3. **分析 fallback 信息**  
   若日志出现 `call fallback`，说明首次带 `is_local` 参数的调用被 SDK 拒绝。确认适配器是否已去除该参数，必要时在配置中关闭
   `is_local`。

4. **定位具体接口**
    - `InfoData` 失败：查看是否是 `get_stock_basic` 等内部需要缓存的调用。结合 `duration` 判断是否网络超时。
    - `MarketData` 失败：关注参数 `arg0_len`（股票数量）以及 `end_date` 是否超出服务端支持范围。

5. **复现与验证**  
   使用 `.trash/repro_get_stock_list.py` 或自定义脚本重放流程，观察日志是否复现同样的退出码，并截图/归档相关日志以便后续分析。

## 建议的后续动作

- 若 `exitcode=0` 场景频繁出现，可在 `_handle_worker_crash` 中降级处理，避免进程池频繁重启；同时评估 SDK 是否需要升级或替换退出策略。
- 对 `exitcode=1` 或负数信号事件，记录 `method`、参数及时间戳，反馈给数据源供应商或进一步增加防御性重试。
- 定期整理 `data/logs/datasource/` 下的日志，避免日志占用过多磁盘空间，可在运维脚本中增加压缩/清理逻辑。

## 参考

- 代码实现：`deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process_proxy.py`
- 复现脚本：`.trash/repro_get_stock_list.py`
- 相关 runbook：`docs/operations/runbooks/realtime_board_subscription.md`
