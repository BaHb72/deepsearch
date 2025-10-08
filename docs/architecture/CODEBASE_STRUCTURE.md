# DeepSearch 代码结构全景分析

## 1. 顶层目录速览
- `deepsearch/`: 核心 Python 包，包含事件引擎、基础设施、交易策略与 WebUI 后端等全部业务代码。
- `docs/`: 已有架构、API、运维和测试文档，本文件位于 `docs/architecture/` 作为代码结构索引。
- `tests/` 与 `deepsearch/tests/`: 前者聚焦系统与集成测试集合，后者附带包内的实验性或旧版测试。
- `scripts/`、`tools/`: 辅助调试、自动化检查、接口生成脚本，配合 `uv` 与 `npm` 工作流。
- `examples/`: 提供回测与数据接口示例，可作为模块组合的入门参考。
- 运行产物(`logs/`、`reports/`、`htmlcov/` 等)集中在根目录，便于排查。

## 2. 运行入口与启动模式
- CLI 入口 `deepsearch/main.py` / `deepsearch/__main__.py`：统一暴露 `python -m deepsearch`，内部调用 `deepsearch/cli/main.py`。
- `deepsearch/cli/main.py`: 定义 `run`、`webui`、`check_ports`、`check-amazingdata` 等命令，负责设置 `APP__ENV`、加载配置、启动日志与事件引擎。
- `deepsearch/core/runtime/async_runner.py`: 根据 CLI 传入的模式(`full`/`engine`/`webui`)装配组件并驱动事件循环。
- WebUI 单独模式通过 `deepsearch/webui/runner.py` 启动 FastAPI 与前端代理，支持仅启动后端或联动前端。

## 3. 核心运行时 (core + event)
- `deepsearch/core/async_component.py` 与 `component_state.py`: 定义组件生命周期模板、状态机与异常治理，保障组件装载/卸载一致。
- `deepsearch/core/component_factory.py`: 组件注册与实例化中心，结合 `core/utils/container.py`、`infrastructure/di/container.py` 实现半自动依赖注入。
- `deepsearch/core/managers/`: `component_manager.py` 管理组件目录与依赖拓扑，`process_manager.py` 负责多进程 worker 生命周期。
- `deepsearch/core/runtime/engine.py`、`engine_adapter.py`、`engine_context.py`: 将事件系统、数据源、策略执行绑定成统一的运行时上下文。
- `deepsearch/event/engine/engine.py`: 主事件引擎，线程模型包含调度器 + 分发器，支持批处理、异步 handler、优先级队列与监控钩子。
- `deepsearch/event/bus/bus.py`: 发布/订阅总线抽象，结合 `deepsearch/messaging/bus.py` 提供复合消息管道。
- `deepsearch/event/handlers/` 与 `strategies/events/`: 定义事件类型、域内事件处理器，配合 `deepsearch/constants/events.py` 统一事件名。

## 4. 基础设施层 (infrastructure)
- `cache/`: 多级缓存框架，`multilevel_cache.py` 组合内存/Redis/数据库策略，`strategies/` 实现 LRU、TTL 等策略，`providers/` 目前提供内存缓存实现。
- `database/optimized_pool.py` 与 `persistence/`: 实现数据库/ DuckDB/ 时序数据访问，`unit_of_work.py` 与仓储(`repositories/`)组合形成事务边界。
- `providers/`: 数据源总目录，分为 `interfaces/`、`base/`、`managers/`、`implementations/`(AmazingData、AkShare、QMT 等)；其中 `implementations/amazingdata/` 通过进程池、代理封装数据源 SDK。
- `providers/datafeed/qmt/scripts/`: QMT 终端脚本 (GBK 编码)；`miniqmt/`、`qmt/` 提供数据适配。
- `messaging/event_publisher.py`: 下沉消息发布实现，与上层 `deepsearch/messaging` 复用。
- `monitoring/`: 运行时监控指标、依赖健康探测；`notifications/` 负责统一通知客户端与配额管理。
- `di/container.py`: 轻量依赖注入容器，支持 Singleton/Scoped/Transient 生命周期。

## 5. 数据与交易域模块
- `backtest/`: Backtrader 集成，包含 `engines/`、`components/`、`interfaces/`、`adapters/` 与 `utils/`，配套 README 指南。
- `gateway/`: 定义 `BaseGateway` 与具体网关装配逻辑，桥接行情/交易服务器。
- `strategies/`: 按 `interfaces/`、`managers/`、`services/`、`implementations/` 划分，支持策略注册、事件响应与回测复用。
- `indicators/`: 技术指标工具集，供策略与回测共用。
- `memory/smart_memory.py`: 统一的内存占用优化与缓存包装。

## 6. WebUI 后端 (FastAPI)
- `deepsearch/webui/server.py`: 构建 FastAPI 应用，挂载路由、异常处理、静态资源与 Socket 服务。
- `webui/api/`: 路由分层——`endpoints/` 存放具体 API，`services/`/`providers.py` 负责业务拼装，`middleware/` 增加防抖与限流，`cache/` 提供统一缓存视角。
- `webui/dependencies.py`、`auth.py`: 提供依赖注入、认证钩子与上下文封装。
- `webui/runner.py`、`server_manager.py`: WebUI 运行管理与子进程控制，配合 CLI `run`/`webui` 入口。

## 7. WebUI 前端 (Vite + React/Ant Design)
- 根配置 (`package.json`, `vite.config.ts`, `eslint.config.js`) 对应 React + TypeScript 技术栈，使用 Zustand/Vite 插件。
- `src/api/` 与 `src/services/api/`: 与 `docs/api/FRONTEND_API_REGISTRY.md` 一致，封装 axios 请求，默认 `baseURL=/api`。
- `src/stores/`: Zustand 状态管理，含系统状态、数据库状态等 store。
- `src/pages/`、`src/views/`: 页面/视图划分，对应系统设置、通知中心等模块。
- `src/components/`、`src/layouts/`: 组件库封装与布局；`src/services/websocket/` 管理实时订阅。
- `.trash/` 目录存放临时回收内容，需忽略。

## 8. 工具、脚本与自动化
- `scripts/run_all_tests.py`: 聚合测试入口，可加 `--quick` 执行快速集。
- scripts/debug_backend.py: 调试与故障复现脚本；历史片段见 scripts/archive/2025-10-05/test_state_sync.js。
- `tools/generate_api_documentation.py`: API 文档生成器，修改接口后需运行并更新 `docs/api/`。
- `tools/analyze_*` 系列：依赖分析、性能诊断、架构迁移等辅助工具，配合 `CLAUDE.md` 中的 mock 示例。
- `.bat`/`.ps1` 启动脚本 (`run_dev.ps1`, `run_dev.bat` 等) 适配 Windows 环境。

## 9. 配置与环境管理
- `deepsearch/config/`: `settings.py` + Pydantic 模型管理配置；`loader.py`、`manager.py` 负责加载 `settings.{env}.yaml`；`validator.py` 做结构校验。
- `config/models/`: 定义分模块配置模型，如数据库、缓存、数据源等。
- `settings.*.yaml` 与 `settings.template.yaml`: 环境配置模板，敏感信息需使用示例/占位符。
- `constants/` 目录与 `constants.py`: 提供系统、事件、业务常量，避免硬编码。

## 10. 测试体系
- 根目录 `tests/`
  - `unit/`: 单元测试，命名遵循 `test_<module>_<case>`。
  - `integration/`、`api/`: 集成与接口测试；`test_system.py`、`test_monitoring.py` 覆盖关键链路。
  - `fixtures.py`、`stubs/`: Mock 与伪数据，支持 AmazingData 隔离测试。
- `deepsearch/backtest/tests/`: 回测模块自带的针对性测试。
- 推荐执行顺序：`python scripts/run_all_tests.py` → `pytest tests/unit -n auto` → 覆盖率/安全扫描。

## 11. 文档与示例
- `docs/README.md`: 文档索引，指向架构、开发、运维与 API 说明。
- `docs/api/`: API 总览、前后端映射、数据源规范，接口变更后需重新生成并登记变更原因。
- `docs/architecture/`: 保存系统/策略/缓存等架构设计，本文件补充代码结构视角。
- `examples/*.py`: 展示回测、数据接口调用方式，可与 `deepsearch/backtest`、`infrastructure/providers` 对照学习。

## 12. 依赖关系与扩展点
- 纵向分层：CLI → Runtime(core/event) → Domain(backtest/strategies/gateway) → Infrastructure → Providers → 外部服务。
- 核心模式：事件驱动 + 组件工厂 + DI + Repository/UnitOfWork，可通过新增组件或 providers 扩展。
- 数据源扩展需遵循 `infrastructure/providers/interfaces/base.py`，并将实现注册到 `providers/managers` 管理器。
- 缓存/持久化扩展分别挂载于 `infrastructure/cache/providers/` 与 `infrastructure/persistence/`，注意同步配置模型。
- WebUI API 增量需在 `webui/api/endpoints/` 添加路由，并更新 `docs/api/` 与前端 `src/api`。

## 13. 协作与质量控制提醒
- 统一使用 Python 3.13 + UV 工具链，Windows 环境通过仓库内虚拟环境运行；WSL 仅限只读。
- 修改配置或敏感逻辑需同步 `.example` 模板与安全自检 (`git grep -i "password\|secret\|token" -- ':(exclude)*.example'`)。
- 提交前执行 `ruff check`、`black`、`isort`、`mypy` (类型敏感模块) 与 `bandit -r deepsearch`；必要时更新 `docs/testing`。
- 前端改动需说明效果，接口调整必须更新 API 文档并记录时间/内容/原因。

---
本文件聚焦代码目录与职责映射，配合 `docs/architecture/SYSTEM_ARCHITECTURE.md`、`docs/api/README.md` 可快速定位到对应实现与文档。后续若有新模块或目录调整，请同步维护此索引。
