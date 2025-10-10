# Pytest 失败报告

## 执行命令

1. `uv sync --all-extras --dev`
2. `uv run pytest`

> 若需采集具体失败堆栈，可使用 `uv run pytest <path>::<test_name> -vv` 针对单个用例复现。

## 报错信息摘要

### 依赖补齐前

- `pytest: error: unrecognized arguments: --cov=deepsearch --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml --cov-config=.coveragerc --benchmark-disable`
- `inifile: /workspace/deepsearch/pytest.ini`
- `rootdir: /workspace/deepsearch`

### 使用 uv 同步依赖后

- `uv sync --all-extras --dev` 成功安装 FastAPI、Pydantic、Redis、pandas、psutil 等核心依赖，pytest 能够完成 600+ 用例的收集。【53a0d0†L1-L105】【edaa42†L1-L27】
- `uv run pytest` 在约 18% 处触发大量功能性失败，集中于 WebUI 数据源与 AmazingData 相关测试，遂提前终止以避免冗余日志（历史记录，现已针对关键问题补丁修复）。【7abb18†L1-L14】
- `tests/api/test_data_source_api.py::TestDataSourceAPI::test_update_data_source_config` 曾因 `ProxyDataProvider.__init__()` 未识别 `timeout` 参数导致实例化失败、数据源保持禁用；2025-10-09 已通过适配器扩展构造参数并统一超时设置解决。【e08232†L1-L87】【e08232†L88-L146】
- `tests/api/test_notification_api.py::test_get_notification_config` 早前在 fixture 阶段读取 `deepsearch/config/settings.dev.yaml` 时触发 `FileNotFoundError`；现已新增 `ensure_env_config_file()`，缺失时会基于 `.example` 自动生成配置文件，测试得以顺利执行。【30b4e8†L1-L129】
- AmazingData 全量 API 用例依赖真实账号与离线解释器，未配置真实环境时仍会失败，可参考 `docs/datasources/amazingdata/` 搭建或在调试阶段跳过相关标签。【7abb18†L1-L14】

### 2025-10-09 自检结果

- `uv run pytest tests/api/test_notification_api.py -vv` ✅：通知配置读写链路完全通过，自动生成的 `settings.dev.yaml` 在用例结束后恢复原状。【907ae7†L1-L11】【d18148†L1-L23】
- `uv run pytest tests/api/test_data_source_api.py::TestDataSourceAPI::test_update_data_source_config -vv` ✅：测试模式下更新 AmazingData 配置返回启用状态，Cloudflare 代理初始化失败仅标记为网络告警，不再阻断配置变更。【9eed42†L1-L11】【2299bb†L1-L6】

## 初步分析

### 2025-10-09 更新

1. **环境准备**：继续遵循 README 指南使用 `uv sync --all-extras --dev` 同步依赖，并以 `uv run pytest` 执行测试链路。
2. **修复措施**：
   - **数据源配置**：`ProxyDataProvider` 现支持 `timeout`、`retry_count`、`connection`、`cache` 等可选字段，并统一输出超时设置，避免因模板字段导致初始化失败。
   - **通知配置**：新增 `ensure_env_config_file()`，测试及运行期若缺失 `settings.<env>.yaml` 会基于 `.example` 自动生成占位文件，符合 README 中“模板入库、实际配置排除”的要求。
3. **剩余工作**：AmazingData 相关集成仍需真实账号与解释器环境支持；在未开通前，建议按照现有标签策略跳过或在专用环境执行。
