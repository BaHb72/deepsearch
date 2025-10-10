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

### 2025-10-10 排查记录

- `tests/test_amazingdata_isolation.py::TestSDKIsolation::test_safe_login_catches_system_exit` 失败原因：用例尝试通过 `patch("AmazingData.ad.login")` 注入 `SystemExit`，但 `_login()` 实际调用的是在 `deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata` 模块内导入的 `ad.login`，补丁目标路径不匹配，导致真正的 SDK 登录逻辑被执行并返回成功值，未触发预期的 `DataProviderError`。修复思路是将补丁指向真实引用的模块路径或在测试前显式覆盖 `AmazingDataProvider._sdk` 对象。【F:tests/test_amazingdata_isolation.py†L41-L55】【F:deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py†L137-L354】【F:deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata.py†L495-L632】

### 2025-10-10 全量执行结果（最新补充）

- `uv run pytest` 再次全量执行时成功收集 609 项用例，但在 18% 左右进入 `tests/test_amazingdata_all_apis.py::TestAccountManagement::test_login` 等场景便集中报错，pytest 输出显示上述用例均直接标记为 `ERROR`，导致后续 AmazingData 相关用例持续失败并阻塞整体进度。【63d8e9†L1-L36】【489742†L1-L5】【c581e7†L1-L4】【6c5d00†L1-L6】【30164b†L1-L4】【560fcf†L1-L4】【c0a31b†L1-L9】
- 通过 `uv run pytest tests/test_amazingdata_all_apis.py::TestAccountManagement::test_login -vv` 单独复现，`mock.patch` 无法找到 `deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_extended.HAS_AMAZINGDATA` 属性，抛出 `AttributeError` 并提前终止，说明批量 ERROR 的根源在于缺失该特性位标记。【ae808d†L1-L18】
- 全量执行在 `tests/test_amazingdata_isolation.py::TestDataProviderFactory::test_fallback_to_error_provider_when_all_fail` 附近停止响应，只能通过发送 `SIGQUIT` 强制退出，建议修复上述属性缺口后再重新运行全套 pytest，以免覆盖率数据库阻塞测试进程。【c6c121†L1-L4】
- `tests/test_amazingdata_all_apis.py::TestHistoricalData::test_query_kline` 失败原因：示例环境未加载真实 SDK，`ad.constant.Period.day` 缺失导致默认周期推断抛出 `AttributeError`。已在 `AmazingDataExtended.query_kline` 内优先复用实例化阶段缓存的 `_sdk`，若常量仍不可用则退回字符串日线常量并记录告警，目前用例已稳定通过。【F:deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py†L403-L440】【e12823†L1-L3】
- 受限网络环境下执行 `uv run pytest` 仍会在 Akshare、Cloudflare 等外部行情调用阶段遭遇 SSL 校验或 DNS 解析失败，同时伴随 Loguru 尝试写入已关闭标准输出的告警；需在具备外网访问与可信证书的环境中复测，以验证真实数据源链路。【9f9bf0†L1-L80】

## 初步分析

### 2025-10-09 更新

1. **环境准备**：继续遵循 README 指南使用 `uv sync --all-extras --dev` 同步依赖，并以 `uv run pytest` 执行测试链路。
2. **修复措施**：
   - **数据源配置**：`ProxyDataProvider` 现支持 `timeout`、`retry_count`、`connection`、`cache` 等可选字段，并统一输出超时设置，避免因模板字段导致初始化失败。
   - **通知配置**：新增 `ensure_env_config_file()`，测试及运行期若缺失 `settings.<env>.yaml` 会基于 `.example` 自动生成占位文件，符合 README 中“模板入库、实际配置排除”的要求。
3. **剩余工作**：AmazingData 相关集成仍需真实账号与解释器环境支持；在未开通前，建议按照现有标签策略跳过或在专用环境执行。
