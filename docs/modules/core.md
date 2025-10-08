# core 模块实现说明

## 模块定位

`deepsearch.core` 负责将系统内的功能单元抽象为可组合的组件体系，统一管理生命周期、依赖关系与容错策略，是运行时装配的基础层。所有事件引擎、数据源、消息通道等上层能力都会在此模块注册为组件。

## 目录结构

- `async_component.py`：定义异步组件基类与事件循环调度逻辑。
- `component_factory.py`：组件注册/创建工厂，支持依赖注入、配置化加载。
- `component_state.py`：跟踪组件状态、健康度与生命周期事件。
- `errors.py`、`error_handling.py`：封装统一的异常层级、熔断与降级策略。
- `components/`：内置组件实现（缓存、数据库、事件适配器等）。
- `managers/`、`runtime/`：组件容器、运行时上下文与协程调度工具。
- `utils/`：组件元数据、标签管理与序列化辅助方法。

## 核心类与数据结构

- `Component`/`ComponentType`：接口与枚举描述组件的功能边界。
- `ComponentConfig`：组件注册配置，记录名称、依赖、启用状态与私有配置。
- `ComponentState`：包含状态机、健康快照、最近错误等字段，支撑监控面板。
- `AsyncComponentRuntime`：封装事件循环、线程池与取消令牌，确保异步组件可安全关闭。

## 关键流程

1. 启动时通过 `ComponentFactory.register()` 绑定组件类型与构造函数。
2. 加载配置(`settings.*.yaml`)后，`ComponentFactory.create()` 根据依赖关系递归实例化组件。
3. `ComponentStateManager` 持续收集心跳/异常并写入 observability 管道。
4. 当组件发生异常，`ErrorContext` 根据策略执行重试、降级或触发全局停机事件。

## 扩展与集成

- 推荐通过子类化 `Component` 并在 `components/` 下新增文件，再在 `ComponentFactory` 中登记。
- 若需要异步行为，继承 `AsyncComponent` 并实现 `run_forever()` 与 `shutdown()`。
- 组件间共享依赖统一通过构造函数注入，避免从全局单例读取。
- 监控指标需在 `ComponentState` 中注册字段，并在 `observability` 中添加上报逻辑。
