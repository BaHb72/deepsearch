# 当前任务状态汇总（2025-09-29）

## 已完成工作
- 修复 ConfigAdapter、LoggerAdapter、EventEngineComponent 等适配器延迟加载问题，使单元测试重新通过。
- 调整事件引擎优先级队列、调度任务与取消流程，解决单元测试中事件优先级与任务调度相关失败。
- 更新 Akshare WorkerManager 配置，实现单节点自动策略降级与健康检查上下文兼容处理，并补充资源清理逻辑。
- 调整统一数据 API 旧接口 /api/data/source/status 的返回状态码为 404，并统一返回格式使用 success_response。

## 当前测试结果
- uv run --managed-python pytest tests/unit --maxfail=1 -vv：全部通过。
- uv run --managed-python pytest tests/api --maxfail=1 -vv：运行中，当前失败用例：tests/api/test_data_source_api.py::TestDataSourceAPI::test_get_stock_info（响应 code=500，需进一步排查）。
- 集成测试、端到端测试尚未执行。

## 待办事项
1. 调查 DataSourceManager.fetch_stock_info 在测试环境下返回错误码的原因，确保 API 成功路径返回 code=0：
   - 检查 tests/api/conftest.py 中的数据源 mock 设置。
   - 确认测试桩中对 fetch_stock_info 的实现是否覆盖。
   - 必要时在统一 API 层提供回退或更明确的错误包装。
2. 完成剩余 API 用例并运行 scripts/run_all_tests.py --quick 进行整体验证。
3. 若统一响应格式调整影响前端调用，需要安排前端联调确认。
