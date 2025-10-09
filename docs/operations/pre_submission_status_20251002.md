# 数据源状态优化与测试计划（2025-10-05）

## 背景
- `test_data_source_config_toggle` 仍期望禁用后状态记录为 `offline/disabled_by_config`，而重新启用时即刻恢复可用；目前实现与测试预期冲突，需统一“软禁用”语义与状态映射。
- API 集成测试 `test_data_validation` 与 `test_notification_config` 在 CI 环境下持续出现 429，说明限流中间件与测试流量之间缺少配套策略。

## 建议计划
1. **测试逻辑对齐与软禁用方案**
   - 深入分析 `test_data_source_config_toggle` 的期望路径，将“禁用但可回退”状态设计为 WebUI 层可识别的 `DEGRADED/disabled_by_config`，并在前端提供明确文案。
   - 在数据源管理器中为测试场景保留单独的状态分支，例如当启用请求来自自动化测试时，仅恢复运行时连接而保持配置持久层禁用，等待完整初始化后再切换状态。
   - 完成后更新 `tests/api/test_data_source_api.py` 相关断言，确保测试与实现对齐。

2. **状态回退与自检**
   - 禁用后调用链应立即释放连接、标记 `DEGRADED`，且保留配置，方便随时恢复。
   - 重新启用时执行自检（即刻或异步），成功后更新状态为 `ACTIVE`，并同步最后一次自检时间供断言使用。

3. **限流中间件调试**
   - 在 `TestClient` 构造或 API helper 中统一注入 `X-Test-Mode: true`，确保每个测试请求被识别为测试流量。
   - 如仍命中限流，扩展 `RateLimitMiddleware` 的白名单或在测试模式下直接跳过统计，特别是 `/api/data/*` 与 `/api/notification/*`。

4. **回归验证**
   - 调整完成后依次运行：
     - `uv run --python ./.venv/Scripts/python.exe pytest tests/api/test_data_source_api.py::TestDataSourceAPI::test_data_source_config_toggle --no-cov`
     - `uv run --python ./.venv/Scripts/python.exe pytest tests/api/test_data_source_api.py::TestDataSourceAPI::test_data_validation --no-cov`
     - `uv run --python ./.venv/Scripts/python.exe pytest tests/api/test_notification_api.py::test_get_notification_config --no-cov`
     - `uv run --python ./.venv/Scripts/python.exe python scripts/run_all_tests.py --quick`

5. **风险与后续**
   - 启用/禁用分支的额外逻辑需兼顾真实运行场景，避免引起状态机回归。
   - 若修改配置落盘流程，需同步样例与文档，并审查安全提示。
   - `_sdk_loader.py`、限流调整仍属新增文件，需纳入版本控制后统一回归。
