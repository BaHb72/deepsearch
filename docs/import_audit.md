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

## 最新诊断概览
> 数据来源：`pyright --outputjson`（2025-10-10 执行）。

| 排名前十的文件 | 诊断数量 | 主要问题类别 |
| --- | --- | --- |
| `tests/unit/infrastructure/test_data_source_manager.py` | 101 | 依赖旧版数据源注册接口，需补齐新的端口定义与类型桩 |
| `deepsearch/webui/api/endpoints/datasources/datasource_manager.py` | 64 | 服务层与端口层未对齐，存在大量 `None` 属性访问告警 |
| `deepsearch/strategies/implementations/momentum.py` | 44 | 策略示例仍假定老版 `AmazingData` 同步 API，需要统一为新的服务封装 |
| `tests/test_data_sources.py` | 43 | 数据源工厂使用过时路径，需要迁移到 `deepsearch.application.services.market` |
| `deepsearch/strategies/implementations/simple_ma.py` | 39 | 同上，依赖旧版回测端口与数据源配置 |
| `deepsearch/strategies/implementations/mean_reversion.py` | 38 | 同上 |
| `tests/integration/amazingdata/test_amazingdata_api.py` | 35 | 期望 `AmazingDataProvider.connect/disconnect` 等旧接口，需要补充兼容包装 |
| `deepsearch/strategies/implementations/turtle_trading.py` | 34 | 旧版策略示例依赖被移除的同步接口 |
| `examples/data_interface_usage.py` | 32 | 示例脚本直接导入旧模块，缺少新的兼容封装 |
| `tools/validate_all_datasources.py` | 24 | `mypy` 与 `pyright` 均提示的可选依赖判空、联合类型拆解与 SDK 句柄降级问题已部分缓解，仍需补充协议建模 |

### mypy 首轮扫描摘要

- 命令：`mypy deepsearch tools tests`（2025-10-11 执行）。
- 诊断：42 个错误分布在 17 个文件，主要集中在以下三类：
  1. **可选依赖判空缺失** —— 数据同步服务、AkShare/Cloudflare 管理器及部分 QMT 组件在后端句柄为空时直接访问属性。
  2. **类型桩缺口** —— 通知链路依赖的 `httpx` API、CLI 脚本引用的 `docx/schedule/tqdm` 等缺乏静态定义，本轮已补齐常用接口。
  3. **历史接口残留** —— 数据源管理器与 WebUI 端点仍调用已废弃的同步方法或旧枚举，导致返回值类型为 `Any`。
- 已完成：新增 `docx`、`schedule`、`tqdm`、`fastapi.testclient`、`httpx` 类型桩，并补强 `UnifiedQMTProvider`、通知服务测试、AmazingData 登录测试的判空逻辑。
- 未解项：通知服务 `XtuisClient` 适配、`DataSyncService` 入参校验、QMT 网关 TypedDict 对齐、数据源管理器返回值建模等。

## 后续修复计划
1. **AmazingData 兼容性**：为 `AmazingData` 模块补充类型桩，提供 `MarketData/BaseData` 等静态方法定义，并在接口层构建同步包装器，满足现有测试对 `connect/disconnect` 的预期。
2. **数据源管理器迁移**：梳理 `tests/unit/infrastructure/test_data_source_manager.py` 与 `datasource_manager.py`，对照新版 `DataSourceRegistry` 与服务化入口，统一类型注解及导入路径。
3. **策略示例与文档**：批量更新策略示例、教程脚本与 WebUI API，使其依赖新的 `MarketService` 与 `AmazingDataProvider` 兼容层，避免直接访问已废弃模块。
4. **工具脚本收敛**：逐一消除 `tools/validate_all_datasources.py` 与 `tools/update_data_provider_imports.py` 中的 `Optional` 判空与类型不匹配问题，必要时引入 `Protocol`/`TypedDict` 描述第三方返回数据。
5. **通知链路治理**：在补齐 `httpx` 类型桩后，梳理通知服务与测试对 `XtuisClient`、响应结构的依赖，校准 `NotificationService` 构造参数与返回值类型。
6. **持续追踪**：在每轮修改后执行 `pyright --outputjson` 与针对性 `mypy` 子集扫描，记录差异，确保诊断总量持续下降至可控范围。
7. **配套依赖桩完善**：继续为 `colorama` 等 CLI 依赖补写最小类型桩，并扩展 `schedule`/`tqdm` 的关键接口定义，统一处理降级逻辑，避免重复告警。

