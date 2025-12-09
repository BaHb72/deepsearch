# CLI 模块概览

## 模块定位

`deepsearch/cli` 基于 `click` 提供 DeepSearch 的命令行入口。仓库通过 `main.py` 暴露系统管理、诊断、配置操作，同时在
`debug_commands.py` 中补充调试子命令，方便在开发或运维场景下快速操控核心引擎、WebUI 及周边组件。

## `main.py` 主要命令

- `run`：设置 `APP__ENV`，加载 `settings.<env>.yaml`，校验 Redis 与端口占用，并根据 `mode` (`full`/`engine`/`webui`) 调用
  `core.runtime.async_runner.run_async_engine` 或独立启动 WebUI。
- `webui`：单独启动 WebUI 服务，可选是否拉起前端、指定端口并自动打开浏览器。
- `check_ports`：调用 `utils.system.port_checker` 输出关键端口占用情况。
- `check-amazingdata`：执行 AmazingData 连接与认证诊断，汇总结果为 JSON。
- `start` / `stop` / `status` / `cleanup` / `diagnose`：围绕 `ComponentManager` 与 `process_manager`
  提供组件启停、状态查询、资源清理、系统体检等能力。
- `init`：生成示例配置文件，指导用户二次修改。
- `config show` / `config set`：展示或更新 `settings.<env>.yaml` 配置，支持 YAML/JSON/表格输出以及类型感知的写入。
- `debug` 组：若安装了 `debug_commands.py`，会注入性能、内存、日志等调试子命令；在非 dev 环境会提示切换至开发模式。

命令特点：

- 统一依赖 `observability.logger.logger_manager` 控制日志级别与输出，确保 CLI 与引擎一致。
- 关键任务前进行环境自检（Redis、端口、配置文件），失败时友好提示并退出。
- 多数命令借助 `click.echo`/`click.secho` 保持一致的终端体验，并通过选项提供细粒度控制。

## `debug_commands.py` 概览

- `debug.errors`：读取 `core.utils.error_handler` 的错误历史，使用 `rich` 表格展示，并支持导出 JSON 报告。
- `debug.profile`：驱动 `debug.performance_profiler.profiler`，展示热点函数耗时；可导出性能报告。
- `debug.memory`：调用 `memory.smart_memory.memory_manager` 实时查看内存使用、缓存命中率。
- `debug.db`：展示 `infrastructure.persistence.query_optimizer` 统计信息。
- `debug.watch`：利用 `psutil` 构建系统监控面板（CPU/内存/线程）。
- `debug.clear` / `debug.report`：一键清理调试数据或生成综合报告（JSON/HTML/文本）。

## 工作流程要点

1. 用户运行 `deepsearch <command>`，`click` 解析参数后初始化日志与配置。
2. 涉及核心引擎的命令会调用 `core.runtime.async_runner` 或 `MainEngine`，确保组件按依赖顺序启动/停止。
3. 诊断类命令懒加载所需依赖，避免 CLI 启动时即加载重量级模块。
4. 与配置相关的命令严格使用 UTF-8 读写文件，避免产生编码问题。

## 与其他模块的关系

- 深度依赖 `deepsearch.config`（`get_config`、`config_manager`、`settings`）以读取和修改环境参数。
- 与 `core.runtime`、`webui.runner`、`observability`、`memory`、`infrastructure.persistence` 等模块联动，对系统运行态进行操控与诊断。

## 扩展建议

- 新命令可以通过 `cli.command()` 或新增子命令组注册，并保持现有帮助文案风格一致。
- 长时间运行或需要实时输出的命令建议结合 `rich` 组件，提升可读性。
