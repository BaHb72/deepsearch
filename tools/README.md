# tools/ 目录说明

本目录包含 **开发工具** 和 **架构迁移脚本**。

## 目录结构

| 类别 | 文件模式 | 用途 |
|------|----------|------|
| 架构工具 | `architecture_*.py` | 架构健康检查和迁移 |
| 分析工具 | `analyze_*.py`, `performance_analyzer.py` | 性能分析和依赖分析 |
| 迁移工具 | `update_*.py`, `safe_architecture_migration.py` | 代码迁移和导入更新 |
| 验证工具 | `validate_*.py` | 配置和API验证 |
| 生成工具 | `generate_api_*.py` | API文档生成 |
| 运行工具 | `run_system.py`, `startup.py`, `webui_standalone.py` | 系统启动 |
| 清理工具 | `cleanup_*.py` | 清理废弃代码 |

## 运行方式

```bash
# 架构健康检查
uv run python tools/architecture_health_monitor.py

# 分析依赖关系
uv run python tools/analyze_dependencies.py

# 验证配置
uv run python tools/validate_config.py

# 启动WebUI（独立模式）
uv run python tools/webui_standalone.py
```

## 相关目录

- `scripts/` - SDK测试和数据验证脚本
- `tests/` - pytest单元测试和集成测试
