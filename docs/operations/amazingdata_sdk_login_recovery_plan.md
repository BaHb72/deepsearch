# AmazingData SDK 登录异常应对计划

## 1. 事件背景

- 2025-10-23 20:55-20:59 在执行 `uv run deepsearch run dev --log-level DEBUG` 时，主进程加载 `AmazingData` 优化版 SDK 发生
  `SystemExit`，日志指向 `CheckLogonLegal username is empty or over kUsernameLen` 与
  `The internet mode of tgw init failed`。
- 同时，进程池模式(`amazingdata_process_pool`) 能成功保存账号 `212200038719` 并完成一次登录，但随后仍被健康检查判定为
  `unknown -> error`，触发多轮重启。
- 前端 `WebUI` 请求多次返回 HTTP 503，Redis/DuckDB 等本地资源在停止流程中出现 `ConnectionResetError` 与跨事件循环的
  `RuntimeError`。

## 2. 影响及风险

- **实时行情与指标不可用**：`AmazingData` 路由无法抽象出实时数据，`/api/market/live/*` 等接口立即降级为 503。
- **系统稳定性下降**：优化版 SDK 在主进程内持续抛出 `SystemExit`，阻断了实时线程装载，导致 `MainEngine` 处于半初始化状态。
- **资源回收异常**：停止流程出现跨事件循环 Future，`asyncpg` 连接未在同一 loop 内关闭，后续重启可能卡死或退出码恒为 -1。
- **潜在账号封禁风险**：TGW 日志反复报错 `Heartbeat send fail`，长期重试可能触发数据源侧的安全限制。

## 3. 诊断初结

1. **凭证读取路径差异**：优化版 SDK 可能依赖本地 INI/注册表条目或环境变量，不经过 `process_pool` 的代理封装，导致账号为空。
2. **网络/驱动模式未就绪**：`The internet mode of tgw init failed` 指向 TGW 客户端网络配置异常，需确认 Windows 防火墙、代理及
   SDK 配置工具的运行状态。
3. **健康检查逻辑敏感**：进程池虽然登录成功，但心跳阶段即被判定为 `invalid state`，可能是网关心跳接口或状态机未对中断做熔断处理。
4. **异步停止流程存在竞态**：`AsyncComponent.stop_async()` 获得他 loop 的 Future，说明资源注销时缺乏统一的 loop 绑定。

## 4. 行动目标

- 在 24 小时内恢复 `AmazingData` 实时数据能力，确保前端与内部调用获取到 200 响应。
- 制定明确 fallback 策略：当优化版 SDK 初始化失败时，自动切换至进程池模式且不再尝试优化版。
- 修复停止流程的跨 loop Future 问题，保证异常退出不会影响下一次启动。
- 形成文档化的巡检与验证清单，纳入 `operations` 运行手册。

## 5. 行动计划

### 5.1 短期止血（立即执行，负责人：运行团队值班）

1. **强制禁用优化版 SDK**
    - 在 `settings.dev.yaml` 与生产配置中新增显式开关（如 `amazingdata.optimized_mode.enabled=false`），或在
      `AmazingDataProviderFactory` 中检测首次 `SystemExit` 后标记熔断。
    - 重启服务，确认进程池模式稳定运行不少于 30 分钟。
2. **校验凭证**
    - 核对 `settings.*.yaml` 中的账号字段，与 `amazingdata_process_proxy` 记录的用户名保持一致。
    - 如需本地 ini/注册表，使用官方配置工具重新写入。
3. **网络连通性验证**
    - 通过 `uv run -- python tools/check_ports.py amazingdata`（若存在）或 `Test-NetConnection 101.230.159.234 -Port 8600`
      等方式确认出口连通。
    - 检查防火墙、VPN、代理规则。

### 5.2 根因排查（T+1，负责人：数据平台开发）

1. **优化版 SDK 初始化流程复盘**
    - 在 `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_optimized.py`
      增加详细日志（避免输出敏感信息），打印读取到的账号、配置路径、DLL 加载结果。
    - 比对与进程池版本的配置来源差异。
2. **TGW 客户端诊断**
    - 使用官方 TGW 自检工具检查网络模式是否被设置为“互联网模式”。
    - 收集 `%APPDATA%/TGW/logs` 下近 24 小时日志留档。
3. **健康检查策略调整**
    - 评估 `amazingdata_process_pool` 在心跳失败时的重试/熔断阈值，避免首次抖动即被标记为 `unknown -> error`。
    - 必要时让健康检查核对登录态，而不是单次心跳。
4. **异步停止流程修复**
    - 复核 `deepsearch/core/async_component.py:196`、`deepsearch/core/runtime/engine.py:1258` 的 loop 使用场景，统一使用
      `asyncio.get_running_loop()` 并通过 `call_soon_threadsafe` 关闭资源。
    - 增加单元测试覆盖停止阶段。

### 5.3 长期治理（T+7，负责人：平台负责人）

1. **SDK 模式自动降级**
    - 在 `ports.AmazingDataProcessPort` 层加入策略：优化版失败后切换进程池并记录指标；仅在维护窗口内再尝试恢复优化版。
2. **凭证与配置基线化**
    - 建立 `ops/secrets/` 加密配置仓库，统一发版时校验账户信息。
    - 将 TGW 网络模式、DLL 版本纳入巡检脚本。
3. **监控与报警**
    - 在 `observability` 模块增加 `amazingdata_login_success`、`amazingdata_heartbeat_latency` 指标，Prometheus 报警阈值与
      Grafana 面板联动。
    - 对 API 503 比例设置告警，及时通知值班。
4. **演练与文档**
    - 每季度演练一次 `AmazingData` 失效切换流程，将本计划整理后的版本加入 `docs/operations/runbooks/`。
    - 更新新员工培训资料，强调 SDK 模式差异与常见故障点。

### 5.4 业态强化专项应对（2025Q4 规划）

1. **单会话租约与缓存回退**
    - Provider 管理器落地租约登记，使用 Redis/DB 记录 `session_lease:{username}` 与租约 ID + TTL，登录流程须先 CAS
      申请租约再建立真实连接。
    - 租约持有者负责刷新 TTL 并维护实时流；非持有者一律返回缓存快照（刷新频率 5-10s），响应中标记 `mode="degraded"`
      ，确保“非持有者只读缓存”。
    - 安排租约巡检任务处理租约过期或进程异常退出，必要时强制释放并触发重建。
2. **降级不黑屏**
    - 后端 API 统一返回 `{ "mode": "normal"|"degraded", "staleness_s": float, "data": {...} }`，即使降级也保持 200。
    - WebUI 增加状态提示、颜色标识和告警入口，结合 `staleness_s` 呈现数据新鲜度，彻底替代 503 黑屏。
    - 当 `staleness_s > 30` 或降级持续超过 5 分钟时触发观测告警。
3. **自适应节流与指数退避**
    - 拆分竞价时段（9:15-9:25，1-2s emit）与常规时段（5-10s emit），RateLimiter 根据时间段和订阅量动态调整。
    - 登录失败进入指数退避：1s → 2s → 4s → 8s → 16s，最大 5 分钟；成功后恢复基础频率。
    - 心跳失败累计达阈值后自动降级为缓存模式，同时写回租约状态。
4. **Windows 关停规范**
    - 创建与关闭操作必须使用同一事件循环，跨线程收尾通过 `asyncio.run_coroutine_threadsafe` 调度。
    - 按“provider → gateway → cache → message_bus → database → webui”顺序停机，补充单元/集成测试覆盖 cross-loop
      RuntimeError 场景。
5. **指标与熔断**
    - 新增指标：`login_fail_total{reason}`、`heartbeat_rtt_p99`、`api_degraded_ratio`、`session_lease_conflict_total`、
      `emit_interval_p95`。
    - 熔断策略：`login_fail_total{credential_empty} ≥ 1` 立即禁用优化版；`api_degraded_ratio > 0.2` 持续 5 分钟触发降级提示并报警；
      `heartbeat_rtt_p99 > 0.8s` 连续 3 轮则加长节流周期。
    - 在 Prometheus + Alertmanager + Grafana 建立仪表盘与告警模板。
6. **SLO 与验收**
    - 关键 API 24h 内 200 响应率 ≥ 98%；`emit_interval_p95 ≤ 2s`（竞价窗口 ≤ 1.5s）；租约续约成功率 ≥ 99%。
    - 指标 5 分钟内同步且异常态均有告警通知。
    - 自测用例覆盖：优化版失败自动降级、租约冲突回退缓存、登录退避节奏、Windows 关停流程无 cross-loop 异常、指标上报校验。

## 6. 风险与依赖

- **账号权限变更**：若 `AmazingData` 在后台更新账号策略，需要协调数据源方重新发放凭证。
- **操作系统限制**：优化版可能依赖 PowerShell 策略或特定 C++ 运行时，需与桌面运维团队确认。
- **开发资源冲突**：异步框架调整与其他模块的迭代可能冲突，需在分支上独立验证后合并。

## 7. 观测指标与验收

- `WebUI` 关键接口 (`/api/market/live/strength`, `/api/market/live/limit-strength` 等) 连续 1 小时返回 200。
- `AmazingData` 登录/心跳日志连续 24 小时无 `SystemExit`、`invalid state` 记录。
- 异步停止流程经自测不再出现跨 loop `RuntimeError`，并在 `scripts/run_all_tests.py` 中补充断言。
- 计划内容同步进团队周会与知识库，确认所有相关人完成阅读。

## 8. 后续跟踪

- 责任人每天下午 15:00 前在 `diagnostic_log.json` 补充当日巡检情况。
- 若恢复过程中遇到新异常，需更新本计划并通知运行团队重新评审。

