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

### mypy 扫描摘要（第二轮）

- 命令：`mypy deepsearch tools tests`（2025-10-10 执行）。
- 诊断：**198 个错误** 分布在 **48 个文件**，问题类型聚焦于：
  1. **测试与示例缺乏类型桩** —— `tests/performance/benchmark_framework.py`、`tests/base/component_test_base.py` 等引用 `matplotlib`、`pytest_mock`、内部未迁移模块，触发导入缺失与 `Any` 派发。
  2. **工具脚本模型未显式建模** —— `tools/validate_akshare_apis.py`、`tools/analyze_performance_bottlenecks.py` 等使用裸 `dict`/`list`，导致赋值与返回类型不匹配。
  3. **数据源与组件协议错位** —— `deepsearch/core/components/analytics_component.py`、`deepsearch/core/components/qmt_gateway_component.py` 与相关管理器的返回签名仍为旧版，未对齐 `AsyncComponent`/`DataProvider` 协议。
- 重点文件 TOP5：
  | 文件 | 错误数量 | 首要问题 |
  | --- | --- | --- |
  | `tests/performance/benchmark_framework.py` | 21 | 缺失 `infrastructure.cache`/`matplotlib` 类型桩、`numpy.random` API 判定及 None 判空 |
  | `tests/base/component_test_base.py` | 21 | `pytest_mock` 与 `async_component_v2` 缺桩，且多处协程缺少 `await`、状态枚举未补全 |
  | `tests/webui/test_api_endpoints.py` | 20 | `TestClient` 响应被视为 `_Response`，缺少 `json/text` 方法定义与 `options` 动态方法 |
  | `tools/validate_akshare_apis.py` | 14 | `tqdm` 上下文协议、`None` 默认值与 `TypedDict` 字段赋值不匹配 |
  | `tests/unit/webui/api/test_datasource_manager_router.py` | 14 | 手工搭建的 stub 模块缺失必要属性，`type: ignore` 多余 |
- 其余 43 个文件分别涉及 Redis、AmazingData、QMT 网关、DI 容器等子系统，后续需按模块集中治理。

### 模块聚合分析

- **数据源管理链路**：`tests/unit/infrastructure/test_data_source_manager.py`、`deepsearch/webui/api/endpoints/datasources/datasource_manager.py` 同时在 pyright 与 mypy 中高频报错，表明 WebUI 服务层与底层注册中心尚未统一。下一步应优先梳理数据源协议、补齐 TypedDict 与枚举导出，减少 `Any` 与 `Optional` 传播。
- **AmazingData 集成测试**：`tests/integration/amazingdata/*` 在 pyright（约 120 条）与 mypy（>20 条）均有大量 `None` 判空与旧接口问题，需补充兼容包装及在类型桩中声明 `connect/disconnect`、`get_calendar` 等 API。
- **工具脚本体系**：`tools/validate_akshare_apis.py`、`tools/analyze_performance_bottlenecks.py`、`tools/architecture_health_monitor.py` 等在两套检查器下均提示 `Optional` 默认值、`list[float]` 与标量混用等问题，建议统一以 `TypedDict`/`dataclass` 建模并补充类型桩（如 `tqdm` 上下文管理）。
- **测试基类与性能基准**：`tests/base/component_test_base.py`、`tests/performance/benchmark_framework.py` 同时命中多项缺桩与协议校验，需要补齐 `pytest_mock`、`matplotlib`、`numpy.random` 等 stubs，并根据组件协议补上协程 `await` 与状态枚举。
- **核心组件协议**：`deepsearch/core/components/analytics_component.py`、`deepsearch/core/components/qmt_gateway_component.py`、`deepsearch/infrastructure/providers/managers/enhanced_manager.py` 等报错集中在返回类型不符合 `AsyncComponent`/`DataProvider` 约束，后续治理应在端口层明确返回值模型，并同步更新实现与测试。

## 后续修复计划
1. **AmazingData 兼容性**：为 `AmazingData` 模块补充类型桩，提供 `MarketData/BaseData` 等静态方法定义，并在接口层构建同步包装器，满足现有测试对 `connect/disconnect` 的预期。
2. **数据源管理器迁移**：梳理 `tests/unit/infrastructure/test_data_source_manager.py` 与 `datasource_manager.py`，对照新版 `DataSourceRegistry` 与服务化入口，统一类型注解及导入路径。
3. **策略示例与文档**：批量更新策略示例、教程脚本与 WebUI API，使其依赖新的 `MarketService` 与 `AmazingDataProvider` 兼容层，避免直接访问已废弃模块。
4. **工具脚本收敛**：逐一消除 `tools/validate_all_datasources.py` 与 `tools/update_data_provider_imports.py` 中的 `Optional` 判空与类型不匹配问题，必要时引入 `Protocol`/`TypedDict` 描述第三方返回数据。
5. **通知链路治理**：在补齐 `httpx` 类型桩后，梳理通知服务与测试对 `XtuisClient`、响应结构的依赖，校准 `NotificationService` 构造参数与返回值类型。
6. **持续追踪**：在每轮修改后执行 `pyright --outputjson` 与针对性 `mypy` 子集扫描，记录差异，确保诊断总量持续下降至可控范围。
7. **配套依赖桩完善**：继续为 `colorama` 等 CLI 依赖补写最小类型桩，并扩展 `schedule`/`tqdm` 的关键接口定义，统一处理降级逻辑，避免重复告警。

