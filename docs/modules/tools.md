# tools 模块实现说明

## 模块定位

`deepsearch.tools` 提供运维和开发辅助脚本，专注于日志分析、数据源诊断等独立工具，便于快速排查问题或生成报告。

## 目录结构

- `log_analyzer.py`：读取系统日志，支持关键字过滤、异常聚类、时间轴分析。
- `datasource_diagnostics/`：数据源自检脚本，检测授权状态、响应延迟、字段完整性。

## 使用方式

- 可通过 `uv run python -m deepsearch.tools.log_analyzer --help` 查看命令参数。
- 数据源诊断脚本支持指定环境配置，与 `infrastructure.providers` 共享校验逻辑。

## 扩展建议

- 新增脚本时保持模块化设计，提供函数入口便于测试。
- 处理敏感信息时需遵守脱敏规则，避免日志泄露密钥。
- 工具脚本改动需同步在文档中记录，以便团队成员了解可用能力。
