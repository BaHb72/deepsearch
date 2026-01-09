# 核心引擎模块概览

## 模块定位

`deepsearch/core` 是 DeepSearch 的运行时引擎与组件系统所在。它负责组件生命周期管理、依赖注入、主引擎调度、健康检查以及统一的异步执行环境，是所有业务/基础设施模块的枢纽层。

## 核心文件

- `async_component.py`：定义 `AsyncComponent` 抽象基类，提供状态机驱动的生命周期（initialize/start/stop/dispose）、异步任务管理、统计指标采集接口。组件识别
  `ComponentType`（业务、基础设施等）并暴露 `status/state/resource`。
- `component_state.py`：描述 `ComponentLifecycle`、`ComponentState` 与 `ComponentStateManager`，统一状态迁移与错误处理。
- `component_factory.py`、`unified_components.py`：根据配置动态装配组件集，预置基础设施、业务、WebUI、监控等组件组合。
- `components/`：内置组件实现，例如 `EventEngineComponent`（封装事件引擎）、`MessageBusComponent`（消息总线）、
  `DatabaseComponent`、`CacheComponent`、`GatewayComponent`、`AnalyticsComponent`、`WebUIComponent`、`QMTGatewayComponent`
  等，每个都继承 `AsyncComponent` 并在 `_do_initialize/_do_start/_do_stop` 中完成本子系统的启动和清理。
- `managers/component_manager.py`：负责组件注册、依赖解析、并发启动、优雅关闭与异常处理；`managers/process_manager.py`
  管理多进程场景下的引擎注册和信号转发。
- `runtime/engine.py`：`MainEngine` 核心调度器，组合 `ComponentManager`、`AsyncContainer` 以 DI 方式构建组件；按运行模式（
  `all/engine/webui`）分阶段启动基础设施、业务、前端；接入 `EngineIPCServer`、健康管理器、端口探测等。
- `runtime/async_runner.py`：封装顶层入口 `AsyncRunner` 与 `run_async_engine`，处理事件循环、信号、模式切换；
  `async_engine_context` 提供 async contextmanager 用于测试或嵌入式运行。
- `runtime/context.py`、`engine_context.py`：暴露线程安全的上下文存取（当前引擎、组件容器等），供其他模块访问运行态。
- `health/`：`HealthCheckManager` 聚合多种 `HealthChecker`，周期性执行检测并暴露结果。
- `utils/`：通用工具，如 `async_timeout`、`container`（轻量依赖注入容器）、`decorators`（生命周期装饰器）、`error_handler`、`ipc`
  （ZeroMQ/Socket IPC）、`statistics`（运行指标采集）等。
- `errors.py`、`error_handling.py`：统一异常类型、包装上下文，用于日志与诊断。

## 运行流程

1. CLI 调用 `run_async_engine` 后，`AsyncRunner` 初始化 `MainEngine`，注册到 `process_manager` 并加载配置。
2. `MainEngine.initialize_async` 通过 `component_factory` 根据模式构建组件图，注入配置、依赖，初始化统计采集与健康检查。
3. `_start_phased_async` 根据模式分阶段启动：先启动基础设施（消息总线、缓存、数据库等），再启动业务组件（策略、回测、gateway），最后可选启动
   WebUI 与前端。
4. 引擎运行期间监听系统信号，`process_manager`/`EngineIPCServer` 支持跨进程控制与状态查询。
5. 停止流程中，`ComponentManager` 反向遍历组件依赖顺序调用 `stop_async`，同时释放运行中的任务与资源。
6. 健康检查通过 `HealthCheckManager` 定时执行 `checkers`，结果可被监控模块或 CLI 查询。

## 重要特性

- 全部组件遵循端口 + 适配器架构：组件内部仅依赖抽象接口，通过容器注入具体实现。
- `AsyncComponent` 内置统计收集器，可向 `observability` 模块推送运行指标。
- `ComponentManager` 支持并行启动（利用 `asyncio.gather`，带超时与失败回滚），并维护组件依赖图防止重复加载。
- `MainEngine` 集成端口检测（防止占用冲突）、日志系统初始化、WebUI 实际端口回填等细节，保证部署一致性。
- `runtime` 模块提供同步/异步两种入口，方便 CLI、测试或其他Python应用嵌入运行。

## 与其他模块协作

- 业务模块（`application`、`backtest`、`strategies` 等）通过继承 `AsyncComponent` 注册到核心引擎。
- `observability`、`messaging`、`infrastructure` 等子系统由核心组件在启动阶段初始化，并通过容器向其他组件提供服务。
- 事件总线、消息队列、数据库连接等资源也通过核心模块统一管理和清理。

## 扩展建议

- 新增子系统时建议继承 `AsyncComponent` 并通过 `component_factory` 注册，声明依赖和启动顺序。
- 需要新增健康检查项时，在 `health/checkers.py` 中实现 `HealthChecker` 并在 `HealthCheckManager` 注册。
