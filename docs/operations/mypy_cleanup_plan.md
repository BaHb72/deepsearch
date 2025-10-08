# DeepSearch mypy 清理计划（2025-10-06 更新）

## 当前状态
- 2025-10-06 02:58：执行 `uv run mypy deepsearch`，共检查 393 个源文件，有 191 个文件触发 1633 个错误，详细日志保存在 `mypy.log`。
- 目前未对 mypy 配置做额外放宽，`pyproject.toml` 中的忽略项保持不变，后续改动需同步评估对 CI 的影响。

## 近期修复回顾
- 2025-10-06 09:45：补齐 `strategies.managers.risk_manager`、`workers.proxy_manager` 与 `infrastructure.persistence.timeseries` 的关键类型注解，重构部分工厂方法返回值，关联单测通过：
  - 运行 `uv run pytest tests/unit/strategies/test_risk_manager.py tests/unit/workers/test_proxy_manager.py -q --no-cov --maxfail=1` 共 6 次稳定通过。
  - `deepsearch/core/runtime/async_runner.py` 与 `engine_context.py` 的同步触发逻辑改为显式 `ComponentState` 枚举，消除了 `Any` 派生的链式错误。
  - `deepsearch/infrastructure/providers/datafeed/qmt/{datafeed,provider}.py` 对 pandas 默认值与回调签名补充了类型，避免 `Callable[..., Any]` 继续外溢。
  - `deepsearch/infrastructure/providers/managers/optimized_manager.py` 针对 `_access_history`、预取策略和命中统计补齐了结构化类型描述，解决多处 `[var-annotated]` / `[index]` 误报。
- 2025-10-06 11:12：`deepsearch/infrastructure/providers/redis/_compat.py` 加入 Timeseries 模块兜底加载与告警，新增 `tests/unit/infrastructure/test_timeseries_redis_compat.py` 保障。
- 2025-10-06 12:20：完善 `RedisTimeSeriesStorage` 的发布 / 查询 / 清理流程，新增集成测试 `tests/integration/infrastructure/test_timeseries_storage_integration.py`（若缺少 `REDIS_TIMESERIES_LIB` 将自动 skip）。

## 错误热点（tools/mypy_error_report.py 提取 Top 15）
1. `deepsearch/backtest/data/data_validator.py` · 41
2. `deepsearch/core/components/qmt_gateway_component.py` · 39
3. `deepsearch/core/runtime/engine.py` · 32
4. `deepsearch/infrastructure/persistence/timeseries.py` · 29
5. `deepsearch/strategies/managers/risk_manager.py` · 27
6. `deepsearch/workers/proxy_manager.py` · 27
7. `deepsearch/messaging/bus.py` · 26
8. `deepsearch/webui/api/endpoints/trading/chart.py` · 26
9. `deepsearch/memory/smart_memory.py` · 24
10. `deepsearch/indicators/simple.py` · 23
11. `deepsearch/webui/api/endpoints/amazingdata/financial.py` · 23
12. `deepsearch/webui/api/endpoints/amazingdata/shareholder.py` · 22
13. `deepsearch/webui/server_manager.py` · 20
14. `deepsearch/strategies/managers/engine.py` · 17
15. `deepsearch/infrastructure/providers/managers/manager.py` · 17

> 总计记录 1079 条诊断，完整输出可通过 `python tools/mypy_error_report.py mypy.log > reports/mypy_hotspots.txt` 再加工。

## 风险与依赖
- RedisTimeSeries 模块在本地/CI 的可用性仍是 Timeseries 存储测试的前置条件，需同步运维同事确认 Windows 环境的模块加载路径。
- `optimized_manager` 涉及数据源优先级与降级策略，修改需要配合长时间回放测试，避免影响实时交易路径。
- 多数 `webui` 相关告警集中在 FastAPI 响应模型与依赖注入，可能需要新增 Pydantic 模型或补齐 `TypedDict`。

## 下一阶段计划
1. **P0：providers 优化管理器收敛**
   - 梳理 `deepsearch/infrastructure/providers/managers/optimized_manager.py` 中 `_access_history`、`_prefetch_tasks` 与 `_providers` 的数据结构，补齐 `TypedDict` 或 `Protocol`。
   - 与运行时团队确认缓存层复用场景，避免类型改动引入性能回退。
2. **P1：Timeseries 生态闭环**
   - 将 RedisTimeSeries 模块加载文档化（已完成）后，编写 smoke 测试脚本验证 Windows + CI 的默认配置。
   - 评估是否需要在 `pyproject.toml` 中为 Redis 兼容层添加特定忽略，或通过局部注解消除现有告警。
3. **P1：核心引擎与 QMT 组件**
   - 对 `core/runtime/engine.py`、`core/components/qmt_gateway_component.py` 分段处理，优先标注上下文对象、消息分发器等高频 API。
   - 引入 `typing.Protocol` 或 `abc.ABC` 约束异步回调签名，减少 `[call-arg]`、`[assignment]` 级别错误。
4. **P2：WebUI 与指标模块**
   - 为 `webui/api/endpoints/*` 补齐响应模型类型定义，与前端 `docs/api/FRONTEND_API_REGISTRY.md` 对齐。
   - 为 `indicators.simple`、`strategies.managers.engine` 探索拆分数据结构或添加 `NamedTuple` 支撑，降低后续重构成本。
5. **P3：工具化支撑**
   - 扩展 `tools/mypy_error_report.py`，支持分组输出（模块、错误类型），并将结果纳入 CI 产物，便于每日追踪。

## 协同需求
- 如需批量调整 Redis 相关类型，请在合入前同步基础设施组进行冒烟验证。
- 新增 `TypedDict` / `Protocol` 时，提前通知应用层维护者更新调用方式，避免产生运行时断裂。
