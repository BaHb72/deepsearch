# cli 模块实现说明

## 模块定位

`deepsearch.cli` 提供终端命令入口，面向运维与开发调试场景。模块基于 `typer` 封装，支持启动引擎、管理任务、诊断运行状态等操作。

## 主要文件

- `main.py`：命令分组定义，包含 `run`、`diagnose`、`config` 等子命令。
- `debug_commands.py`：调试辅助命令，支持追踪事件、导出内存快照、触发模拟数据。
- `__init__.py`：暴露 CLI 应用实例，供 `python -m deepsearch` 直接调用。

## 核心数据结构

- `CliContext`：封装全局配置、日志、依赖注入容器，注入到各命令。
- `CommandResult`：标准命令执行结果，包含状态码与可选的 JSON 输出。

## 关键流程

1. 入口脚本解析命令行参数，加载 `settings` 并注入 `CliContext`。
2. 根据子命令调用对应函数，必要时启动事件引擎或 WebUI。
3. Debug 命令可通过 `messaging` 发布测试消息、模拟行情。
4. 异常将被捕获并输出结构化日志，同时返回非零状态码。

## 扩展与集成

- 新增命令时，在 `main.py` 中注册，并视情况放入独立模块。
- 需复用系统依赖时，通过 `config.loader` 和 `core.ComponentFactory` 获取。
- 命令输出应兼容管道处理，避免输出颜色控制符或大量非结构化文本。
- 跨平台脚本（Windows/WSL）请保持路径转换与编码一致性。
