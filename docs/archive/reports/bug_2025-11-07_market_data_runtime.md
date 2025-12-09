# 2025-11-07 市场行情运行异常记录

## 背景

- 在本地 DEV 环境执行 `uv run --project D:\Stock\code\deepsearch --module deepsearch run dev --log-level DEBUG`
  ，启动全量系统用于验证市场行情改造后的链路。
- 启动过程中 AmazingData 进程、WebUI 数据源测试及实时行情轮询陆续出现异常，最终导致系统无法得到可用的数据源。

## 环境信息

- 日期：2025-11-07
- 操作系统：Windows（PowerShell）
- 配置文件：`settings.dev.yaml`
- 关键组件：AmazingData 实时数据进程、AkShare 直连数据源、WebUI 数据源测试接口

## 异常列表

### 1. AmazingData SDK 登录阶段多次触发 `SystemExit`

- **现象**：主线程调用 AmazingData 登录（本地进程模式）时，子进程多次在初始握手阶段直接触发 `SystemExit(0)`，被代理层捕获后记为失败。
- **日志证据**：
    -
    `2025-11-07 02:35:33.020 | CRITICAL | ...amazingdata_process_proxy:_worker_loop:1319 - SDK called SystemExit during login: 0`
    - 随后多条 `Detected TGW push init failure, switching to api_mode=api` 表明 SDK 推送通道初始化失败，代码尝试自动降级。
    - ProviderHealthMonitor 连续记录 `[ALERT][SDK_EXIT]`，统计失败次数并触发重启：
      `[ProcessPool] Restarting unhealthy process ... after pre-login failure streak`.
- **定位分析**：
    - 触发点：`amazingdata_process_proxy._worker_loop` 在 `_perform_login` 返回时检测到 SDK 主动退出。退出前日志包含
      `Init push server failed`、`The internet mode of tgw init failed`，说明 TCP 推送通道初始化失败。
    - 代理层逻辑：首次失败后将 `api_mode` 从 `default` 调整为 `kInternetMode` 再试；SDK 仍然 `SystemExit`，因此判定为纯 API
      模式也不可用。
    - 与账号/网络相关性：日志显示登录请求使用 `212200038719@101.230.159.234:8600`，推送模式无法建立（可能是网络限制、账号权限或
      TGW 配置），但未见凭证错误（未出现认证失败码）。
- **影响**：AmazingData 始终未登录成功，`MarketDataRealtimePipeline` 只有首个轮询尝试，立即因为 `outside-trading-window`
  退出；主数据源不可用后引发后续回退逻辑（见条目 4）。
- **后续处理**：
    1. 按 `docs/datasources/amazingdata/TROUBLESHOOTING.md` 检查网络可达性、推送端口与 SDK 版本；如属外部限制需联系运维开通。
    2. 在 `amazingdata_process_proxy` 对 `SystemExit` 增加扩展日志（输出 SDK 返回的错误码 / TGW 日志），并考虑在多次失败后自动禁用推送模式，改用纯
       REST。
    3. ProviderHealthMonitor 已触发高危告警，应在运营平台或 IM 通知到位，并确认 `provider_health` 配置允许指数退避，避免频繁拉起子进程。

### 2. WebUI 数据源测试接口抛出 `UnboundLocalError`

- **现象**：启用 AkShare 后，WebUI 对 `/api/data-sources/test/akshare` 的自检返回 500。
- **关键日志**：
  ```text
  UnboundLocalError: cannot access local variable 'response_payload' where it is not associated with a value
    at deepsearch/webui/api/endpoints/datasources/datasource_manager.py:1261
  ```
- **影响**：数据源测试返回 500，被视为自检失败，AkShare 数据源立即被禁用，系统再次回退到 AmazingData（此时仍然登录失败）。
- **建议**：
    1. 在 `test_data_source` 接口中为 `response_payload` 赋予默认值或在异常分支返回结构化的失败结果。
    2. 为数据源测试增加单元测试覆盖异常路径，防止未初始化变量导致 500。

### 3. WebUI 页面持续弹出 500 错误

- **现象**：AmazingData/AkShare 皆不可用时，后端相关接口处于阻塞或直接返回 500；此时 WebUI
  仍可进入数据源/行情界面，用户操作按钮会重复触发失败请求，界面不断弹出 “500 错误” 对话框，造成体验干扰。
- **关键日志**：
  ```text
  [前端api-error] Request failed with status code 500
  [前端api-error] timeout of 8000ms exceeded
  ```
- **影响**：WebUI 市场行情页无法展示数据，数据源管理界面反复弹出报错，用户误以为操作仍在进行。
- **建议**：
    1. 修复上述后端异常后，重新验证前端请求链路；必要时在前端区分 `数据源不可用` 与 `请求异常` 的提示文案。
    2. 在前端针对数据源失败状态增加节流或禁用按钮，避免阻塞恢复前持续发送请求。

### 4. AkShare 数据源无法启用

- **现象**：AmazingData 多次失败后，系统自动尝试启用 AkShare 备援。AkShare 实时行情接口可返回结果，但随后触发的 WebUI 自检接口因第
  2 条错误返回 500，被数据源管理器认定为 `self_test_failed`，立即禁用。
- **关键日志**：
  ```text
  2025-11-07 02:35:36.888  DEBUG ... data_source_monitor:295 - 数据访问成功: akshare -> realtime_quote [000001] 1896.9ms
  2025-11-07 02:35:36.933  INFO  ... data_source_manager:2309 - 已禁用数据源 akshare
  2025-11-07 02:35:44.822  ERROR ... data_source_manager:1240 - 没有可用的数据源
  2025-11-07 02:35:44.822  WARNING ... data_source_monitor:300 - 数据访问失败: akshare -> realtime_quote [000001] self_test_failed
  ```
- **定位分析**：
    - `realtime_quote` 调用成功说明基础网络与接口通畅（日志中执行时长约 1.9s）。
    - 禁用原因并非接口不可达，而是 `test_data_source` 抛出的 `UnboundLocalError` 导致统一返回 500，数据源管理器按逻辑将其视为自检失败并调用
      `disable_provider`。
    - 后续反复尝试启用 AkShare，因自检函数未修复而陷入 “启动 -> 自检失败 -> 禁用” 的循环。
- **影响**：备援数据源无法成功接管，系统无可用数据源，WebUI 与行情服务持续异常。
- **后续处理**：
    1. 先修复条目 2 的接口 bug，确保自检返回明确的结构（即便失败也要带上错误码而非 500）。
    2. 在数据源管理器中为 `self_test_failed` 引入冷却时间或人工确认，以免因自检 BUG 直接禁用真实可用的数据源。
    3. 修复后重新执行 enable 流程，并在 `docs/testing/datasource_switch.md`（若缺失需补充）记录验证步骤。

### 5. 数据源监控 API 模块加载失败

- **现象**：WebUI 启动阶段，`data_source_monitor` API 的一部分模块因 import 失败被跳过。
- **日志证据**：
  ```text
  2025-11-07 02:34:30.242  WARNING ... d.w.server:906 - 数据源监控API模块加载失败: cannot import name 'get_data_proxy' from 'deepsearch.infrastructure.providers.unified_proxy'
  ```
- **定位分析**：
    - WebUI 在注册数据源监控 API 时试图从 `unified_proxy` 导入 `get_data_proxy`，但模块中不存在该符号或未对外导出。
    - 虽随后日志显示“数据源能力对比 API 已注册”“数据源监控 API 已注册”，但缺失的部分功能可能导致监控页面缺少数据或功能。
- **影响**：数据源监控相关的某些端点未成功初始化；在 WebUI 中可能表现为功能缺失或按钮不可用。
- **后续处理**：
    1. 检查 `deepsearch/infrastructure/providers/unified_proxy.py` 是否重构遗漏导出，或 WebUI 引用路径已变更。
    2. 补充单元测试覆盖 API 初始化流程，防止 import 错误在启动时才暴露。

### 6. 数据同步服务依赖缺失

- **现象**：数据同步服务启动后，提示数据库层未实现关键接口而跳过部分同步任务。
- **日志证据**：
  ```text
  2025-11-07 02:34:32.929  WARNING ... data_sync_service:131 - 数据库组件未实现 fetch_kline_history，跳过 K 线同步
  2025-11-07 02:34:32.930  WARNING ... data_sync_service:209 - 数据库组件未实现股票信息拉取接口，跳过同步
  2025-11-07 02:34:32.930  DEBUG   ... data_sync_service:263 - 实时数据快照同步已跳过（等待实时数据源）
  ```
- **定位分析**：
    - `data_sync_service` 调用数据库组件的扩展接口（`fetch_kline_history` 等）失败，直接跳过任务。
    - 当前环境可能尚未实现这些接口或配置未注入，即使系统恢复数据源也无法完成历史数据同步。
- **影响**：即便后续行情服务恢复，历史数据（K 线、股票基本信息）仍可能缺失，影响后续指标计算与前端展示。
- **后续处理**：
    1. 在数据库持久化层实现缺失的接口，或临时关闭相关任务避免持续警告。
    2. 启动前在健康检查中确认依赖齐备（可在 `docs/operations/preflight_checklist.md` 补充该项）。

### 7. 进程退出异常与资源清理

- **现象**：最终系统以退出码 `-1` 结束，日志显示 AmazingData worker 在等待队列时被 `KeyboardInterrupt` 中断。
- **日志证据**：
  ```text
  Process SpawnProcess-2:
  ...
  KeyboardInterrupt
  2025-11-07 02:36:11.354  DEBUG ... d.w.server:718 - 关闭 Web UI 服务...
  进程已结束，退出代码为 -1
  ```
- **定位分析**：
    - 主线程在多次失败后可能被用户手动终止（Ctrl+C）。Worker 进程收到关闭信号时因等待多进程队列触发 `KeyboardInterrupt`
      ，但仍能执行锁释放与退出路径。
    - 退出码 `-1` 表明异常退出，重启时需确认 Redis、临时锁文件（`amazingdata_worker_*.lock`）是否已释放。
- **影响**：若锁文件未删除可能影响下次启动；应确保 shutdown 流程在异常情况下也释放资源。
- **后续处理**：
    1. 在 `amazingdata_process_proxy` 的 finally 块中确保锁释放（当前日志显示已释放，但需回归测试）。
    2. 记录此次异常退出原因，启动前检查是否存在残留的 worker 进程或锁文件。

### 8. Worker 启动竞争与锁冲突

- **现象**：同一时间有多个初始化流程尝试启动 AmazingData worker，导致锁被占用，另一条流程失败并记录 “Failed to start
  process”。
- **日志证据**：
  ```text
  00:44:01.427  WARNING ... _acquire_worker_lock:421 - Worker lock busy; skip starting worker (path=...amazingdata_worker_37a8eec1ce19.lock)
  00:44:01.427  ERROR   ... logging_utils:_log:40 - AmazingData 子进程获取失败: Failed to start process for amazingdata::...
  00:44:01.428  ERROR   ... data_source_manager:initialize:1121 - 初始化数据源 amazingdata 失败: ...Failed to start process...
  ```
- **定位分析**：
    - 在同一秒内出现两组 “注册数据源” 日志，说明某处重复触发初始化（可能是启动过程中并行的组件构建与自检任务）。
    - 第二个流程因锁存在而跳过启动，随即认为初始化失败，引发 fallback 过程中多项接口调用失败 (`execute_with_fallback`
      连续报错)。
- **影响**：虽然随后第一次启动的 worker 正常运行，但前序错误会触发告警、误报失败并可能影响后续逻辑（如 fallback 连续尝试）。
- **后续处理**：
    1. 排查为何 `register`/`get_provider_instance` 在短时间内被调用两次（可能来自并行运行的服务初始化与健康检查）。
    2. 在 `get_or_create` 中补充“锁占用但已有现成进程”时的等待/重试逻辑，而不是直接抛出失败。
    3. 在 ProviderManager 中对重复初始化记录进行去重或节流，避免误触发异常路径。

### 9. AmazingData `get_kline_data` 接口参数不兼容

- **现象**：在 fallback 流程中调用 `get_kline_data` 时返回错误：“AmazingData 不支持参数 period='daily'”，随后 fallback 失败。
- **日志证据**：
  ```text
  00:44:53.636 ERROR ... execute_with_fallback:1979 - 通过 DataSourceType.AMAZINGDATA 执行 get_kline_data 失败: AmazingData 不支持参数 period='daily'
  ```
- **定位分析**：
    - 调用者传入 `period='daily'`，但当前封装未做参数映射或 AmazingData SDK 不支持该值。
    - fallback 逻辑未能切换到其他数据源（当时没有可用备援），故多次调用都以相同错误结束。
- **影响**：历史行情/北向资金等任务无法完成，错误被持续重复记录。
- **后续处理**：
    1. 检查 `get_kline_data` 的参数映射，确认 SDK 的允许值（可能需使用 `'1d'` 等）。
    2. 在 fallback 逻辑中对“不支持参数”类错误进行识别，必要时自动转换参数或切换数据源。
    3. 补充集成测试覆盖常用 period，防止回归。

### 10. Fallback 链路错误告警

- **现象**：在 worker 启动失败和接口不兼容期间，`execute_with_fallback` 连续报出“所有数据源无法执行某接口”的错误。
- **日志证据**：
  ```text
  00:44:01.428 ERROR ... execute_with_fallback:1982 - 所有数据源都无法执行 get_stock_list
  00:44:01.428 ERROR ... execute_with_fallback:1982 - 所有数据源都无法执行 get_stock_info
  ...
  ```
- **定位分析**：
    - AmazingData 未就绪时 fallback 原计划切换至 AkShare / Cloudflare 代理，但此时这些数据源尚未完成初始化（或被延迟启用），导致
      fallback 直接报错。
    - 错误未聚合，日志中短时间内出现大量同类告警，加大排障噪音。
- **影响**：一旦主数据源故障，所有依赖该接口的功能同时失败；日志量大且对业务无附加信息。
- **后续处理**：
    1. 在 fallback 逻辑中区分“主数据源未就绪”与“备援也失败”，可在主源初始化完成后再触发重试。
    2. 对重复错误进行节流/合并，或提升监控可读性。

### 11. 监控与统计组件重复初始化

- **现象**：启动日志中多次出现 “数据源监控中心初始化完成”“StatisticsCollector initialized”，表明相关单例被重复创建。
- **日志证据**：
  ```text
  00:43:58.160 INFO ... data_source_monitor:__init__:215 - 数据源监控中心初始化完成
  00:44:00.185 INFO ... data_source_monitor:__init__:215 - 数据源监控中心初始化完成
  ```
  两次记录间隔不足 2 秒，同样的情况也出现在 `StatisticsCollector`.
- **定位分析**：
    - 可能是多个线程/协程在启动早期并发请求监控实例（例如 ProviderManager 与 WebUI 同时触发）。
    - 虽然初始化函数内部可能是幂等的，但重复日志会混淆观察者，并可能带来资源浪费（例如重复注册监控任务）。
- **影响**：监控、统计组件如果携带后台线程或定时任务，重复初始化可能导致重复任务或状态覆盖。
- **后续处理**：
    1. 检查 `get_monitor()`、`StatisticsCollector` 等单例工厂的线程安全实现，确保只初始化一次。
    2. 在启动顺序上统一由核心 runtime 初始化，再供其他模块引用，避免 “谁先调用谁初始化” 的竞态。

### 12. 数据源模式自动切换告警

- **现象**：AmazingData 日志出现 “检测到缓存与远程模式同时存在，自动切换为远程模式” 的提示，表明运行中缓存参数与实际模式不一致。
- **日志证据**：
  ```text
  00:44:45.608 WARNING ... logging_utils:_log:40 - 检测到缓存和远程模式同时存在，自动切换为远程模式 | action=cache_params, context=MarketData.query_snapshot
  ```
- **定位分析**：
    - AmazingData 缓存参数中记录了本地模式信息，但当前运行环境可能被强制切换到远程模式（或反之），触发自动调整。
    - 该过程虽然未导致当前调用失败，但说明缓存配置与实际环境未同步，可能在后续流程中再次触发系统退出（结合条目 1 的推送初始化失败）。
- **影响**：模式反复切换会影响登录、推送、缓存的稳定性；同时造成日志噪音，使故障定位复杂化。
- **后续处理**：
    1. 检查 `cache_params` 的写入/读取逻辑，确保本地缓存与真实模式同步（例如启动后立即刷新缓存）。
    2. 明确在 DEV 环境下期望的登录模式（本地进程 or 远程 API），避免在运行时来回切换。

## 诊断脚本与定位支持

为便于复现和验证上述问题，新增以下测试脚本（均基于 `settings.dev.yaml` 参数）：

| 脚本                                                          | 目的                                                                               | 使用方式                                                                                       |
|-------------------------------------------------------------|----------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| `scripts/tests/diagnostics/test_amazingdata_login.py`       | 触发数据源初始化，查看 AmazingData 状态与股票列表拉取结果，复现登录失败及状态机异常。                                | `uv run python scripts/tests/diagnostics/test_amazingdata_login.py`                        |
| `scripts/tests/diagnostics/test_kline_period_compat.py`     | 分别使用 `period='daily'`/`'1d'` 调用 `get_kline_data`，定位参数不兼容导致的 fallback 失败。         | `uv run python scripts/tests/diagnostics/test_kline_period_compat.py`                      |
| `scripts/tests/diagnostics/test_datasource_selftest_api.py` | 调用 WebUI `/api/data-sources/test/{source}` 接口，再现 `response_payload` 未初始化引发的 500。 | `uv run python scripts/tests/diagnostics/test_datasource_selftest_api.py --source akshare` |
| `scripts/tests/diagnostics/test_datasync_requirements.py`   | 检查数据同步服务所需的数据库方法是否在当前实现中缺失。                                                      | `uv run python scripts/tests/diagnostics/test_datasync_requirements.py`                    |

> 运行脚本前，请确认 Redis/PostgreSQL 等依赖按 dev 配置可用，否则输出会包含额外的连接错误提示。

## 解决方案概览

1. **AmazingData 登录失败与模式切换**
    - 校验网络与账号授权；若推送模式不可用，允许运维配置强制 `api_mode=api`。
    - 在 `amazingdata_process_proxy` 中捕获 SDK `SystemExit` 后自动降级、延长退避时间，并刷新缓存模式。
2. **数据源自检接口 500**
    - 为 `response_payload` 设置默认值；失败时返回结构化 JSON 而非直接 500。
    - 增加单元测试覆盖异常路径，确保数据源失败提示准确。
3. **K 线参数兼容**
    - 在 DataSourceManager 内部映射 `period` 参数（如 `daily -> 1d`）；若仍失败，自动尝试备援数据源。
    - 扩充接口契约文档，统一 period 字段格式。
4. **AkShare 备援被误禁用**
    - 修复自检接口后，调整 DataSourceManager 禁用策略：失败需多次确认或人工干预。
    - 自检逻辑引入冷却时间，避免短时间内触发启用/禁用循环。
5. **数据同步依赖缺失**
    - 在数据库组件或服务层实现 `fetch_*` 系列接口，或在同步任务中显式禁用相关步骤。
    - 将接口依赖整理进开发文档，并在 CI 中增加方法存在性检查。
6. **监控/统计重复初始化、Fallback 噪音**
    - 对单例工厂加锁，避免并发初始化；重复的 fallback 报错做节流聚合，提高日志可读性。
7. **Worker 锁冲突**
    - 为 `get_or_create` 增加等待机制或复用已有进程；同时排查触发重复初始化的调用链。

落实以上方案后，需按诊断脚本逐项回归，并更新本报告及对应 Runbook。

## 综合影响

- AmazingData 与 AkShare 双双不可用，实时行情主流程被阻断。
- ProviderHealthMonitor 连续告警，系统状态面板会显示严重异常，需要运维进一步介入。

## 后续行动建议

1. 修复 `response_payload` 未初始化问题，确保数据源测试接口健壮。
2. 复现并定位 AmazingData SDK `SystemExit` 根因，若为网络/账号限制需协调运维处理；若为代码问题需在
   `amazingdata_process_proxy` 内增加重试策略与模式切换。
3. 所有修复完成后，按照 `docs/testing/` 指南重新执行启动流程，并在文档记录恢复步骤。
