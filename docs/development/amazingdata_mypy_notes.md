# AmazingData mypy 修复记录

## 现状概览

- 进程池 `amazingdata_process_pool.py` 中存在 `handle` / `snapshot_handle` 混用，导致 mypy 报错和潜在逻辑混乱。
- 扩展 provider `amazingdata_extended.py` 若干接口签名与返回值不一致（声明 `DataFrame` 却返回 `None`）。
- 市场数据适配器、Web API 层还有 `Mapping`/`dict` 的类型不匹配问题。

### 2025-11-04

- `amazingdata_process_pool.py`：统一 `handle` 引用，重新梳理重启与登录节流逻辑。
- `amazingdata_extended.py`：新增 `_safe_dataframe` 帮助函数，所有 DataFrame 接口异常时返回空 DF。
- `datasources/datasource_manager.py`：拆分测试接口响应 payload，避免 `DataSourceTestRequest` 混用。
- `process/runtime.py`：安全封装模块引用补充 `ModuleType` 注解。

## 已完成修改

1. 在 `runtime.py`、`helpers.py`、`market_stream_adapter.py` 等模块补充严格类型定义，移除无效 `type: ignore`。
2. 更新 `ProviderCallStats` 与 `ProviderStatsReport` 添加 `last_health_status` 字段，配合安全封装统计。
3. 整理 `query_manager.py` 内部结构，消除 `MutableMapping` 更新、`TypedDict` 字段缺失等问题。

## 待处理事项

1. **进程池状态管理**
    - 统一 `handle` 引用，明确快照/当前引用的变量名。
    - `restart` / `wait_for_login_slot` / `record_login_result` / `get_status` 需要重新审视锁的使用顺序，避免返回 `None`
      后继续访问。
2. **扩展 provider 的接口签名**
    - `get_code_info` 应始终返回 `pd.DataFrame`（空数据用空 DF 表示），其余类似接口比照调整。
3. **Web API 结构体**
    - `test_amazingdata` 相关 payload 应与 `DataSourceTestRequest` 保持一致，不再在同一变量上复用不同类型。
4. 所有改动完成后再次运行 `uv run --python ./.venv/Scripts/python.exe mypy deepsearch`，确认收敛。

## 记录要求

- 每完成一个子任务在此文档追加“处理方案 + 结论”。
- 如需大幅重构，优先在此标记高层步骤。***
