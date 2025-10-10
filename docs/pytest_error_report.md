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
- `uv run pytest` 在约 18% 处触发大量功能性失败，集中于 WebUI 数据源与 AmazingData 相关测试，遂提前终止以避免冗余日志。【7abb18†L1-L14】
- `tests/api/test_data_source_api.py::TestDataSourceAPI::test_update_data_source_config` 断言 `enabled is True` 失败，日志显示 `ProxyDataProvider.__init__()` 收到未声明的 `timeout` 参数，导致 Cloudflare 代理实例化失败并使数据源保持禁用。【e08232†L1-L87】【e08232†L88-L146】
- `tests/api/test_notification_api.py::test_get_notification_config` 在 fixture 阶段读取 `deepsearch/config/settings.dev.yaml` 时触发 `FileNotFoundError`，当前仓库仅存在 `settings.prod.yaml`，需补齐或在测试中改用临时配置。【30b4e8†L1-L129】
- AmazingData 全量 API 用例依赖真实账号与离线解释器，未配置真实环境时会持续失败，可参考 `docs/datasources/amazingdata/` 搭建或在调试阶段临时跳过相关标签。【7abb18†L1-L14】

## 初步分析

### 2025-10-09 更新

1. **环境准备**：按照 README 指南使用 `uv sync --all-extras --dev` 一次性同步运行与开发依赖，测试命令统一切换为 `uv run pytest`，无需再手动安装单个插件。
2. **执行结果**：依赖补齐后，pytest 收集阶段已恢复正常，但以下模块仍需关注：
   - **数据源配置**：Cloudflare 代理实现缺少 `timeout` 参数支持，需在 `ProxyDataProvider` 适配层补充入参或在配置侧规避该字段。
   - **通知配置**：测试期望存在 `settings.dev.yaml`，应提供模板文件或调整 fixture 以使用现有模板。
   - **AmazingData 集成**：大量用例依赖真实服务，建议在未就绪的环境下添加条件跳过或补充 Mock，以提升本地自动化稳定性。
3. **后续建议**：
   - 在数据源适配器中实现 `timeout` 选项解析，保证云端代理能够被启用。
   - 将 `settings.dev.yaml` 模板纳入仓库，或在测试前动态生成临时配置文件。
   - 为依赖外部服务的测试增加环境检测与跳过逻辑，避免 CI/CD 中出现大量不可控失败。
