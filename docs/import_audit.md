# 导入依赖审计纪要

## 工具与检测方案
- 使用 `pyright --outputjson` 扫描仓库，追踪所有未解析的导入、类型桩缺失以及与可选依赖相关的接口不匹配问题。
- 通过 `pyrightconfig.json` 将 `typings/` 以及 `third_party/amazingdata/src` 纳入类型检查路径，保证兼容层与第三方 SDK 桥接代码被正确识别。
- 借助 Python 脚本汇总诊断数据，按文件统计问题数量以定位高风险目录。

## 已完成工作
1. 安装 `requirements*.txt` 声明的依赖，并补充 `pandas、aiohttp、akshare、asyncpg、redis、duckdb、pyyaml、matplotlib、backtrader、loguru、psutil、rich、pydantic` 等缺失包，确保类型检查环境完整。
2. 更新 `pyrightconfig.json`，新增 `typings/` 与 `third_party/amazingdata/src`，同时生成初始 `pyright-output.json` 作为基线。
3. 新增兼容层 `deepsearch/interfaces/data/`，为旧版调用方提供 `AdjustType/PeriodType/SecurityType/DataCache/AmazingDataProvider` 等别名，减少示例与测试中的硬编码导入。
4. 通过 `importlib` 改造 `deepsearch` 内部多个模块（如 QMT 适配器、AmazingData 工具、RedisTimeSeries 存储等），在可选依赖缺失时优雅降级，避免 `ImportError`。
5. 基于最新扫描结果，继续修复 `tools/validate_all_datasources.py` 与 `unified_qmt_provider` 的静态导入问题，完成本轮代码同步。
6. 通过新增 `pyrightconfig.json` 显式引入 `typings/` 与 `third_party/amazingdata/src`，并扩充 AmazingData 类型桩，
   让 `tests/integration/amazingdata/*` 能识别占位 SDK，导入缺失问题下降至仅余实际逻辑空值告警。
7. 重构 `tools/validate_all_datasources.py`，为配置访问与可选依赖导入补充显式判空与 Any 降级工具函数，
   解决 `ValidationResult` 联合类型残留及 `aiohttp`、`asyncpg` 等缺失桩导致的报错。
8. 执行首轮 `mypy` 扫描并补齐 `docx`、`schedule`、`tqdm`、`fastapi.testclient`、`httpx` 等第三方最小类型桩，
   同步加固 `UnifiedQMTProvider` 可选依赖判空以及通知服务、AmazingData 测试夹具的动态导入守卫。
9. 将 `tools/validate_akshare_apis.py` 重写为基于 `TypedDict` 的结构化结果集，补齐 `tqdm.set_postfix` 桩与可选依赖判空，
   已通过独立 `mypy` 扫描，为后续工具脚本治理提供模板。
10. 新增 `infrastructure.cache`、`psutil`、`numpy.random`、`matplotlib.pyplot` 等最小类型桩，并针对 `tests/performance/benchmark_framework.py`
    以及多项工具脚本补充概率数组建模、可选参数判空和缓存类型标注，使相关 mypy 报错清零。
11. 完成 AmazingData 集成测试的彩色输出与进度条降级改造，引入本地 `Protocol` 与动态加载逻辑，
    同步扩充 `MarketData.get_kline_data` 与测试脚本访问的配置方法，保证缺失依赖时依旧满足 mypy 约束。
12. 清理事件引擎与数据提供者相关测试桩：补全事件批处理/回调的字典断言、将 `SimpleNamespace` 替换为模块占位，
    并为管理器 Dummy Provider 补足返回类型，使 mypy 可以在测试层验证接口契约。
13. 收敛数据库与缓存组件的状态接口，补齐 Redis、pytest-mock 的最小类型桩，并将旧版 `analytics_component` 合并为
    兼容导出，mypy 主命令诊断降至 45 项（-47）。
14. 调整 QMT 网关组件、统一 QMT 提供者与数据源管理器的接口签名，补充 AkShare 能力映射与 WebUI SQLAlchemy 查询类型，
    让 mypy 全量扫描返回 0 错误并解除剩余导入缺口。
15. 补齐配置管理与验证工具的类型注解：为 `ConfigManager`、`ConfigValidator` 及 `tools/validate_config.py` 增加显式返回类型、
    映射别名与降级守卫，确保在 `mypy` 扫描中同样保持 0 错误，并为后续启用 `--check-untyped-defs` 打下基础。

## 最新诊断概览
> 数据来源：`pyright --outputjson`（2025-10-10 执行）。

- 本轮扫描共计 **1388** 条诊断，分布在 **178** 个文件中，主因仍集中在旧版数据源管线、策略示例与仓储实现的接口漂移。

| 排名前十的文件 | 诊断数量 | 主要问题类别 |
| --- | --- | --- |
| `tests/unit/infrastructure/test_data_source_manager.py` | 99 | 沿用历史 `DataSourceRegistry` 与同步 API，返回结构与端口协议不一致 |
| `deepsearch/webui/api/endpoints/datasources/datasource_manager.py` | 64 | WebUI 服务层未按新端口判空，存在大量 `Optional` 属性访问与 Any 派发 |
| `deepsearch/strategies/implementations/momentum.py` | 44 | 策略示例直接访问旧版 `AmazingData` 同步接口，需要迁移到应用服务封装 |
| `tests/test_data_sources.py` | 43 | 工厂测试依赖废弃的注册路径，需接入 `deepsearch.application.services.market` |
| `deepsearch/strategies/implementations/simple_ma.py` | 39 | 同上，缺乏新的行情/回测端口适配 |
| `deepsearch/strategies/implementations/mean_reversion.py` | 38 | 同上 |
| `deepsearch/strategies/implementations/turtle_trading.py` | 34 | 同上 |
| `tests/integration/amazingdata/test_amazingdata_api.py` | 34 | 仍旧期望 `AmazingDataProvider.connect/disconnect` 等旧接口，需要兼容层 |
| `deepsearch/infrastructure/repositories/stock_repository.py` | 29 | 仓储实现引用被移动的 ORM 模型与类型别名，导致导入缺失与属性告警 |
| `deepsearch/infrastructure/repositories/stock_repository_impl.py` | 29 | 同上 |

### mypy 扫描摘要（第八轮）

- 命令：`mypy deepsearch tools tests examples`（2025-10-12 执行）。
- 诊断：**0 个错误**（↓45）覆盖 **545** 个文件。随着 QMT 组件、统一提供者以及数据源管理器接口的全面收敛，历史遗留的抽象类实例化和 TypedDict 缺口已全部闭合，当前仅剩 `annotation-unchecked` 提示等待逐步开启严格检查。
- 最新关注点：
  1. **WebUI 数据源桩** —— `tests/unit/webui/api/test_datasource_manager_router.py` 等文件仍依赖运行时打桩，后续需补齐正式枚举与协议桩并考虑启用 `--check-untyped-defs`。
  2. **事件引擎与批处理工具** —— 事件总线及性能脚本大多保留未注解函数体，建议结合业务排期逐步迁移到强类型实现。
  3. **策略与回测示例** —— 旧版策略脚本仍大量依赖 `Any`，需在文档迁移与示例更新时同步治理。

### 模块聚合分析

- **WebUI 数据源链路**：`tests/unit/webui/api/test_datasource_manager_router.py` 与 `deepsearch/webui/api/endpoints/data/*` 仍以运行时桩为主，应在补全协议与 TypedDict 后逐步启用严格函数体检查。
- **事件与消息系统**：事件引擎、进程管理器以及 `deepsearch/messaging/implementations/inmemory.py` 保留大量未注解方法，可在系统稳定后统一启用 `--check-untyped-defs` 并补全返回模型。
- **策略与回测示例**：`deepsearch/backtest/*` 与 `deepsearch/strategies/*` 仍沿用教学示例形态，需在文档迁移时同步治理类型并补齐最小桩。

## 后续修复计划
1. **AmazingData 兼容性**：为 `AmazingData` 模块补充类型桩，提供 `MarketData/BaseData` 等静态方法定义，并在接口层构建同步包装器，满足现有测试对 `connect/disconnect` 的预期。
2. **数据源管理器迁移**：梳理 `tests/unit/infrastructure/test_data_source_manager.py` 与 `datasource_manager.py`，对照新版 `DataSourceRegistry` 与服务化入口，统一类型注解及导入路径。
3. **策略示例与文档**：批量更新策略示例、教程脚本与 WebUI API，使其依赖新的 `MarketService` 与 `AmazingDataProvider` 兼容层，避免直接访问已废弃模块。
4. **工具脚本收敛**：逐一消除 `tools/validate_all_datasources.py` 与 `tools/update_data_provider_imports.py` 中的 `Optional` 判空与类型不匹配问题，必要时引入 `Protocol`/`TypedDict` 描述第三方返回数据。
5. **通知链路治理**：在补齐 `httpx` 类型桩后，梳理通知服务与测试对 `XtuisClient`、响应结构的依赖，校准 `NotificationService` 构造参数与返回值类型。
6. **持续追踪**：在每轮修改后执行 `pyright --outputjson` 与针对性 `mypy` 子集扫描，记录差异，确保诊断总量持续下降至可控范围。
7. **配套依赖桩完善**：继续为 `colorama` 等 CLI 依赖补写最小类型桩，并扩展 `schedule`/`tqdm` 的关键接口定义，统一处理降级逻辑，避免重复告警。

### 追加验证（2025-10-13）

- 命令：`mypy deepsearch`。
- 结果：**Success: no issues found in 433 source files**，仅保留 `annotation-unchecked` 级别提示。
- 结论：当前 `pyproject.toml` 中未启用 `ignore_missing_imports` 或类似忽略规则，`mypy` 并未通过配置屏蔽任何模块。

