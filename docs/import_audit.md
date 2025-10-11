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
| `tools/validate_all_datasources.py` | 30 | 运行时判空、`asyncio.gather` 类型收敛及 SDK 检测逻辑待进一步完善 |

## 后续修复计划
1. **AmazingData 兼容性**：为 `AmazingData` 模块补充类型桩，提供 `MarketData/BaseData` 等静态方法定义，并在接口层构建同步包装器，满足现有测试对 `connect/disconnect` 的预期。
2. **数据源管理器迁移**：梳理 `tests/unit/infrastructure/test_data_source_manager.py` 与 `datasource_manager.py`，对照新版 `DataSourceRegistry` 与服务化入口，统一类型注解及导入路径。
3. **策略示例与文档**：批量更新策略示例、教程脚本与 WebUI API，使其依赖新的 `MarketService` 与 `AmazingDataProvider` 兼容层，避免直接访问已废弃模块。
4. **工具脚本收敛**：逐一消除 `tools/validate_all_datasources.py` 等工具中的 `Optional` 判空与类型不匹配问题，必要时引入局部 `Protocol` 或 `TypedDict` 描述第三方返回数据。
5. **持续追踪**：在每轮修改后执行 `pyright --outputjson` 并记录差异，确保诊断总量持续下降，直至全部导入问题消除。
6. **配套依赖桩完善**：为 `colorama`、`tqdm` 等仅用于调试输出的依赖补齐最小类型桩，统一处理 CLI 工具中的降级逻辑，避免重复出现的 `reportAssignmentType` 告警。

